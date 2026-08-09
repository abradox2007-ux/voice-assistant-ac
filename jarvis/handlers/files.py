"""jarvis/handlers/files.py — Open existing files and create new text files."""

from __future__ import annotations

import os
from pathlib import Path

from jarvis.utils import find_best_file_match, sanitize_filename

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def open_file(query: str, search_paths: list[str]) -> str:
    """Find and open the best-matching file. Returns spoken response."""
    paths = [Path(p) for p in search_paths]
    best, matches = find_best_file_match(query, paths)

    if best is None:
        return f"No file matching '{query}' found in your search paths."

    try:
        os.startfile(str(best))
        return f"Opening {best.name}."
    except Exception as exc:
        return f"Found {best.name} but couldn't open it: {exc}"


def create_file(name: str) -> str:
    """Create a new .txt file in the data/ directory. Returns spoken response."""
    safe_name = sanitize_filename(name)
    if not safe_name:
        return "That filename isn't valid. Please try a different name."

    DATA_DIR.mkdir(exist_ok=True)
    file_path = DATA_DIR / f"{safe_name}.txt"

    if file_path.exists():
        return f"'{safe_name}.txt' already exists in your data folder."

    file_path.write_text("", encoding="utf-8")
    return f"Created '{safe_name}.txt' in your data folder."
