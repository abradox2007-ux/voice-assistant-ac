"""Automated tests for Jarvis command routing and handlers (no microphone)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.router import CommandRouter
from jarvis.utils import find_best_file_match, load_config, sanitize_filename


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()
        cls.router = CommandRouter(cls.config)

    def test_delete_rejected(self) -> None:
        result = self.router.route("delete file test")
        self.assertIn("not supported", result.lower())

    def test_diary_priority_over_open(self) -> None:
        with patch("jarvis.handlers.diary.append_diary_entry", return_value="Added to your diary.") as mock:
            result = self.router.route("diary open google was fun")
            mock.assert_called_once_with("open google was fun")
            self.assertEqual(result, "Added to your diary.")

    def test_diary_empty(self) -> None:
        with patch("jarvis.handlers.diary.append_diary_entry", return_value="What would you like to add to your diary?") as mock:
            result = self.router.route("diary")
            mock.assert_called_once_with("")
            self.assertEqual(result, "What would you like to add to your diary?")
            
            mock.reset_mock()
            result_spaces = self.router.route("diary   ")
            mock.assert_called_once_with("")
            self.assertEqual(result_spaces, "What would you like to add to your diary?")

    def test_diary_with_punctuation(self) -> None:
        with patch("jarvis.handlers.diary.append_diary_entry", return_value="Added to your diary.") as mock:
            result_comma = self.router.route("diary, I had a great day")
            mock.assert_called_once_with("I had a great day")
            self.assertEqual(result_comma, "Added to your diary.")

            mock.reset_mock()
            result_colon = self.router.route("diary: another entry")
            mock.assert_called_once_with("another entry")
            self.assertEqual(result_colon, "Added to your diary.")

            mock.reset_mock()
            result_period = self.router.route("diary. a third entry")
            mock.assert_called_once_with("a third entry")
            self.assertEqual(result_period, "Added to your diary.")

    def test_open_diary(self) -> None:
        with patch("jarvis.handlers.diary.open_diary", return_value="Opening your diary.") as mock:
            result_read = self.router.route("read diary")
            mock.assert_called_once()
            self.assertEqual(result_read, "Opening your diary.")

            mock.reset_mock()
            result_watch = self.router.route("watch the content of the diary")
            mock.assert_called_once()
            self.assertEqual(result_watch, "Opening your diary.")

    def test_diary_manual(self) -> None:
        with patch("server.set_status") as mock_status:
            result = self.router.route("diary manual")
            mock_status.assert_called_once_with("diary_manual", "Opening manual diary panel...")
            self.assertEqual(result, "Opening manual diary panel.")

            mock_status.reset_mock()
            result_homophone = self.router.route("Dairy manual")
            mock_status.assert_called_once_with("diary_manual", "Opening manual diary panel...")
            self.assertEqual(result_homophone, "Opening manual diary panel.")

    def test_time_query(self) -> None:
        result = self.router.route("what time is it")
        self.assertIn("time is", result.lower())
        result2 = self.router.route("what's the time now")
        self.assertIn("time is", result2.lower())

    def test_date_query(self) -> None:
        result = self.router.route("what's the date")
        self.assertIn("today is", result.lower())

    def test_weather_query(self) -> None:
        with patch("jarvis.handlers.info.tell_weather", return_value="The weather in Chennai is clear."):
            result = self.router.route("what's the weather")
            self.assertIn("weather", result.lower())
            result2 = self.router.route("what's the weather today")
            self.assertIn("weather", result2.lower())

    def test_create_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("jarvis.handlers.files.DATA_DIR", Path(tmp)):
                name = "unittest_create_file"
                path = Path(tmp) / f"{name}.txt"
                if path.exists():
                    path.unlink()
                result = self.router.route(f"create file {name}")
                self.assertIn("Created", result)
                self.assertTrue(path.exists())
                result2 = self.router.route(f"create file {name}")
                self.assertIn("already exists", result2.lower())

    def test_open_url_not_file(self) -> None:
        with patch("jarvis.handlers.urls.webbrowser.open") as mock_open:
            result = self.router.route("open google")
            mock_open.assert_called_once()
            self.assertIn("Opening google", result)

    def test_open_app_not_url(self) -> None:
        with patch("jarvis.handlers.apps.subprocess.Popen") as mock_popen:
            result = self.router.route("open notepad")
            mock_popen.assert_called_once()
            self.assertIn("Opening notepad", result)

    def test_open_file_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "notes.txt"
            test_file.write_text("hello", encoding="utf-8")
            config = dict(self.config)
            config["search_paths"] = [tmp]
            router = CommandRouter(config)
            with patch("jarvis.handlers.files.os.startfile") as mock_start:
                result = router.route("open notes")
                mock_start.assert_called_once()
                self.assertIn("Opening notes.txt", result)

    def test_unknown_command(self) -> None:
        with patch.dict(self.router._config, {"gemini_api_key": ""}):
            result = self.router.route("do something random xyz")
            self.assertIn("didn't understand", result.lower())

    def test_search_command(self) -> None:
        with patch("webbrowser.open") as mock_open:
            result = self.router.route("search quantum computing")

            mock_open.assert_called_once_with("https://www.google.com/search?q=quantum%20computing")
            self.assertIn("Searching for 'quantum computing' on Google", result)

        # Empty query
        result_empty = self.router.route("search ")
        self.assertEqual(result_empty, "What would you like me to search for?")

    def test_play_command(self) -> None:
        with patch("requests.get") as mock_get, patch("webbrowser.open") as mock_open:
            mock_get.return_value.text = 'href="/watch?v=dQw4w9WgXcQ"'
            result = self.router.route("play bohemian rhapsody")
            mock_open.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertIn("Playing 'bohemian rhapsody' on YouTube", result)

        # Empty query
        result_empty = self.router.route("play ")
        self.assertEqual(result_empty, "What song would you like me to play?")

    def test_ai_fallback_configured(self) -> None:
        custom_config = dict(self.config)
        custom_config["gemini_api_key"] = "test-api-key"
        custom_router = CommandRouter(custom_config)

        with patch("jarvis.router.ai.generate_voice_response", return_value='{"reply": "Mocked Gemini response."}') as mock_ai:
            result = custom_router.route("why is the sky blue")
            mock_ai.assert_called_once_with("why is the sky blue", custom_config)
            self.assertEqual(result, "Mocked Gemini response.")

    def test_smart_home_routing(self) -> None:
        custom_config = dict(self.config)
        custom_config["gemini_api_key"] = "test-api-key"
        custom_router = CommandRouter(custom_config)

        with patch("server.update_device", return_value=True) as mock_update:
            json_response = '{"action": "control_device", "device": "light", "state": "on"}'
            with patch("jarvis.router.ai.generate_voice_response", return_value=json_response):
                result = custom_router.route("turn on the light")
                mock_update.assert_called_once_with("light", {"state": "on"})
                self.assertIn("successfully", result.lower())


    def test_help_command(self) -> None:
        result = self.router.route("help")
        self.assertIn("open google", result.lower())

    def test_tamil_command_routing(self) -> None:
        from jarvis.router import translate_tamil_to_english
        self.assertEqual(translate_tamil_to_english("நேரம் என்ன"), "time")
        self.assertEqual(translate_tamil_to_english("தேதி என்ன"), "date")
        self.assertEqual(translate_tamil_to_english("வானிலை என்ன"), "weather")
        self.assertEqual(translate_tamil_to_english("கூகுள் திற"), "open google")
        self.assertEqual(translate_tamil_to_english("ஓபன் யூடியூப்"), "open youtube")
        self.assertEqual(translate_tamil_to_english("டைரி இன்று மகிழ்ச்சியாக இருந்தது"), "diary இன்று மகிழ்ச்சியாக இருந்தது")

        with patch("jarvis.handlers.urls.webbrowser.open") as mock_open:
            result = self.router.route("கூகுள் திறக்கவும்")
            mock_open.assert_called_once()
            self.assertIn("Opening google", result)


class UtilsTests(unittest.TestCase):
    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename('  my/file<>name  '), "myfilename")

    def test_find_best_file_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.txt").write_text("x", encoding="utf-8")
            (root / "notes.txt").write_text("y", encoding="utf-8")
            best, all_matches = find_best_file_match("notes", [root])
            self.assertIsNotNone(best)
            assert best is not None
            self.assertEqual(best.name, "notes.txt")
            self.assertGreaterEqual(len(all_matches), 1)


class ListenerTests(unittest.TestCase):
    def test_wake_word_detection(self) -> None:
        from jarvis.listener import Listener

        self.assertTrue(Listener.contains_wake_word("hey jarvis open google"))
        self.assertTrue(Listener.contains_wake_word("Hey jarvis diary test"))
        self.assertFalse(Listener.contains_wake_word("hello open google"))

    def test_extract_inline_command(self) -> None:
        from jarvis.listener import Listener

        cmd = Listener.extract_command_from_wake("hey jarvis open youtube")
        self.assertEqual(cmd, "open youtube")


class DiaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.diary_path = Path(self.tmp_dir.name) / "Diary.txt"
        self.patcher = patch("jarvis.handlers.diary.DIARY_PATH", self.diary_path)
        self.patcher.start()
        
    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp_dir.cleanup()
        
    def test_crud_operations(self) -> None:
        from jarvis.handlers.diary import append_diary_entry, get_diary_entries, update_entry, delete_entry
        
        self.assertEqual(get_diary_entries(), [])
        
        append_diary_entry("First entry")
        append_diary_entry("Second entry")
        
        entries = get_diary_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["text"], "First entry")
        self.assertEqual(entries[1]["text"], "Second entry")
        
        update_entry(0, "Modified first entry")
        entries = get_diary_entries()
        self.assertEqual(entries[0]["text"], "Modified first entry")
        
        delete_entry(0)
        entries = get_diary_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["text"], "Second entry")


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        from server import app
        self.app = app.test_client()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.diary_path = Path(self.tmp_dir.name) / "Diary.txt"
        self.patcher = patch("jarvis.handlers.diary.DIARY_PATH", self.diary_path)
        self.patcher.start()
        
    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp_dir.cleanup()

    @patch("jarvis.speech.speak")
    def test_api_diary_write_speaks(self, mock_speak) -> None:
        response = self.app.post("/api/diary/write", json={"text": "Today was a good day"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(mock_speak.call_count, 2)
        mock_speak.assert_any_call("Diary: Today was a good day", block=False)
        mock_speak.assert_any_call("Added to your diary.", block=False)

    @patch("jarvis.speech.speak")
    def test_api_diary_overwrite_speaks(self, mock_speak) -> None:
        from jarvis.handlers.diary import append_diary_entry
        append_diary_entry("First entry")
        
        response = self.app.post("/api/diary/overwrite", json={"index": 0, "text": "Modified entry"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(mock_speak.call_count, 2)
        mock_speak.assert_any_call("Modify diary entry 0 to Modified entry", block=False)
        mock_speak.assert_any_call("Diary entry updated successfully.", block=False)

    @patch("jarvis.speech.speak")
    def test_api_diary_delete_speaks(self, mock_speak) -> None:
        from jarvis.handlers.diary import append_diary_entry
        append_diary_entry("First entry")
        
        response = self.app.post("/api/diary/delete", json={"index": 0})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(mock_speak.call_count, 2)
        mock_speak.assert_any_call("Delete diary entry 0", block=False)
        mock_speak.assert_any_call("Diary entry deleted successfully.", block=False)


if __name__ == "__main__":
    unittest.main()
