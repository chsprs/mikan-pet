from enum import Enum

from mikan_pet.core.types import Point


BASE_DPI = 96


class GestureResult(str, Enum):
    CLICK = "click"
    DRAG = "drag"


def _validate_dpi(dpi: int) -> None:
    if dpi <= 0:
        raise ValueError("dpi must be positive")


def _round_half_up(value: int, numerator: int, denominator: int) -> int:
    magnitude = (abs(value) * numerator + denominator // 2) // denominator
    return magnitude if value >= 0 else -magnitude


def drag_offset_to_logical(offset: Point, dpi: int) -> Point:
    """Convert a physical pointer offset to the 96-DPI logical baseline."""
    _validate_dpi(dpi)
    return Point(
        _round_half_up(offset.x, BASE_DPI, dpi),
        _round_half_up(offset.y, BASE_DPI, dpi),
    )


def position_from_pointer(pointer: Point, logical_offset: Point, dpi: int) -> Point:
    """Keep the saved physical pet-body origin aligned beneath the pointer."""
    _validate_dpi(dpi)
    return Point(
        pointer.x - _round_half_up(logical_offset.x, dpi, BASE_DPI),
        pointer.y - _round_half_up(logical_offset.y, dpi, BASE_DPI),
    )


class PointerGesture:
    def __init__(self, threshold: int) -> None:
        self._threshold = self._validate_threshold(threshold)
        self._press_point: Point | None = None
        self._dragged = False
        self._released = False

    @property
    def dragged(self) -> bool:
        return self._dragged

    def press(self, point: Point) -> None:
        self._press_point = point
        self._dragged = False
        self._released = False

    def move(self, point: Point) -> bool:
        if self._press_point is None or self._released:
            return False
        delta_x = point.x - self._press_point.x
        delta_y = point.y - self._press_point.y
        if delta_x * delta_x + delta_y * delta_y >= self._threshold * self._threshold:
            self._dragged = True
        return self._dragged

    def release(self, point: Point) -> GestureResult | None:
        if self._press_point is None or self._released:
            return None
        self.move(point)
        self._released = True
        return GestureResult.DRAG if self._dragged else GestureResult.CLICK

    def set_threshold(self, threshold: int) -> None:
        self._threshold = self._validate_threshold(threshold)

    @staticmethod
    def _validate_threshold(threshold: int) -> int:
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        return threshold
