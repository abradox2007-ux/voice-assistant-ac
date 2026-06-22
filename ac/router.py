"""ac/router.py — Route a recognised command string to the right handler."""

from __future__ import annotations

import logging
import os
import re

from ac.handlers import apps, diary, files, info, urls, ai

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
        cmd = cmd.replace("dairy", "diary")
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

        # ── Weather ──────────────────────────────────────────────────────────
        if "weather" in cmd:
            return info.tell_weather(self._weather_city, self._weather_country)

        # ── Time ─────────────────────────────────────────────────────────────
        if any(p in cmd for p in ("time", "clock")):
            return info.tell_time()

        # ── Date ─────────────────────────────────────────────────────────────
        if any(p in cmd for p in ("date", "today")):
            return info.tell_date()

        # ── Create file ──────────────────────────────────────────────────────
        if cmd.startswith("create file "):
            name = command[len("create file "):].strip()
            return files.create_file(name)

        # ── Search ───────────────────────────────────────────────────────────
        if cmd == "search" or cmd.startswith("search "):
            query = command[len("search "):].strip()
            if query:
                import urllib.parse
                import webbrowser
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)
                return f"Searching for '{query}' on Google."
            else:
                return "What would you like me to search for?"

        # ── Play ─────────────────────────────────────────────────────────────
        if cmd == "play" or cmd.startswith("play "):
            song = command[len("play "):].strip()
            if song:
                import urllib.parse
                import webbrowser
                import requests

                try:
                    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    html = requests.get(search_url, headers=headers, timeout=5).text
                    video_ids = re.findall(r"watch\?v=(\S{11})", html)
                    if video_ids:
                        url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                        webbrowser.open(url)
                        return f"Playing '{song}' on YouTube."
                except Exception:
                    pass

                # Fallback to search results page if scraping fails
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}"
                webbrowser.open(url)
                return f"Playing '{song}' on YouTube."
            else:
                return "What song would you like me to play?"

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

        # ── Unknown / AI Fallback ────────────────────────────────────────────
        api_key = self._config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            return ai.generate_voice_response(command, api_key)

        if any(w in cmd for w in ("why", "what", "how", "who", "where", "when", "tell me")):
            return "To ask general questions, please configure your gemini_api_key in config.json."

        return f"Sorry, I didn't understand '{command}'. Say 'help' for a list of commands."
