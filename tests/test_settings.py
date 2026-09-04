import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mikan_pet.core.types import Point, SkinId
from mikan_pet.services.settings import AppSettings, SettingsStore, default_settings, settings_path


class SettingsStoreTests(unittest.TestCase):
    def test_missing_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(Path(folder) / "settings.json")
            self.assertEqual(default_settings(), store.load())

    def test_round_trip_preserves_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            settings = AppSettings(
                schema_version=1,
                position=Point(-120, 450),
                monitor_id=r"\\.\DISPLAY2",
                skin=SkinId.BYTE,
                walking=False,
                controls_visible=False,
                always_on_top=True,
            )
            store = SettingsStore(path)
            store.save(settings)
            self.assertEqual(settings, store.load())
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_corrupt_or_invalid_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"skin":"unknown","position":"bad"}', encoding="utf-8")
            self.assertEqual(default_settings(), SettingsStore(path).load())

    def test_truncated_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"schema_version": 1,', encoding="utf-8")
            self.assertEqual(default_settings(), SettingsStore(path).load())

    def test_save_writes_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            SettingsStore(path).save(default_settings())
            self.assertEqual(1, json.loads(path.read_text(encoding="utf-8"))["schema_version"])

    def test_save_atomically_replaces_the_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("old", encoding="utf-8")
            with patch("mikan_pet.services.settings.os.replace", wraps=os.replace) as replace:
                SettingsStore(path).save(default_settings())
            replace.assert_called_once_with(path.with_name("settings.tmp"), path)
            self.assertEqual(1, json.loads(path.read_text(encoding="utf-8"))["schema_version"])

    def test_failed_replace_preserves_existing_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("old", encoding="utf-8")
            with patch("mikan_pet.services.settings.os.replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    SettingsStore(path).save(default_settings())
            self.assertEqual("old", path.read_text(encoding="utf-8"))
            self.assertFalse(path.with_name("settings.tmp").exists())

    def test_settings_path_uses_appdata(self) -> None:
        with patch.dict(os.environ, {"APPDATA": r"C:\Users\Test\AppData\Roaming"}):
            self.assertEqual(Path(os.environ["APPDATA"]) / "MikanPet" / "settings.json", settings_path())

    def test_invalid_documents_use_defaults(self) -> None:
        invalid_documents = [
            {"schema_version": True},
            {"schema_version": 1.0},
            {"schema_version": "1"},
            {"schema_version": 1, "position": {"x": True, "y": 2}},
            {"schema_version": 1, "position": {"x": 1, "y": False}},
            {"schema_version": 1, "position": {"x": 1}},
            {"schema_version": 1, "position": {"y": 2}},
            {"schema_version": 1, "position": []},
            {"schema_version": 1, "monitor_id": 4},
            {"schema_version": 1, "skin": "mikan", "walking": 1},
            {"schema_version": 1, "skin": "mikan", "controls_visible": 0},
            {"schema_version": 1, "skin": "mikan", "always_on_top": "true"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            for index, document in enumerate(invalid_documents):
                with self.subTest(index=index):
                    path = Path(folder) / f"{index}.json"
                    path.write_text(json.dumps(document), encoding="utf-8")
                    self.assertEqual(default_settings(), SettingsStore(path).load())

    def test_unreadable_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(default_settings(), SettingsStore(Path(folder)).load())

    def test_failed_write_cleans_temp_and_preserves_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("old", encoding="utf-8")
            with patch("mikan_pet.services.settings.json.dump", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    SettingsStore(path).save(default_settings())
            self.assertEqual("old", path.read_text(encoding="utf-8"))
            self.assertFalse(path.with_name("settings.tmp").exists())

    def test_failed_fsync_cleans_temp_and_preserves_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("old", encoding="utf-8")
            with patch("mikan_pet.services.settings.os.fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    SettingsStore(path).save(default_settings())
            self.assertEqual("old", path.read_text(encoding="utf-8"))
            self.assertFalse(path.with_name("settings.tmp").exists())


if __name__ == "__main__":
    unittest.main()
