"""ac/listener.py — Microphone listener with wake-word detection."""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

import speech_recognition as sr

logger = logging.getLogger(__name__)

WAKE_WORDS = ["hey ac", "hey a c", "hey, ac", "hey,ac"]


class Listener:
    def __init__(
        self,
        on_network_error: Callable[[], None] | None = None,
        on_mic_error: Callable[[], None] | None = None,
    ) -> None:
        self._recognizer = sr.Recognizer()
        self._recognizer.pause_threshold = 1.2
        self._recognizer.dynamic_energy_threshold = True
        self._ambient_adjusted = False
        self._on_network_error = on_network_error or (lambda: None)
        self._on_mic_error = on_mic_error or (lambda: None)

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def contains_wake_word(text: str) -> bool:
        """Return True if *text* contains any wake-word variant."""
        t = text.lower().strip()
        for ww in WAKE_WORDS:
            if ww in t:
                return True
        # Fuzzy: "hey" followed by "ac" within 2 tokens
        tokens = re.split(r"\s+", t)
        for i, tok in enumerate(tokens):
            if tok in ("hey", "hay", "hi") and i + 1 < len(tokens):
                nxt = tokens[i + 1].replace(",", "").replace(".", "")
                if nxt in ("ac", "a.c", "a-c"):
                    return True
        return False

    @staticmethod
    def extract_command_from_wake(text: str) -> str:
        """Strip the wake word prefix and return the remainder."""
        t = text.lower().strip()
        for ww in WAKE_WORDS:
            if ww in t:
                idx = t.index(ww) + len(ww)
                return t[idx:].lstrip(", ").strip()
        # Fuzzy strip
        tokens = re.split(r"\s+", t)
        for i, tok in enumerate(tokens):
            if tok in ("hey", "hay", "hi") and i + 1 < len(tokens):
                nxt = tokens[i + 1].replace(",", "")
                if nxt in ("ac", "a.c", "a-c"):
                    return " ".join(tokens[i + 2:]).strip()
        return t

    # ── Listening helpers ─────────────────────────────────────────────────────

    def _get_mic(self) -> sr.Microphone | None:
        try:
            return sr.Microphone()
        except OSError:
            self._on_mic_error()
            return None

    def _transcribe(self, audio: sr.AudioData) -> str | None:
        try:
            return self._recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            self._on_network_error()
            return None

    # ── Public interface ──────────────────────────────────────────────────────

    def wait_for_wake_word(self) -> tuple[str, Optional[str]]:
        """
        Block until the wake word is detected.
        Returns (full_transcript, inline_command_or_None).
        """
        mic = self._get_mic()
        if mic is None:
            import time
            time.sleep(2)
            return "", None

        while True:
            try:
                with mic as source:
                    if not self._ambient_adjusted:
                        logger.info("Adjusting for ambient noise...")
                        self._recognizer.adjust_for_ambient_noise(source, duration=1.0)
                        self._ambient_adjusted = True
                    audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=8)
            except sr.WaitTimeoutError:
                continue
            except OSError:
                self._on_mic_error()
                import time
                time.sleep(2)
                continue

            text = self._transcribe(audio)
            if text and self.contains_wake_word(text):
                logger.debug("Wake word detected in: %s", text)
                inline = self.extract_command_from_wake(text) or None
                return text, inline

    def capture_command(
        self,
        inline_command: str | None = None,
        timeout: int = 15,
    ) -> str | None:
        """
        Capture and return one spoken command (or return *inline_command* immediately).
        Returns None if nothing is heard within *timeout* seconds.
        """
        if inline_command:
            return inline_command

        mic = self._get_mic()
        if mic is None:
            return None

        try:
            with mic as source:
                if not self._ambient_adjusted:
                    logger.info("Adjusting for ambient noise...")
                    self._recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    self._ambient_adjusted = True
                try:
                    audio = self._recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=None,
                    )
                except sr.WaitTimeoutError:
                    return None
        except OSError:
            self._on_mic_error()
            return None

        return self._transcribe(audio)
