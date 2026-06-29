"""ac/speech.py — Thread-safe text-to-speech using local engine initialization."""

from __future__ import annotations

import threading
import pyttsx3

_lock = threading.Lock()


def speak(text: str) -> None:
    """Speak the given text aloud. Blocks until speech is finished."""
    if not text.strip():
        return

    with _lock:
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print(f"[speech] Error: {exc}")


def shutdown() -> None:
    """Stop the TTS engine cleanly (no-op with local engine initialization)."""
    pass


