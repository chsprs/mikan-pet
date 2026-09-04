"""Physical-pixel monitor work-area discovery and placement helpers."""

from __future__ import annotations

import ctypes
import importlib
from dataclasses import dataclass
from typing import Protocol, Sequence

from mikan_pet.core.types import Point, Size, WorkArea


@dataclass(frozen=True)
class MonitorInfo:
    id: str
    work_area: WorkArea
    primary: bool


class MonitorBackend(Protocol):
    def enumerate(self) -> Sequence[MonitorInfo]: ...


class DpiAwarenessBackend(Protocol):
    def is_per_monitor(self) -> bool: ...

    def set_per_monitor_v2(self) -> bool: ...

    def set_per_monitor_legacy(self) -> bool: ...


def intersection_area(position: Point, pet_size: Size, area: WorkArea) -> int:
    """Return the half-open rectangle overlap between a pet and a work area."""
    width = max(0, min(position.x + pet_size.width, area.right) - max(position.x, area.left))
    height = max(0, min(position.y + pet_size.height, area.bottom) - max(position.y, area.top))
    return width * height


def clamp_position(position: Point, pet_size: Size, area: WorkArea) -> Point:
    """Keep the pet in ``area``, anchoring oversized pets at its top-left."""
    maximum_x = max(area.left, area.right - pet_size.width)
    maximum_y = max(area.top, area.bottom - pet_size.height)
    return Point(
        min(max(position.x, area.left), maximum_x),
        min(max(position.y, area.top), maximum_y),
    )


def default_position(area: WorkArea, pet_size: Size, margin: int) -> Point:
    return clamp_position(
        Point(area.right - pet_size.width - margin, area.bottom - pet_size.height - margin),
        pet_size,
        area,
    )


def _require_monitors(monitors: Sequence[MonitorInfo]) -> None:
    if not monitors:
        raise ValueError("at least one monitor is required")


def _primary_or_first(monitors: Sequence[MonitorInfo]) -> MonitorInfo:
    return next((monitor for monitor in monitors if monitor.primary), monitors[0])


def select_monitor(position: Point, pet_size: Size, monitors: Sequence[MonitorInfo]) -> MonitorInfo:
    _require_monitors(monitors)
    best = max(monitors, key=lambda monitor: intersection_area(position, pet_size, monitor.work_area))
    if intersection_area(position, pet_size, best.work_area) > 0:
        return best
    return _primary_or_first(monitors)


def _center_distance_squared(position: Point, pet_size: Size, area: WorkArea) -> int:
    center_x2 = 2 * position.x + pet_size.width
    center_y2 = 2 * position.y + pet_size.height
    if center_x2 < 2 * area.left:
        delta_x = 2 * area.left - center_x2
    elif center_x2 > 2 * area.right:
        delta_x = center_x2 - 2 * area.right
    else:
        delta_x = 0
    if center_y2 < 2 * area.top:
        delta_y = 2 * area.top - center_y2
    elif center_y2 > 2 * area.bottom:
        delta_y = center_y2 - 2 * area.bottom
    else:
        delta_y = 0
    return delta_x * delta_x + delta_y * delta_y


def select_drag_monitor(
    position: Point,
    pet_size: Size,
    monitors: Sequence[MonitorInfo],
    last_intersected_id: str | None,
) -> MonitorInfo:
    _require_monitors(monitors)
    overlaps = [intersection_area(position, pet_size, monitor.work_area) for monitor in monitors]
    largest_overlap = max(overlaps)
    if largest_overlap > 0:
        return monitors[overlaps.index(largest_overlap)]

    distances = [_center_distance_squared(position, pet_size, monitor.work_area) for monitor in monitors]
    nearest_distance = min(distances)
    tied = [monitor for monitor, distance in zip(monitors, distances) if distance == nearest_distance]
    return next((monitor for monitor in tied if monitor.id == last_intersected_id), tied[0])


