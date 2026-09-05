import io
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from mikan_pet.services.updater import (
    ReleaseInfo,
    download_and_extract_update,
    fetch_latest_release,
    is_directory_writable,
    is_newer_version,
    launch_in_place_updater,
    parse_version,
)


class UpdaterTests(unittest.TestCase):
    def test_parse_version_handles_prefixes_and_lengths(self) -> None:
        self.assertEqual((0, 1, 0), parse_version("0.1.0"))
        self.assertEqual((0, 2, 1), parse_version("v0.2.1"))
        self.assertEqual((1, 0), parse_version("v1.0"))
        self.assertEqual((2,), parse_version("2"))

    def test_is_newer_version(self) -> None:
        self.assertTrue(is_newer_version("0.1.0", "0.2.0"))
        self.assertTrue(is_newer_version("0.1.0", "v0.1.1"))
        self.assertFalse(is_newer_version("0.2.0", "0.2.0"))
        self.assertFalse(is_newer_version("v0.2.0", "0.2.0"))
        self.assertFalse(is_newer_version("0.2.0", "0.1.9"))
        self.assertFalse(is_newer_version("1.0.0", "0.9.9"))

    def test_fetch_latest_release_parses_github_api_json(self) -> None:
        sample_payload = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/owner/mikan-pet/releases/tag/v0.2.0",
            "body": "Bugfixes and sleep Zzzz animation",
            "assets": [
                {
                    "name": "MikanPet-Setup-x64.exe",
                    "browser_download_url": "https://github.com/owner/mikan-pet/releases/download/v0.2.0/MikanPet-Setup-x64.exe",
                },
                {
                    "name": "MikanPet-portable-x64.zip",
                    "browser_download_url": "https://github.com/owner/mikan-pet/releases/download/v0.2.0/MikanPet-portable-x64.zip",
                },
            ],
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(sample_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            release = fetch_latest_release("owner/mikan-pet")

        self.assertIsNotNone(release)
        self.assertEqual("0.2.0", release.version)
        self.assertEqual("v0.2.0", release.tag_name)
        self.assertEqual(
            "https://github.com/owner/mikan-pet/releases/download/v0.2.0/MikanPet-portable-x64.zip",
            release.zip_url,
        )
        self.assertEqual("https://github.com/owner/mikan-pet/releases/tag/v0.2.0", release.html_url)
        self.assertEqual("Bugfixes and sleep Zzzz animation", release.release_notes)

    def test_fetch_latest_release_handles_network_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=URLError("Network down")):
            release = fetch_latest_release("owner/mikan-pet")
        self.assertIsNone(release)

    def test_fetch_latest_release_handles_no_zip_asset(self) -> None:
        sample_payload = {
            "tag_name": "v0.3.0",
            "html_url": "https://github.com/owner/mikan-pet/releases/tag/v0.3.0",
            "body": "Notes",
            "assets": [],
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(sample_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            release = fetch_latest_release("owner/mikan-pet")

        self.assertIsNotNone(release)
        self.assertIsNone(release.zip_url)

    def test_download_and_extract_update(self) -> None:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test.txt", "hello from update")

        mock_response = MagicMock()
        mock_response.read.return_value = zip_buffer.getvalue()
        mock_response.__enter__.return_value = mock_response

        with TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)
            with patch("urllib.request.urlopen", return_value=mock_response):
                download_and_extract_update("https://example.com/update.zip", target_path)

            extracted_file = target_path / "test.txt"
            self.assertTrue(extracted_file.exists())
            self.assertEqual("hello from update", extracted_file.read_text(encoding="utf-8"))

    def test_is_directory_writable_returns_true_for_temp_dir(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            self.assertTrue(is_directory_writable(Path(tmp_dir)))

    @patch("subprocess.Popen")
    def test_launch_in_place_updater_creates_script_with_retry_loop(self, mock_popen: Mock) -> None:
        with TemporaryDirectory() as staging, TemporaryDirectory() as install:
            script_path = launch_in_place_updater(Path(staging), Path(install))
            self.assertTrue(script_path.exists())
            content = script_path.read_text(encoding="ascii")
            self.assertIn(":copy_loop", content)
            self.assertIn("RETRY", content)
            self.assertIn("xcopy", content)
            mock_popen.assert_called_once()
            # Clean up
            try:
                script_path.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
