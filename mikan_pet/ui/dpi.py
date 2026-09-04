"""Injectable Win32 DPI-change handling for the Tk pet window."""

from __future__ import annotations

import ctypes
import importlib
from collections.abc import Callable
from typing import Protocol


WM_DPICHANGED = 0x02E0
DEFAULT_DPI = 96
Rect = tuple[int, int, int, int]
DpiCallback = Callable[[int, Rect], None]
WindowMessageHandler = Callable[[int, int, int], int]


class DpiBackend(Protocol):
    def resolve_top_level(self, child_hwnd: int) -> int: ...

    def get_window_dpi(self, hwnd: int) -> int: ...

    def install_subclass(self, hwnd: int, handler: WindowMessageHandler) -> None: ...

    def read_suggested_rect(self, lparam: int) -> Rect: ...

    def apply_suggested_rect(self, rect: Rect) -> None: ...

    def call_previous(self, message: int, wparam: int, lparam: int) -> int: ...

    def restore_subclass(self) -> None: ...


class _NativeRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def dpi_from_wparam(wparam: int) -> int:
    """Extract the horizontal DPI from a WM_DPICHANGED wParam."""
    return wparam & 0xFFFF


class Win32DpiBackend:
    """Small pywin32/ctypes adapter whose mechanics are replaceable in tests."""

    def __init__(
        self,
        win32gui_module: object | None = None,
        win32con_module: object | None = None,
        user32: object | None = None,
    ) -> None:
        self._win32gui = win32gui_module or importlib.import_module("win32gui")
        self._win32con = win32con_module or importlib.import_module("win32con")
        self._user32 = user32 or ctypes.WinDLL("user32", use_last_error=True)
        self._set_window_long_ptr = getattr(self._user32, "SetWindowLongPtrW", None)
        if self._set_window_long_ptr is not None:
            self._set_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            self._set_window_long_ptr.restype = ctypes.c_void_p
        self._hwnd: int | None = None
        self._previous_proc: object | None = None
        self._window_proc: Callable[..., int] | None = None

    def resolve_top_level(self, child_hwnd: int) -> int:
        parent = int(self._win32gui.GetParent(child_hwnd) or 0)
        return parent or child_hwnd

    def get_window_dpi(self, hwnd: int) -> int:
        get_dpi = getattr(self._user32, "GetDpiForWindow", None)
        if get_dpi is None:
            return DEFAULT_DPI
        dpi = int(get_dpi(hwnd))
        if dpi <= 0:
            raise RuntimeError("GetDpiForWindow returned an invalid DPI")
        return dpi

    def install_subclass(self, hwnd: int, handler: WindowMessageHandler) -> None:
        if self._previous_proc is not None:
            return

        def window_proc(_hwnd: int, message: int, wparam: int, lparam: int) -> int:
            return handler(message, wparam, lparam)

        self._hwnd = hwnd
        self._window_proc = window_proc
        self._previous_proc = self._win32gui.SetWindowLong(
            hwnd,
            self._win32con.GWL_WNDPROC,
            window_proc,
        )

    def read_suggested_rect(self, lparam: int) -> Rect:
        native = ctypes.cast(lparam, ctypes.POINTER(_NativeRect)).contents
        return native.left, native.top, native.right, native.bottom

    def apply_suggested_rect(self, rect: Rect) -> None:
        if self._hwnd is None:
            return
        left, top, right, bottom = rect
        flags = self._win32con.SWP_NOZORDER | self._win32con.SWP_NOACTIVATE
        self._win32gui.SetWindowPos(
            self._hwnd,
            0,
            left,
            top,
            right - left,
            bottom - top,
            flags,
        )

    def call_previous(self, message: int, wparam: int, lparam: int) -> int:
        if self._previous_proc is None or self._hwnd is None:
            return 0
        return int(
            self._win32gui.CallWindowProc(
                self._previous_proc,
                self._hwnd,
                message,
                wparam,
                lparam,
            )
        )

    def restore_subclass(self) -> None:
        if self._previous_proc is None or self._hwnd is None:
            return
        if isinstance(self._previous_proc, int) and self._set_window_long_ptr is not None:
            self._set_window_long_ptr(
                self._hwnd,
                self._win32con.GWL_WNDPROC,
                ctypes.c_void_p(self._previous_proc),
            )
        else:
            self._win32gui.SetWindowLong(
                self._hwnd,
                self._win32con.GWL_WNDPROC,
                self._previous_proc,
            )
        self._previous_proc = None
        self._window_proc = None


class DpiWatcher:
    def __init__(
        self,
        root: object,
        callback: DpiCallback,
        backend: DpiBackend | None = None,
    ) -> None:
        self._root = root
        self._callback = callback
        self._backend = backend or Win32DpiBackend()
        self._installed = False
        self._closed = False
        self._initial_dpi: int | None = None

    def install(self) -> int:
        if self._installed:
            assert self._initial_dpi is not None
            return self._initial_dpi
        self._root.update_idletasks()
        hwnd = self._backend.resolve_top_level(self._root.winfo_id())
        if not hwnd:
            raise RuntimeError("Tk did not expose a top-level window handle")
        initial_dpi = self._backend.get_window_dpi(hwnd)
        self._backend.install_subclass(hwnd, self.handle_message)
        self._initial_dpi = initial_dpi
        self._installed = True
        return initial_dpi

    def handle_message(self, message: int, wparam: int, lparam: int) -> int:
        if message != WM_DPICHANGED:
            return self._backend.call_previous(message, wparam, lparam)
        if self._closed:
            return 0
        rect = self._backend.read_suggested_rect(lparam)
        self._backend.apply_suggested_rect(rect)
        dpi = dpi_from_wparam(wparam)

        def notify_if_open() -> None:
            if not self._closed:
                self._callback(dpi, rect)

        self._root.after_idle(notify_if_open)
        return 0

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._installed:
            self._backend.restore_subclass()
