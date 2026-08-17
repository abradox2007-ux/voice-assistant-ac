"""jarvis/utils.py — Shared utilities: config, logging, file helpers."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
LOG_DIR = Path(__file__).parent.parent / "logs"


def load_config() -> dict:
    """Load config.json and expand ~ in search_paths."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["search_paths"] = [
        str(Path(p).expanduser()) for p in cfg.get("search_paths", [])
    ]
    return cfg


def setup_logging() -> logging.Logger:
    """Set up file + console logging and return the root logger."""
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "jarvis.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("jarvis")


def sanitize_filename(name: str) -> str:
    """Remove illegal filename characters and strip whitespace."""
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name


def find_best_file_match(
    query: str, search_paths: list[Path | str]
) -> tuple[Optional[Path], list[Path]]:
    """
    Search *search_paths* for files whose stem contains *query* (case-insensitive).
    Returns (best_match, all_matches).  best_match is None if nothing found.
    """
    query_lower = query.lower()
    all_matches: list[Path] = []

    for root in search_paths:
        root_path = Path(root)
        if not root_path.exists():
            continue
        try:
            for current_root, dirs, files in os.walk(str(root_path)):
                rel_depth = len(Path(current_root).relative_to(root_path).parts)
                if rel_depth >= 3:
                    dirs.clear()
                for fname in files:
                    fpath = Path(current_root) / fname
                    if query_lower in fpath.stem.lower():
                        all_matches.append(fpath)
        except Exception:
            continue

    if not all_matches:
        return None, []

    # Exact stem match wins; otherwise first found
    for p in all_matches:
        if p.stem.lower() == query_lower:
            return p, all_matches

    return all_matches[0], all_matches
