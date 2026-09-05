"""Windows GSMTC media information service for Mikan Pet."""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MediaTrackInfo:
    title: str = ""
    artist: str = ""
    is_playing: bool = False

    @property
    def has_track(self) -> bool:
        return bool(self.title.strip())


def format_display_title(info: MediaTrackInfo, max_length: int = 24) -> str:
    """Format track and artist nicely, truncating if necessary."""
    if not info.has_track:
        return ""
    title = info.title.strip()
    artist = info.artist.strip()
    if artist:
        text = f"{title} - {artist}"
    else:
        text = title
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


class MediaInfoBackend(Protocol):
    def query_current_track(self) -> MediaTrackInfo: ...


class WindowsGsmtcBackend:
    """Query Windows GlobalSystemMediaTransportControls via PowerShell WinRT bridge."""

    _SCRIPT = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
        "$asTaskGen = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
        "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
        "$op = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType=WindowsRuntime]::RequestAsync(); "
        "$t1 = $asTaskGen.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]).Invoke($null, @($op)); "
        "$t1.Wait(1500) | Out-Null; "
        "$mgr = $t1.Result; "
        "$session = $mgr.GetCurrentSession(); "
        "if ($session) { "
        "$infoOp = $session.TryGetMediaPropertiesAsync(); "
        "$t2 = $asTaskGen.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties]).Invoke($null, @($infoOp)); "
        "$t2.Wait(1500) | Out-Null; "
        "$p = $t2.Result; "
        "$pb = $session.GetPlaybackInfo(); "
        "$status = if ($pb) { [int]$pb.PlaybackStatus } else { 0 }; "
        "Write-Host ($p.Title + '|' + $p.Artist + '|' + $status) "
        "} else { Write-Host 'NO_SESSION' }"
    )

    def query_current_track(self) -> MediaTrackInfo:
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", self._SCRIPT],
                capture_output=True,
                text=True,
                timeout=3.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if res.returncode != 0:
                return MediaTrackInfo()
            output = res.stdout.strip()
            if not output or output == "NO_SESSION":
                return MediaTrackInfo()
            parts = output.split("|", 2)
            title = parts[0] if len(parts) > 0 else ""
            artist = parts[1] if len(parts) > 1 else ""
            status = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            is_playing = status == 4  # 4 is Playing in GSMTC PlaybackStatus
            return MediaTrackInfo(title=title, artist=artist, is_playing=is_playing)
        except Exception:
            return MediaTrackInfo()


class MediaInfoService:
    """Provides non-blocking access to currently playing media title."""

    def __init__(
        self,
        backend: MediaInfoBackend | None = None,
        poll_interval_seconds: float = 3.0,
    ) -> None:
        self._backend = backend or WindowsGsmtcBackend()
        self._poll_interval = poll_interval_seconds
        self._current_track = MediaTrackInfo()
        self._last_poll_time = 0.0
        self._lock = threading.Lock()
        self._query_in_progress = False

    @property
    def current_track(self) -> MediaTrackInfo:
        with self._lock:
            return self._current_track

    def poll_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_poll_time >= self._poll_interval and not self._query_in_progress:
            self.refresh_async()

    def refresh_async(self) -> None:
        if self._query_in_progress:
            return
        self._query_in_progress = True
        self._last_poll_time = time.monotonic()

        def worker() -> None:
            try:
                track = self._backend.query_current_track()
                with self._lock:
                    self._current_track = track
            except Exception:
                pass
            finally:
                self._query_in_progress = False

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