class Win32MonitorBackend:
    def __init__(self, win32api_module: object | None = None) -> None:
        self._win32api = win32api_module or importlib.import_module("win32api")

    def enumerate(self) -> list[MonitorInfo]:
        monitors = []
        for handle, _, _ in self._win32api.EnumDisplayMonitors():
            info = self._win32api.GetMonitorInfo(handle)
            left, top, right, bottom = info["Work"]
            monitors.append(
                MonitorInfo(
                    id=info["Device"],
                    work_area=WorkArea(left, top, right, bottom),
                    primary=bool(info["Flags"] & 1),
                )
            )
        return monitors


class WindowsDpiAwarenessBackend:
    """ctypes adapter for process-wide Windows DPI awareness APIs."""

    _PER_MONITOR = 2
    _PER_MONITOR_V2_CONTEXT = -4

    def __init__(self, user32: object | None = None, shcore: object | None = None, kernel32: object | None = None) -> None:
        self._user32 = user32 or ctypes.WinDLL("user32", use_last_error=True)
        self._shcore = shcore or ctypes.WinDLL("shcore", use_last_error=True)
        self._kernel32 = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.GetCurrentProcess.argtypes = []
        self._kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        self._shcore.GetProcessDpiAwareness.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        self._shcore.GetProcessDpiAwareness.restype = ctypes.c_long
        self._set_per_monitor_v2 = getattr(self._user32, "SetProcessDpiAwarenessContext", None)
        if self._set_per_monitor_v2 is not None:
            self._set_per_monitor_v2.argtypes = [ctypes.c_void_p]
            self._set_per_monitor_v2.restype = ctypes.c_int
        self._shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        self._shcore.SetProcessDpiAwareness.restype = ctypes.c_long

    def is_per_monitor(self) -> bool:
        awareness = ctypes.c_int()
        result = self._shcore.GetProcessDpiAwareness(
            self._kernel32.GetCurrentProcess(), ctypes.byref(awareness)
        )
        return result >= 0 and awareness.value == self._PER_MONITOR

    def set_per_monitor_v2(self) -> bool:
        if self._set_per_monitor_v2 is None:
            return False
        return bool(self._set_per_monitor_v2(ctypes.c_void_p(self._PER_MONITOR_V2_CONTEXT)))

    def set_per_monitor_legacy(self) -> bool:
        return self._shcore.SetProcessDpiAwareness(self._PER_MONITOR) >= 0


def enable_per_monitor_dpi_awareness(backend: DpiAwarenessBackend | None = None) -> bool:
    """Enable and confirm process DPI awareness before creating a Tk root."""
    dpi_backend = backend or WindowsDpiAwarenessBackend()
    if dpi_backend.is_per_monitor():
        return True
    dpi_backend.set_per_monitor_v2()
    if dpi_backend.is_per_monitor():
        return True
    dpi_backend.set_per_monitor_legacy()
    return dpi_backend.is_per_monitor()


class MonitorService:
    def __init__(self, backend: MonitorBackend) -> None:
        self._backend = backend
        self._monitors: list[MonitorInfo] = []

    def refresh(self) -> list[MonitorInfo]:
        monitors = list(self._backend.enumerate())
        self._monitors = monitors
        if not monitors:
            raise RuntimeError("Windows returned no monitors")
        return self._monitors

    def primary(self) -> MonitorInfo:
        _require_monitors(self._monitors)
        return _primary_or_first(self._monitors)

    def current_for(self, position: Point, pet_size: Size) -> MonitorInfo:
        return select_monitor(position, pet_size, self._monitors)

    def drag_target(self, position: Point, pet_size: Size, last_intersected_id: str | None) -> MonitorInfo:
        return select_drag_monitor(position, pet_size, self._monitors, last_intersected_id)

    def recover_position(self, saved_position: Point, pet_size: Size) -> Point:
        monitor = select_monitor(saved_position, pet_size, self._monitors)
        if intersection_area(saved_position, pet_size, monitor.work_area) > 0:
            return clamp_position(saved_position, pet_size, monitor.work_area)
        return default_position(self.primary().work_area, pet_size, 24)
