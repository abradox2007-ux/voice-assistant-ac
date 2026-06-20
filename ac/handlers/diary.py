"""ac/handlers/diary.py — Append diary entries to data/Diary.txt."""

from __future__ import annotations

import time
from pathlib import Path

DIARY_PATH = Path(__file__).parent.parent.parent / "data" / "Diary.txt"


def append_diary_entry(text: str) -> str:
    """Append *text* with a timestamp to the diary file. Returns spoken response."""
    if not text.strip():
        return "What would you like to add to your diary?"

    DIARY_PATH.parent.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n[{timestamp}]\n{text.strip()}\n"

    with open(DIARY_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    return "Added to your diary."


def open_diary() -> str:
    """Open the diary file in the default text viewer. Returns spoken response."""
    import os
    if not DIARY_PATH.exists():
        DIARY_PATH.parent.mkdir(exist_ok=True)
        with open(DIARY_PATH, "w", encoding="utf-8") as f:
            f.write("=== My Voice Assistant Diary ===\n")
    try:
        os.startfile(str(DIARY_PATH))
        return "Opening your diary."
    except Exception as exc:
        return f"Couldn't open the diary file: {exc}"
