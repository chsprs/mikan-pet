import io
import unittest
from unittest.mock import MagicMock, Mock, patch

from mikan_pet.services.media_info import (
    MediaInfoService,
    MediaTrackInfo,
    WindowsGsmtcBackend,
    format_display_title,
)


class MediaInfoTests(unittest.TestCase):
    def test_format_display_title_combines_title_and_artist(self) -> None:
        info = MediaTrackInfo(title="Stay", artist="Justin Bieber", is_playing=True)
        self.assertEqual("Stay - Justin Bieber", format_display_title(info, max_length=50))

    def test_format_display_title_only_title_when_no_artist(self) -> None:
        info = MediaTrackInfo(title="Instrumental Beat", artist="", is_playing=True)
        self.assertEqual("Instrumental Beat", format_display_title(info, max_length=50))

    def test_format_display_title_truncates_long_titles(self) -> None:
        long_title = "A" * 40
        info = MediaTrackInfo(title=long_title, artist="Artist", is_playing=True)
        formatted = format_display_title(info, max_length=20)
        self.assertEqual(20, len(formatted))
        self.assertTrue(formatted.endswith("..."))

    def test_format_display_title_returns_empty_when_no_track(self) -> None:
        self.assertEqual("", format_display_title(MediaTrackInfo()))

    def test_media_info_service_updates_track_from_backend(self) -> None:
        backend = Mock()
        expected = MediaTrackInfo(title="Song", artist="Artist", is_playing=True)
        backend.query_current_track.return_value = expected
        service = MediaInfoService(backend, poll_interval_seconds=0.0)
        service.poll_if_due()
        import time
        time.sleep(0.05)
        self.assertEqual(expected, service.current_track)

    def test_media_info_service_handles_backend_errors_gracefully(self) -> None:
        backend = Mock()
        backend.query_current_track.side_effect = RuntimeError("Backend failed")
        service = MediaInfoService(backend, poll_interval_seconds=0.0)
        service.poll_if_due()
        import time
        time.sleep(0.05)
        self.assertEqual(MediaTrackInfo(), service.current_track)

    def test_media_info_service_close_forwards_to_backend(self) -> None:
        backend = Mock()
        service = MediaInfoService(backend)
        service.close()
        backend.close.assert_called_once()

    @patch("subprocess.Popen")
    def test_windows_gsmtc_backend_parses_track_and_closes_cleanly(self, mock_popen: Mock) -> None:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = io.StringIO("Blue Bird|Ikimono Gakari|4\n")
        mock_popen.return_value = mock_proc

        backend = WindowsGsmtcBackend()
        info = backend.query_current_track()
        self.assertEqual("Blue Bird", info.title)
        self.assertEqual("Ikimono Gakari", info.artist)
        self.assertTrue(info.is_playing)

        backend.close()
        mock_proc.stdin.write.assert_called_with("QUIT\n")
        mock_proc.terminate.assert_called_once()

    def test_format_time_seconds(self) -> None:
        from mikan_pet.services.media_info import format_time_seconds
        self.assertEqual("00:00", format_time_seconds(0))
        self.assertEqual("00:09", format_time_seconds(9))
        self.assertEqual("01:23", format_time_seconds(83))
        self.assertEqual("03:45", format_time_seconds(225))
        self.assertEqual("1:01:05", format_time_seconds(3665))

    def test_media_track_info_timeline_properties_and_interpolation(self) -> None:
        import time
        t0 = time.monotonic()
        info = MediaTrackInfo(
            title="Song",
            artist="Artist",
            is_playing=True,
            position_seconds=10.0,
            duration_seconds=100.0,
            updated_at=t0 - 2.5,
        )
        self.assertTrue(info.has_timeline)
        self.assertGreaterEqual(info.current_position_seconds, 12.0)
        self.assertLessEqual(info.current_position_seconds, 15.0)

        # Clamps to duration
        overflow = MediaTrackInfo(
            title="Song",
            is_playing=True,
            position_seconds=95.0,
            duration_seconds=100.0,
            updated_at=t0 - 10.0,
        )
        self.assertEqual(100.0, overflow.current_position_seconds)

    @patch("subprocess.Popen")
    def test_windows_gsmtc_backend_parses_timeline_fields(self, mock_popen: Mock) -> None:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = io.StringIO("Golden Hour|JVKE|4|83|209\n")
        mock_popen.return_value = mock_proc

        backend = WindowsGsmtcBackend()
        info = backend.query_current_track()
        self.assertEqual("Golden Hour", info.title)
        self.assertEqual("JVKE", info.artist)
        self.assertTrue(info.is_playing)
        self.assertEqual(83.0, info.position_seconds)
        self.assertEqual(209.0, info.duration_seconds)
        self.assertTrue(info.has_timeline)
        backend.close()


if __name__ == "__main__":
    unittest.main()
