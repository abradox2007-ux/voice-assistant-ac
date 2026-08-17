"""jarvis/router.py — Route a recognised command string to the right handler."""

from __future__ import annotations

import logging
import os
import re

from jarvis.handlers import apps, diary, files, info, urls, ai

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Here are some things you can say: "
    "Open Google, Open YouTube, Open Notepad, "
    "Open notes, Create file todos, "
    "Diary I had a great day, Read diary, "
    "What time is it, What's the date, What's the weather."
)


def translate_tamil_to_english(cmd: str) -> str:
    """Translate common Tamil command patterns to English equivalents."""
    # Check if the command has any Tamil Unicode characters (range U+0B80 to U+0BFF)
    if not any('\u0b80' <= char <= '\u0bff' for char in cmd):
        return cmd

    t = cmd.strip().lower()

    # Transliteration of common application/website names and search queries
    tamil_to_eng_nouns = {
        "கூகுள்": "google",
        "யூடியூப்": "youtube",
        "யூடியுப்": "youtube",
        "ஃபேஸ்புக்": "facebook",
        "இன்ஸ்டாகிராம்": "instagram",
        "சாட்ஜிபிடி": "chatgpt",
        "விக்கிபீடியா": "wikipedia",
        "யாகூ": "yahoo",
        "அமேசான்": "amazon",
        "வாட்ஸ்அப்": "whatsapp",
        "வாட்ஸ் அப்": "whatsapp",
        "நெட்பிளிக்ஸ்": "netflix",
        "ட்விட்டர்": "twitter",
        "லிங்க்டின்": "linkedin",
        "கிட்ஹப்": "github",
        "நோட்பேட்": "notepad",
        "கால்குலேட்டர்": "calculator",
        "பெயிண்ட்": "paint",
        "ரோவன்": "rovan",
    }

    for tam, eng in tamil_to_eng_nouns.items():
        t = t.replace(tam, eng)

    # 1. Help / Info commands
    if any(w in t for w in ("உதவி", "வழிகாட்டி", "கட்டளைகள்", "வழிமுறை")):
        return "help"

    # 2. Time / Date / Weather
    if any(w in t for w in ("நேரம்", "மணி என்ன", "மணி என்னா", "நேரம் என்ன")):
        return "time"
    if any(w in t for w in ("தேதி", "நாள் என்ன", "தேதி என்ன")):
        return "date"
    if any(w in t for w in ("வானிலை", "மழை", "வெயில்")):
        return "weather"

    # 3. Diary manual
    if any(w in t for w in ("டைரி மேனுவல்", "மேனுவல் டைரி")):
        return "diary manual"

    # 4. Read/Open Diary
    if any(w in t for w in ("டைரி படி", "டைரியை படி", "டைரி காட்டு", "டைரியை காட்டு", "டைரி திற", "டைரியை திற")):
        return "read diary"

    # 5. Write to Diary
    diary_write_match = re.match(r"^(டைரி|நாட்குறிப்பு)\s*(.*)$", t)
    if diary_write_match:
        content = diary_write_match.group(2).strip()
        return f"diary {content}"

    # 6. Create file
    create_match = re.match(r"^(.*)\s+(கோப்பு உருவாக்கு|ஃபைல் உருவாக்கு|உருவாக்கு)$", t)
    if create_match:
        filename = create_match.group(1).strip()
        return f"create file {filename}"
    if t.startswith("ஃபைல் உருவாக்கு") or t.startswith("கோப்பை உருவாக்கு"):
        filename = t.replace("ஃபைல் உருவாக்கு", "").replace("கோப்பை உருவாக்கு", "").strip()
        return f"create file {filename}"

    # 7. Open target
    open_match = re.match(r"^(.*)\s+(திற|திறக்கவும்)$", t)
    if open_match:
        target = open_match.group(1).strip()
        return f"open {target}"
    if t.startswith("ஓபன்"):
        target = t.replace("ஓபன்", "").strip()
        return f"open {target}"

    # 8. Play song
    play_match = re.match(r"^(.*)\s+(ப்ளே பண்ணு|போடு|ஒலிபரப்பு|ப்ளே செய்|ப்ளே)$", t)
    if play_match:
        song = play_match.group(1).strip()
        song = song.replace("பாடல்", "").strip()
        return f"play {song}"
    if t.startswith("ப்ளே"):
        song = t.replace("ப்ளே", "").strip()
        song = song.replace("பாடல்", "").strip()
        return f"play {song}"

    # 9. Search query
    search_match = re.match(r"^(.*)\s+(தேடு|தேடவும்|சர்ச் பண்ணு|தேடி காட்டு)$", t)
    if search_match:
        query = search_match.group(1).strip()
        if query.endswith("பற்றி"):
            query = query[:-5].strip()
        return f"search {query}"
    if t.startswith("சர்ச்") or t.startswith("தேடு"):
        query = t.replace("சர்ச்", "").replace("தேடு", "").strip()
        return f"search {query}"

    return t


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
        translated_command = translate_tamil_to_english(command)
        cmd = translated_command.strip().lower()
        cmd = cmd.replace("dairy", "diary")
        logger.debug("Routing command: %s (original: %s)", cmd, command)

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
            entry_text = re.sub(r"^diary\b\s*[,.:|-]?\s*", "", translated_command, flags=re.IGNORECASE).strip()
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
            name = translated_command[len("create file "):].strip()
            return files.create_file(name)

        # ── Search ───────────────────────────────────────────────────────────
        if cmd == "search" or cmd.startswith("search "):
            query = translated_command[len("search "):].strip()
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
            song = translated_command[len("play "):].strip()
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
            target = translated_command[len("open "):].strip()
            target_lower = target.lower()

            # URL alias?
            if target_lower in self._url_aliases or any(
                target_lower == a or target_lower in a.split() or a in target_lower.split() for a in self._url_aliases
            ):
                return urls.open_url(target, self._url_aliases)

            # App alias?
            if target_lower in self._app_aliases or any(
                target_lower == a or target_lower in a.split() or a in target_lower.split() for a in self._app_aliases
            ):
                return apps.open_app(target, self._app_aliases)

            # File fallback
            response = files.open_file(target, self._search_paths)
            if "No file matching" not in response:
                return response

            # Last resort: try as URL
            return urls.open_url(target, self._url_aliases)

        # ── Unknown / AI Fallback ────────────────────────────────────────────
        if self._config.get("gemini_api_key") or self._config.get("openai_api_key") or self._config.get("ollama_url") or os.environ.get("GEMINI_API_KEY"):
            response = ai.generate_voice_response(command, self._config)
            return self.handle_llm_json_response(response)

        if any(w in cmd for w in ("why", "what", "how", "who", "where", "when", "tell me")):
            return "To ask general questions, please configure your gemini_api_key in config.json."

        return f"Sorry, I didn't understand '{command}'. Say 'help' for a list of commands."

    def handle_llm_json_response(self, response_str: str) -> str:
        """Parse LLM JSON response and execute any structured tool actions."""
        try:
            from jarvis.handlers.ai import clean_and_parse_json
            parsed = clean_and_parse_json(response_str)
        except Exception as e:
            logger.warning("Failed to parse LLM response as JSON: %s (Response: %s)", e, response_str)
            return response_str

        if "reply" in parsed:
            return parsed["reply"]

        action = parsed.get("action")
        if not action:
            return response_str

        if action == "multi":
            results = []
            commands = parsed.get("commands", [])
            for cmd in commands:
                res = self.execute_single_action(cmd)
                results.append(res)
            return "Executed actions: " + " and ".join(results)
        else:
            return self.execute_single_action(parsed)

    def execute_single_action(self, action_dict: dict) -> str:
        """Dispatch a single structured JSON command to its Python handler."""
        action = action_dict.get("action")
        if not action:
            return "No action specified."

        # 1. Smart home control
        if action == "control_device":
            device = action_dict.get("device")
            state = action_dict.get("state")
            temp = action_dict.get("temperature")
            
            from server import update_device
            updates = {}
            if state:
                updates["state"] = state
            if temp is not None:
                updates["temperature"] = temp
                
            if device and updates:
                success = update_device(device, updates)
                if success:
                    status_str = f"turned {state}" if state else ""
                    if temp is not None:
                        status_str += f" and set to {temp} degrees"
                    return f"Smart {device} {status_str.strip()} successfully."
                return f"Failed to update smart {device}."
            return "Missing device or state parameters."

        # 2. Create file
        elif action == "create_file":
            from jarvis.handlers import files
            name = action_dict.get("name", "untitled")
            return files.create_file(name)

        # 3. Open application
        elif action == "open_app":
            from jarvis.handlers import apps
            name = action_dict.get("name")
            if name:
                return apps.open_app(name, self._app_aliases)
            return "No application name provided."

        # 4. Play song
        elif action == "play_song":
            song = action_dict.get("name")
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
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}"
                webbrowser.open(url)
                return f"Playing '{song}' on YouTube."
            return "No song name provided."

        # 5. Search Google
        elif action == "search_google":
            query = action_dict.get("query")
            if query:
                import urllib.parse
                import webbrowser
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)
                return f"Searching for '{query}' on Google."
            return "No query provided."

        # 6. Read diary
        elif action == "read_diary":
            from jarvis.handlers import diary
            return diary.open_diary()

        # 7. Write/Append to diary
        elif action == "append_diary":
            from jarvis.handlers import diary
            text = action_dict.get("text", "")
            return diary.append_diary_entry(text)

        # 8. Time/Date/Weather info fallback
        elif action == "tell_time":
            from jarvis.handlers import info
            return info.tell_time()
        elif action == "tell_date":
            from jarvis.handlers import info
            return info.tell_date()
        elif action == "tell_weather":
            from jarvis.handlers import info
            return info.tell_weather(self._weather_city, self._weather_country)

        return f"Action '{action}' is not supported yet."
