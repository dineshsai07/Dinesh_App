"""Voice — Whisper STT + neural British TTS (edge-tts) with macOS fallback."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
import whisper

from config import (
    CHANNELS, MAX_RECORD, PREFERRED_VOICES, SAMPLE_RATE,
    SILENCE_DB, SILENCE_SECS, SPEECH_RATE, WHISPER_MODEL,
    TTS_VOICE, TTS_RATE,
)

_speak_proc = None
_whisper_model = None
_whisper_lock = threading.Lock()
_whisper_loading = False
_edge_available = None
_listen_abort = threading.Event()

# Give up if no speech starts within this many seconds
LISTEN_IDLE_SECS = 6
# Absolute wall-clock cap (InputStream.read can otherwise hang forever)
LISTEN_HARD_TIMEOUT = MAX_RECORD + 4


def abort_listen():
    """Signal active mic capture to stop (HUD Esc / Stop)."""
    _listen_abort.set()
    try:
        sd.stop()
    except Exception:
        pass


def pick_voice() -> str:
    """Display name for HUD — neural British when edge-tts works."""
    if _has_edge_tts():
        return TTS_VOICE.replace("en-GB-", "").replace("Neural", "") + " · Neural"
    try:
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        available = result.stdout.lower()
        for v in PREFERRED_VOICES:
            if v.lower() in available:
                return v + " · System"
    except Exception:
        pass
    return "Alex · System"


def _has_edge_tts() -> bool:
    global _edge_available
    if _edge_available is not None:
        return _edge_available
    try:
        import edge_tts  # noqa: F401
        _edge_available = True
    except ImportError:
        _edge_available = False
    return _edge_available


def _load_whisper_sync():
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            _whisper_model = whisper.load_model(WHISPER_MODEL)
    return _whisper_model


def preload_whisper_background():
    global _whisper_loading
    if _whisper_loading or _whisper_model is not None:
        return

    def _worker():
        global _whisper_loading
        _whisper_loading = True
        try:
            _load_whisper_sync()
        finally:
            _whisper_loading = False

    threading.Thread(target=_worker, daemon=True).start()


def warm_audio_pipeline_background():
    """
    Best-effort warmup so first speak/listen interactions feel instant:
    - cache edge-tts availability
    - resolve preferred voice label
    - begin Whisper preload
    """
    def _worker():
        try:
            _has_edge_tts()
            pick_voice()
            preload_whisper_background()
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="dinesh-audio-warm").start()


def get_whisper_model():
    return _load_whisper_sync()


def _record_inner() -> np.ndarray:
    """Capture until silence, idle timeout, max length, or abort."""
    chunk_ms = 100
    chunk_size = int(SAMPLE_RATE * chunk_ms / 1000)
    max_chunks = int(MAX_RECORD * 1000 / chunk_ms)
    idle_limit = int(LISTEN_IDLE_SECS * 1000 / chunk_ms)
    silence_limit = int(SILENCE_SECS * 1000 / chunk_ms)
    frames: list[np.ndarray] = []
    started = False
    silent_n = 0
    idle_n = 0

    # Prefer built-in mic; avoid hanging on Continuity Camera / iPhone devices
    try:
        devices = sd.query_devices()
        prefer = None
        for i, d in enumerate(devices):
            name = str(d.get("name", "")).lower()
            if d.get("max_input_channels", 0) > 0 and "macbook" in name:
                prefer = i
                break
        if prefer is None:
            for i, d in enumerate(devices):
                if d.get("max_input_channels", 0) > 0 and "iphone" not in str(d.get("name", "")).lower():
                    prefer = i
                    break
        if prefer is not None:
            sd.default.device = (prefer, sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) else None)
    except Exception:
        pass

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=chunk_size,
        latency="low",
    ) as stream:
        for _ in range(max_chunks):
            if _listen_abort.is_set():
                break
            chunk, overflowed = stream.read(chunk_size)
            if overflowed:
                pass
            frames.append(chunk.copy())
            energy = float(np.sqrt(np.mean(chunk ** 2)))
            if energy > SILENCE_DB:
                started = True
                silent_n = 0
                idle_n = 0
            elif started:
                silent_n += 1
                if silent_n >= silence_limit:
                    break
            else:
                idle_n += 1
                if idle_n >= idle_limit:
                    break  # never heard speech — don't hang

    if not frames:
        return np.zeros((1, CHANNELS), dtype="float32")
    return np.concatenate(frames, axis=0)


def record_until_silence() -> np.ndarray:
    """
    Record from mic with hard wall-clock timeout so HUD never sticks on LISTENING.
    """
    _listen_abort.clear()
    box: dict = {"audio": None, "err": None}
    done = threading.Event()

    def worker():
        try:
            box["audio"] = _record_inner()
        except Exception as e:
            box["err"] = e
        finally:
            done.set()

    t = threading.Thread(target=worker, daemon=True, name="dinesh-mic")
    t.start()
    if not done.wait(LISTEN_HARD_TIMEOUT):
        abort_listen()
        done.wait(2.0)
        raise TimeoutError(
            f"Microphone timed out after {LISTEN_HARD_TIMEOUT}s — "
            "check Mic permission for Terminal, or type instead."
        )
    if box["err"]:
        raise box["err"]
    return box["audio"] if box["audio"] is not None else np.zeros((1, CHANNELS), dtype="float32")


def transcribe(audio: np.ndarray, model=None) -> str:
    m = model or get_whisper_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        sf.write(tmp, audio, SAMPLE_RATE)
        result = m.transcribe(tmp, language="en", fp16=False, condition_on_previous_text=False)
        return result["text"].strip()
    finally:
        os.unlink(tmp)


def _clean_speech(text: str) -> str:
    clean = text.replace("*", "").replace("#", "").replace("`", "")
    clean = clean.replace('"', "'")
    # Keep spoken lines short for cinematic feel
    return clean.strip()


async def _edge_save(text: str, out_path: Path):
    import edge_tts
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await communicate.save(str(out_path))


def _speak_neural(text: str, wait: bool) -> bool:
    """Neural British TTS via edge-tts → afplay. Returns False on failure/timeout."""
    global _speak_proc
    if not _has_edge_tts():
        return False
    try:
        tmp = Path(tempfile.mkstemp(suffix=".mp3")[1])
        # Network TTS must not block the HUD forever
        asyncio.run(asyncio.wait_for(_edge_save(text, tmp), timeout=12.0))
        if not tmp.exists() or tmp.stat().st_size < 32:
            return False
        if _speak_proc and _speak_proc.poll() is None:
            _speak_proc.terminate()
        _speak_proc = subprocess.Popen(
            ["afplay", str(tmp)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if wait:
            try:
                _speak_proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                _speak_proc.terminate()
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            threading.Thread(
                target=lambda: (_speak_proc.wait(), tmp.unlink(missing_ok=True)),
                daemon=True,
            ).start()
        return True
    except Exception:
        return False


def _speak_system(text: str, voice: str, wait: bool):
    global _speak_proc
    if _speak_proc and _speak_proc.poll() is None:
        _speak_proc.terminate()
    # strip neural label if present
    v = voice.split("·")[0].strip() or "Daniel"
    if v not in PREFERRED_VOICES and v not in ("Alex", "Daniel", "Oliver", "Samantha"):
        v = "Daniel"
    _speak_proc = subprocess.Popen(
        ["say", "-v", v, "-r", str(SPEECH_RATE), text]
    )
    if wait:
        _speak_proc.wait()


def speak(text: str, voice: str = "", wait: bool = False):
    """Prefer neural British voice; fall back to macOS say."""
    clean = _clean_speech(text)
    if not clean:
        return
    if _speak_neural(clean, wait):
        return
    _speak_system(clean, voice or "Daniel", wait)


# Whisper rarely spells the name correctly — accept close phonetic matches
WAKE_WORDS = (
    "dinesh", "dinash", "danesh", "denesh", "dhinesh",
    "danish", "denise", "dennis", "the nesh", "di nesh",
)


def wake_match(text: str) -> str | None:
    """Return the text after the wake word, or None if not heard."""
    low = (text or "").lower()
    for w in WAKE_WORDS:
        if w in low:
            return low.split(w, 1)[-1].strip(" ,.?!")
    return None


# Backwards-compatible alias
_wake_match = wake_match


def listen_for_wake_word(voice: str) -> str:
    model = get_whisper_model()
    chunk_secs = 2
    chunk_size = int(SAMPLE_RATE * chunk_secs)
    print(f"  👂  Listening for 'Hey Dinesh'... (also accepts: {', '.join(WAKE_WORDS[1:5])})")

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32") as stream:
        while True:
            if _listen_abort.is_set():
                return ""
            chunk, _ = stream.read(chunk_size)
            energy = float(np.sqrt(np.mean(chunk ** 2)))
            if energy < 0.003:
                continue
            text = transcribe(chunk, model).lower()
            if not text:
                continue
            command = wake_match(text)
            if command is None:
                continue
            if len(command) > 3:
                return command
            speak("Yes, sir?", voice)
            return transcribe(record_until_silence(), model)
