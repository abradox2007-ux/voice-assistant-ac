"""Automated tests for AC command routing and handlers (no microphone)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ac.router import CommandRouter
from ac.utils import find_best_file_match, load_config, sanitize_filename


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()
        cls.router = CommandRouter(cls.config)

    def test_delete_rejected(self) -> None:
        result = self.router.route("delete file test")
        self.assertIn("not supported", result.lower())

    def test_diary_priority_over_open(self) -> None:
        with patch("ac.handlers.diary.append_diary_entry", return_value="Added to your diary.") as mock:
            result = self.router.route("diary open google was fun")
            mock.assert_called_once_with("open google was fun")
            self.assertEqual(result, "Added to your diary.")

    def test_diary_empty(self) -> None:
        with patch("ac.handlers.diary.append_diary_entry", return_value="What would you like to add to your diary?") as mock:
            result = self.router.route("diary")
            mock.assert_called_once_with("")
            self.assertEqual(result, "What would you like to add to your diary?")
            
            mock.reset_mock()
            result_spaces = self.router.route("diary   ")
            mock.assert_called_once_with("")
            self.assertEqual(result_spaces, "What would you like to add to your diary?")

    def test_diary_with_punctuation(self) -> None:
        with patch("ac.handlers.diary.append_diary_entry", return_value="Added to your diary.") as mock:
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
        with patch("ac.handlers.diary.open_diary", return_value="Opening your diary.") as mock:
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

    def test_time_query(self) -> None:
        result = self.router.route("what time is it")
        self.assertIn("time is", result.lower())

    def test_date_query(self) -> None:
        result = self.router.route("what's the date")
        self.assertIn("today is", result.lower())

    def test_weather_query(self) -> None:
        with patch("ac.handlers.info.tell_weather", return_value="The weather in Chennai is clear."):
            result = self.router.route("what's the weather")
            self.assertIn("weather", result.lower())

    def test_create_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ac.handlers.files.DATA_DIR", Path(tmp)):
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
        with patch("ac.handlers.urls.webbrowser.open") as mock_open:
            result = self.router.route("open google")
            mock_open.assert_called_once()
            self.assertIn("Opening google", result)

    def test_open_app_not_url(self) -> None:
        with patch("ac.handlers.apps.subprocess.Popen") as mock_popen:
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
            with patch("ac.handlers.files.os.startfile") as mock_start:
                result = router.route("open notes")
                mock_start.assert_called_once()
                self.assertIn("Opening notes.txt", result)

    def test_unknown_command(self) -> None:
        result = self.router.route("do something random xyz")
        self.assertIn("didn't understand", result.lower())

    def test_help_command(self) -> None:
        result = self.router.route("help")
        self.assertIn("open google", result.lower())


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
        from ac.listener import Listener

        self.assertTrue(Listener.contains_wake_word("hey AC open google"))
        self.assertTrue(Listener.contains_wake_word("Hey A C diary test"))
        self.assertFalse(Listener.contains_wake_word("hello open google"))

    def test_extract_inline_command(self) -> None:
        from ac.listener import Listener

        cmd = Listener.extract_command_from_wake("hey AC open youtube")
        self.assertEqual(cmd, "open youtube")


class DiaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.diary_path = Path(self.tmp_dir.name) / "Diary.txt"
        self.patcher = patch("ac.handlers.diary.DIARY_PATH", self.diary_path)
        self.patcher.start()
        
    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp_dir.cleanup()
        
    def test_crud_operations(self) -> None:
        from ac.handlers.diary import append_diary_entry, get_diary_entries, update_entry, delete_entry
        
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


if __name__ == "__main__":
    unittest.main()
