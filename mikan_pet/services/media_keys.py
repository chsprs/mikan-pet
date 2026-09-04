"""Windows media-key service and its injectable backend interface."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

KEYEVENTF_KEYUP = 0x0002


class MediaAction(str, Enum):
    PREVIOUS = "previous"
    PLAY_PAUSE = "play_pause"
    NEXT = "next"


MEDIA_VIRTUAL_KEYS = {
    MediaAction.PREVIOUS: 0xB1,
    MediaAction.PLAY_PAUSE: 0xB3,
    MediaAction.NEXT: 0xB0,
}


class MediaBackend(Protocol):
    def key_event(self, virtual_key: int, flags: int) -> None: ...


class Win32MediaBackend:
    """Adapter around ``win32api.keybd_event``."""

    def key_event(self, virtual_key: int, flags: int) -> None:
        import win32api

        win32api.keybd_event(virtual_key, 0, flags, 0)


class MediaKeyService:
    def __init__(self, backend: MediaBackend | None = None) -> None:
        self._backend = backend or Win32MediaBackend()

    def send(self, action: MediaAction) -> None:
        virtual_key = MEDIA_VIRTUAL_KEYS[action]
        self._backend.key_event(virtual_key, 0)
        self._backend.key_event(virtual_key, KEYEVENTF_KEYUP)
