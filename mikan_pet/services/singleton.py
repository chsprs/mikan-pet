"""Windows named-mutex single-instance guard."""

from __future__ import annotations

from typing import Protocol

ERROR_ALREADY_EXISTS = 183


class SingleInstanceAlreadyRunningError(RuntimeError):
    """Raised when a named singleton is already owned by another process."""


class MutexBackend(Protocol):
    def create_mutex(self, name: str) -> object: ...

    def get_last_error(self) -> int: ...

    def close_handle(self, handle: object) -> None: ...


class Win32MutexBackend:
    """Adapter around the pywin32 mutex and handle APIs."""

    def create_mutex(self, name: str) -> object:
        import win32event

        return win32event.CreateMutex(None, False, name)

    def get_last_error(self) -> int:
        import win32api

        return win32api.GetLastError()

    def close_handle(self, handle: object) -> None:
        import win32api

        win32api.CloseHandle(handle)


class SingleInstance:
    def __init__(self, name: str, backend: MutexBackend | None = None) -> None:
        self._name = name
        self._backend = backend or Win32MutexBackend()
        self._handle: object | None = None
        self.acquired = False

    def acquire(self) -> bool:
        if self.acquired:
            return True
        handle = self._backend.create_mutex(self._name)
        if self._backend.get_last_error() == ERROR_ALREADY_EXISTS:
            self._backend.close_handle(handle)
            return False
        self._handle = handle
        self.acquired = True
        return True

    def release(self) -> None:
        if self._handle is not None:
            handle = self._handle
            self._handle = None
            self.acquired = False
            self._backend.close_handle(handle)

    def __enter__(self) -> "SingleInstance":
        if not self.acquire():
            raise SingleInstanceAlreadyRunningError(
                f"another instance already owns {self._name!r}"
            )
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.release()
