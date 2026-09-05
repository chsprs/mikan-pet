"""Windows GSMTC media information service for Mikan Pet."""

from __future__ import annotations

import base64
import os
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
    def close(self) -> None: ...


class WindowsGsmtcBackend:
    """Query Windows GlobalSystemMediaTransportControls via a persistent PowerShell process."""

    _PS_CODE = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime;\n"
        "$asTaskGen = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
        "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0];\n"
        "while ($true) {\n"
        "    $line = [Console]::In.ReadLine();\n"
        "    if ($line -eq $null -or $line -eq 'QUIT') { break }\n"
        "    try {\n"
        "        $op = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType=WindowsRuntime]::RequestAsync();\n"
        "        $t1 = $asTaskGen.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]).Invoke($null, @($op));\n"
        "        if ($t1.Wait(800)) {\n"
        "            $mgr = $t1.Result;\n"
        "            $session = $mgr.GetCurrentSession();\n"
        "            if ($session) {\n"
        "                $infoOp = $session.TryGetMediaPropertiesAsync();\n"
        "                $t2 = $asTaskGen.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties]).Invoke($null, @($infoOp));\n"
        "                if ($t2.Wait(800)) {\n"
        "                    $p = $t2.Result;\n"
        "                    $pb = $session.GetPlaybackInfo();\n"
        "                    $status = if ($pb) { [int]$pb.PlaybackStatus } else { 0 };\n"
        "                    [Console]::Out.WriteLine($p.Title + '|' + $p.Artist + '|' + $status);\n"
        "                    [Console]::Out.Flush();\n"
        "                    continue;\n"
        "                }\n"
        "            }\n"
        "        }\n"
        "    } catch {}\n"
        "    [Console]::Out.WriteLine('NO_SESSION');\n"
        "    [Console]::Out.Flush();\n"
        "}\n"
    )

    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._closed = False

    def _ensure_process(self) -> subprocess.Popen[str] | None:
        if self._closed:
            return None
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        try:
            encoded = base64.b64encode(self._PS_CODE.encode("utf-16le")).decode("ascii")
            creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
            self._proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=creationflags,
            )
            return self._proc
        except Exception:
            self._proc = None
            return None

    def query_current_track(self) -> MediaTrackInfo:
        with self._lock:
            proc = self._ensure_process()
            if proc is None or proc.stdin is None or proc.stdout is None:
                return MediaTrackInfo()
            try:
                proc.stdin.write("Q\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
                if not line:
                    self._terminate_process()
                    return MediaTrackInfo()
                output = line.strip()
                if not output or output == "NO_SESSION":
                    return MediaTrackInfo()
                parts = output.split("|", 2)
                title = parts[0] if len(parts) > 0 else ""
                artist = parts[1] if len(parts) > 1 else ""
                status = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                is_playing = status == 4
                return MediaTrackInfo(title=title, artist=artist, is_playing=is_playing)
            except Exception:
                self._terminate_process()
                return MediaTrackInfo()

    def _terminate_process(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.write("QUIT\n")
                    self._proc.stdin.flush()
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._terminate_process()


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

    def close(self) -> None:
        if hasattr(self._backend, "close"):
            try:
                self._backend.close()
            except Exception:
                pass
