"""ac/handlers/apps.py — Launch desktop applications."""

from __future__ import annotations

import subprocess


def open_app(name: str, app_aliases: dict[str, str]) -> str:
    """
    Launch an application by alias name.
    Returns a spoken response string.
    """
    key = name.strip().lower()
    exe = app_aliases.get(key)

    if exe is None:
        for alias, path in app_aliases.items():
            if key in alias or alias in key:
                exe = path
                name = alias
                break

    if exe is None:
        return f"I don't know the app '{name}'. Add it to config.json."

    try:
        subprocess.Popen(exe, shell=True)
        return f"Opening {name}."
    except Exception as exc:
        return f"Failed to open {name}: {exc}"
