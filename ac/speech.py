"""ac/speech.py — Text-to-speech using pyttsx3."""

from __future__ import annotations

import threading
import pyttsx3

_engine: pyttsx3.Engine | None = None
_lock = threading.Lock()


def _get_engine() -> pyttsx3.Engine:
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 170)
        _engine.setProperty("volume", 1.0)
    return _engine


def speak(text: str) -> None:
    """Speak the given text aloud."""
    with _lock:
        try:
            engine = _get_engine()
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print(f"[speech] Error: {exc}")


def shutdown() -> None:
    """Stop the TTS engine cleanly."""
    global _engine
    with _lock:
        if _engine is not None:
            try:
                _engine.stop()
            except Exception:
                pass
            _engine = None
