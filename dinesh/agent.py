"""Multi-step agent — hybrid intent + LLM + long-term memory learning."""

import json
import logging
import re
import time

import ollama

from config import LLM_MODEL, MAX_AGENT_STEPS, MAX_HISTORY, OLLAMA_OPTIONS, PROFILE, SYSTEM_PROMPT
from intent import handle_intent
from models import is_weak_tool_model
from nlu import normalize
from tools import TOOL_MAP, active_tools_schema
from ui import print_tool_step
from memory.store import init_db, log_turn, memory_block
from memory.learn import maybe_learn_from_user, summarize_episode

logger = logging.getLogger("Dinesh")

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _build_system() -> str:
    return SYSTEM_PROMPT + "\n\n" + memory_block()


def _parse_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _iter_json_objects(text: str):
    depth = 0
    start = None
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        yield json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    start = None


def extract_text_tool_calls(content: str) -> list[tuple[str, dict]]:
    if not content or "{" not in content:
        return []
    candidates = []
    for block in _JSON_BLOCK.findall(content):
        candidates.extend(_iter_json_objects(block))
    candidates.extend(_iter_json_objects(content))

    calls, seen = [], set()
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        fn = obj.get("function") if isinstance(obj.get("function"), dict) else obj
        name = fn.get("name") or fn.get("tool") or fn.get("tool_name")
        if not isinstance(name, str) or name not in TOOL_MAP:
            continue
        args = _parse_args(fn.get("parameters") or fn.get("arguments") or fn.get("args") or {})
        key = (name, json.dumps(args, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        calls.append((name, args))
    return calls


def _looks_like_raw_json(text: str) -> bool:
    stripped = (text or "").strip().strip("`").strip()
    return stripped.startswith("{") and stripped.endswith("}")


# Replies that mean the model gave up instead of acting.
_GIVE_UP = (
    "i didn't understand", "i did not understand", "i don't understand",
    "i do not understand", "not sure what you mean", "unclear what you",
    "could you rephrase", "please rephrase", "can you clarify",
    "i'm not sure what", "i am not sure what", "didn't quite catch",
    "could you be more specific", "i don't know what you mean",
)


def _is_give_up(reply: str) -> bool:
    low = (reply or "").lower()
    return any(phrase in low for phrase in _GIVE_UP)


# Split on sentence-ending punctuation followed by whitespace, so decimals
# like "71.3 GB" and abbreviations stay intact.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _trim_sentences(reply: str, limit: int = 3) -> str:
    """Keep replies short for speech without mangling numbers."""
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(reply.strip()) if s.strip()]
    if len(parts) <= limit:
        return reply.strip()
    return " ".join(parts[:limit])


def _execute_tool(name: str, args: dict) -> str:
    if name not in TOOL_MAP:
        return f"Unknown tool: {name}"
    fn = TOOL_MAP[name]
    if name == "hotkey" and "keys" in args:
        keys = args.pop("keys")
        if isinstance(keys, list):
            return str(fn(*keys))
    try:
        return str(fn(**args))
    except TypeError as e:
        return f"Tool '{name}' argument error: {e}"
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return f"Tool '{name}' failed: {e}"


def _trim_history(history: list) -> list:
    if len(history) <= MAX_HISTORY:
        return history
    return [history[0]] + history[1:][-(MAX_HISTORY - 1):]


class DineshAgent:
    def __init__(self):
        init_db()
        self.last_assistant = ""
        self.weak = is_weak_tool_model(PROFILE.llm)
        self.schema = active_tools_schema(self.weak)
        self.history = [{"role": "system", "content": _build_system()}]

    def refresh_memory_prompt(self):
        self.history[0] = {"role": "system", "content": _build_system()}

    def _llm_turn(self, on_token=None):
        """
        One Ollama round-trip. Streams tokens when `on_token` is set so the HUD
        can paint the reply live. Tool-call JSON is still collected from the
        finished stream.
        """
        content = ""
        tool_calls = []
        stream = ollama.chat(
            model=LLM_MODEL,
            messages=self.history,
            tools=self.schema,
            options=OLLAMA_OPTIONS,
            stream=True,
        )
        for chunk in stream:
            msg = chunk.get("message") or {}
            delta = msg.get("content") or ""
            if delta:
                content += delta
                if on_token:
                    on_token(delta)
            if msg.get("tool_calls"):
                tool_calls = msg["tool_calls"]
        return content, tool_calls, {"role": "assistant", "content": content, "tool_calls": tool_calls}

    def chat(self, user_message: str, on_token=None) -> str:
        # Learn from corrections / "remember that…"
        notes = maybe_learn_from_user(user_message, self.last_assistant)
        if notes:
            self.refresh_memory_prompt()
            for n in notes:
                print(f"  🧠  {n}")

        log_turn("user", user_message)

        # Repair typos before anything else sees the text.
        cleaned = normalize(user_message)
        if cleaned.lower() != user_message.lower().strip():
            print(f"  ✎  read as: {cleaned}")
        user_message = cleaned or user_message

        # Intent router for simple one-shots
        direct = handle_intent(user_message)
        if direct is not None:
            print("  ⚡ [intent] direct action (no LLM)")
            print("  ✓  Done in 0.1s · intent")
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": direct})
            self.last_assistant = direct
            log_turn("assistant", direct, {"via": "intent"})
            summarize_episode(user_message, direct)
            return direct

        self.history.append({"role": "user", "content": user_message})
        self.history = _trim_history(self.history)
        steps = 0
        executed = 0
        nudged = False
        last_results: list[str] = []
        t0 = time.time()

        while steps < MAX_AGENT_STEPS:
            steps += 1
            try:
                content, tool_calls, msg = self._llm_turn(on_token=on_token if executed == 0 else None)
            except Exception as e:
                logger.error("LLM error: %s", e)
                return f"Sir, communication error: {e}"

            calls: list[tuple[str, dict]] = [
                (tc["function"]["name"], _parse_args(tc["function"].get("arguments", {})))
                for tc in tool_calls
            ]

            recovered = False
            if not calls:
                calls = extract_text_tool_calls(content)
                recovered = bool(calls)

            if not calls:
                if _looks_like_raw_json(content):
                    self.history.append({
                        "role": "user",
                        "content": (
                            "That JSON did not execute. Call a real tool, or reply in plain English."
                        ),
                    })
                    continue
                reply = content.strip() or "Task completed, sir."
                fake = (
                    "folder created", "file written", "html content fetched",
                    "fetching the content", "web search results", "opening the first link",
                    "creating folder",
                )
                if executed == 0 and any(f in reply.lower() for f in fake):
                    self.history.append({
                        "role": "user",
                        "content": (
                            "You claimed actions without calling tools. "
                            "Call the required tools now."
                        ),
                    })
                    continue

                # One retry if the model stalled instead of committing to an action.
                if _is_give_up(reply) and not nudged:
                    nudged = True
                    self.history.append({
                        "role": "user",
                        "content": (
                            "Do not ask me to rephrase. The message may contain typos — "
                            "infer the most likely intent, act on it with a tool if one "
                            "applies, and state your assumption in one short clause."
                        ),
                    })
                    continue

                reply = _trim_sentences(reply, limit=3)
                self.history.append({"role": "assistant", "content": reply})
                self.last_assistant = reply
                log_turn("assistant", reply, {"tools": executed})
                summarize_episode(user_message, reply)
                print(f"  ✓  Done in {time.time() - t0:.1f}s · {executed} tool calls")
                return reply

            self.history.append(msg if not recovered else {"role": "assistant", "content": content})

            for name, args in calls:
                executed += 1
                tag = f"{name} (recovered)" if recovered else name
                print_tool_step(executed, tag, json.dumps(args, ensure_ascii=False))
                result = _execute_tool(name, args)
                last_results.append(result)
                self.history.append({"role": "tool", "content": result[:6000]})

            self.history = _trim_history(self.history)

        summary = (
            "Sir, I reached the step limit. Partial progress: "
            f"{'; '.join(r[:80] for r in last_results[-2:])}"
        )
        self.history.append({"role": "assistant", "content": summary})
        self.last_assistant = summary
        log_turn("assistant", summary, {"tools": executed, "truncated": True})
        return summary

    def clear_memory(self):
        """Clear short-term chat only — long-term memory stays."""
        self.history = [{"role": "system", "content": _build_system()}]
        self.last_assistant = ""
