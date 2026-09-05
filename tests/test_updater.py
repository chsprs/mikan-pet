from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch
from urllib.error import URLError

from mikan_pet.services.updater import (
    ReleaseInfo,
    download_update_installer,
    fetch_latest_release,
    is_newer_version,
    launch_installer_updater,
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
                    "digest": "sha256:" + "a" * 64,
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
            "https://github.com/owner/mikan-pet/releases/download/v0.2.0/MikanPet-Setup-x64.exe",
            release.installer_url,
        )
        self.assertEqual("https://github.com/owner/mikan-pet/releases/tag/v0.2.0", release.html_url)
        self.assertEqual("Bugfixes and sleep Zzzz animation", release.release_notes)
        self.assertEqual("a" * 64, release.installer_sha256)

    def test_fetch_latest_release_handles_network_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=URLError("Network down")):
            release = fetch_latest_release("owner/mikan-pet")
        self.assertIsNone(release)

    def test_fetch_latest_release_handles_no_installer_asset(self) -> None:
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
        self.assertIsNone(release.installer_url)

    def test_download_update_installer(self) -> None:
        payload = b"fake executable binary"
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__.return_value = mock_response

        with TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir) / "MikanPet-Setup.exe"
            with patch("urllib.request.urlopen", return_value=mock_response):
                download_update_installer(
                    "https://example.com/MikanPet-Setup-x64.exe",
                    target_path,
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                )

            self.assertTrue(target_path.exists())
            self.assertEqual(payload, target_path.read_bytes())

    def test_download_installer_rejects_checksum_mismatch(self) -> None:
        payload = b"fake executable binary"
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__.return_value = mock_response

        with TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir) / "MikanPet-Setup.exe"
            with patch("urllib.request.urlopen", return_value=mock_response):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    download_update_installer(
                        "https://example.com/MikanPet-Setup-x64.exe",
                        target_path,
                        expected_sha256="0" * 64,
                    )
            self.assertFalse(target_path.exists())

    @patch("subprocess.Popen")
    def test_launch_installer_updater_executes_target(self, mock_popen: Mock) -> None:
        with TemporaryDirectory() as tmp_dir:
            installer = Path(tmp_dir) / "MikanPet-Setup.exe"
            installer.write_bytes(b"dummy")
            with patch("sys.platform", "win32"):
                launch_installer_updater(installer)
            mock_popen.assert_called_once_with([str(installer)], close_fds=True)


if __name__ == "__main__":
    unittest.main()
