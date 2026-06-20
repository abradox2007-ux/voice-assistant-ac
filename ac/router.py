"""ac/router.py — Route a recognised command string to the right handler."""

from __future__ import annotations

import logging
import re

from ac.handlers import apps, diary, files, info, urls

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Here are some things you can say: "
    "Open Google, Open YouTube, Open Notepad, "
    "Open notes, Create file todos, "
    "Diary I had a great day, Read diary, "
    "What time is it, What's the date, What's the weather."
)


class CommandRouter:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._url_aliases: dict[str, str] = config.get("url_aliases", {})
        self._app_aliases: dict[str, str] = config.get("app_aliases", {})
        self._search_paths: list[str] = config.get("search_paths", [])
        self._weather_city: str = config.get("weather_city", "Chennai")
        self._weather_country: str = config.get("weather_country", "IN")

    def route(self, command: str) -> str:
        """Dispatch *command* to the appropriate handler and return a response."""
        cmd = command.strip().lower()
        logger.debug("Routing command: %s", cmd)

        # ── Safety: no delete ────────────────────────────────────────────────
        if any(w in cmd for w in ("delete", "remove", "erase", "unlink")):
            return "Delete commands are not supported for safety reasons."

        # ── Help ─────────────────────────────────────────────────────────────
        if cmd in ("help", "what can you do", "commands"):
            return HELP_TEXT

        # ── View/Read/Watch Diary ────────────────────────────────────────────
        if any(p in cmd for p in (
            "read diary", "show diary", "view diary", "open diary", "watch diary",
            "read the diary", "show the diary", "view the diary", "open the diary", "watch the diary",
            "watch the content of the diary", "show the content of the diary", "read the content of the diary"
        )):
            return diary.open_diary()

        # ── Diary Manual Panel ───────────────────────────────────────────────
        if cmd in ("diary manual", "manual diary"):
            from server import set_status
            set_status("diary_manual", "Opening manual diary panel...")
            return "Opening manual diary panel."

        # ── Diary (must come before "open" check) ────────────────────────────
        diary_match = re.match(r"^diary\b\s*[,.:|-]?\s*(.*)$", cmd)
        if diary_match:
            entry_text = command[len(command) - len(diary_match.group(1)):].strip()
            return diary.append_diary_entry(entry_text)

        # ── Time ─────────────────────────────────────────────────────────────
        if any(p in cmd for p in ("what time", "current time", "tell me the time")):
            return info.tell_time()

        # ── Date ─────────────────────────────────────────────────────────────
        if any(p in cmd for p in ("what's the date", "what is the date", "today's date", "current date")):
            return info.tell_date()

        # ── Weather ──────────────────────────────────────────────────────────
        if "weather" in cmd:
            return info.tell_weather(self._weather_city, self._weather_country)

        # ── Create file ──────────────────────────────────────────────────────
        if cmd.startswith("create file "):
            name = command[len("create file "):].strip()
            return files.create_file(name)

        # ── Open ─────────────────────────────────────────────────────────────
        if cmd.startswith("open "):
            target = command[len("open "):].strip()
            target_lower = target.lower()

            # URL alias?
            if target_lower in self._url_aliases or any(
                target_lower in a or a in target_lower for a in self._url_aliases
            ):
                return urls.open_url(target, self._url_aliases)

            # App alias?
            if target_lower in self._app_aliases or any(
                target_lower in a or a in target_lower for a in self._app_aliases
            ):
                return apps.open_app(target, self._app_aliases)

            # File fallback
            response = files.open_file(target, self._search_paths)
            if "No file matching" not in response:
                return response

            # Last resort: try as URL
            return urls.open_url(target, self._url_aliases)

        # ── Unknown ──────────────────────────────────────────────────────────
        return f"Sorry, I didn't understand '{command}'. Say 'help' for a list of commands."
