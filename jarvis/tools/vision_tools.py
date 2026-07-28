"""Screen vision — optimized with image compression + caching."""

import time
from datetime import datetime
from pathlib import Path

import ollama
import pyautogui
from PIL import Image

from config import SCREEN_CACHE_SECS, VISION_MAX_WIDTH, VISION_MODEL, ensure_screenshot_dir

_cache: dict = {"path": None, "ts": 0.0}


def _compress_image(src: Path) -> Path:
    """Resize screenshot for faster vision inference on 16GB Mac."""
    out = src.with_suffix(".opt.jpg")
    with Image.open(src) as img:
        w, h = img.size
        if w > VISION_MAX_WIDTH:
            ratio = VISION_MAX_WIDTH / w
            img = img.resize((VISION_MAX_WIDTH, int(h * ratio)), Image.Resampling.LANCZOS)
        img.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
    return out


def _capture_for_vision() -> Path:
    now = time.time()
    if _cache["path"] and (now - _cache["ts"]) < SCREEN_CACHE_SECS:
        return _cache["path"]

    raw = ensure_screenshot_dir() / f"vision_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    pyautogui.screenshot().save(str(raw))
    opt = _compress_image(raw)
    _cache["path"] = opt
    _cache["ts"] = now
    return opt


def _vision_chat(prompt: str, image_path: Path) -> str:
    response = ollama.chat(
        model=VISION_MODEL,
        messages=[{"role": "user", "content": prompt, "images": [str(image_path)]}],
        options={"num_predict": 400, "temperature": 0.2},
    )
    return response["message"]["content"]


def see_screen(
    question: str = "Describe this Mac screen: apps open, buttons, text, layout. Note positions (top/bottom/left/right/center).",
) -> str:
    path = _capture_for_vision()
    try:
        analysis = _vision_chat(question, path)
        return f"[Screen captured]\n{analysis}"
    except Exception as e:
        return (
            f"Vision failed: {e}. Install: ollama pull {VISION_MODEL} "
            f"(moondream recommended for 16GB Macs). Screenshot: {path}"
        )


def analyze_image(image_path: str, question: str = "Describe this image.") -> str:
    full = Path(image_path).expanduser()
    opt = _compress_image(full) if full.exists() else full
    try:
        return _vision_chat(question, opt)
    except Exception as e:
        return f"Could not analyze image: {e}"


def find_element_on_screen(description: str) -> str:
    path = _capture_for_vision()
    w, h = pyautogui.size()
    prompt = (
        f"Screen is {w}x{h}. Find: {description}. "
        'Reply ONLY JSON: {"x": int, "y": int, "confidence": "high|medium|low"}'
    )
    try:
        return _vision_chat(prompt, path)
    except Exception as e:
        return f"Element search failed: {e}"
