from dataclasses import dataclass

from mikan_pet.core.types import Point, Size, WorkArea


BASE_DPI = 96
BASE_PIXEL_SCALE = 4
BASE_PET_SIZE = Size(144, 128)
BASE_COLLAPSED_SIZE = Size(144, 128)
BASE_EXPANDED_SIZE = Size(200, 208)
BASE_EXPANDED_PET_OFFSET = Point(28, 80)
BASE_PET_IMAGE_OFFSET = Point(8, 0)
BASE_DRAG_THRESHOLD_PX = 5


@dataclass(frozen=True)
class DpiMetrics:
    dpi: int
    pixel_scale: int
    pet_size: Size
    collapsed_size: Size
    expanded_size: Size
    expanded_pet_offset: Point
    pet_image_offset: Point
    drag_threshold_px: int


@dataclass(frozen=True)
class WindowLayout:
    root_origin: Point
    window_size: Size
    pet_offset: Point
    pet_screen_origin: Point


def _scale(value: int, dpi: int) -> int:
    return (value * dpi + BASE_DPI // 2) // BASE_DPI


def _scale_size(size: Size, dpi: int) -> Size:
    return Size(_scale(size.width, dpi), _scale(size.height, dpi))


def _scale_point(point: Point, dpi: int) -> Point:
    return Point(_scale(point.x, dpi), _scale(point.y, dpi))


def metrics_for_dpi(dpi: int) -> DpiMetrics:
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    return DpiMetrics(
        dpi=dpi,
        pixel_scale=max(1, _scale(BASE_PIXEL_SCALE, dpi)),
        pet_size=_scale_size(BASE_PET_SIZE, dpi),
        collapsed_size=_scale_size(BASE_COLLAPSED_SIZE, dpi),
        expanded_size=_scale_size(BASE_EXPANDED_SIZE, dpi),
        expanded_pet_offset=_scale_point(BASE_EXPANDED_PET_OFFSET, dpi),
        pet_image_offset=_scale_point(BASE_PET_IMAGE_OFFSET, dpi),
        drag_threshold_px=_scale(BASE_DRAG_THRESHOLD_PX, dpi),
    )


def calculate_window_layout(position: Point, controls_visible: bool, metrics: DpiMetrics) -> WindowLayout:
    if not controls_visible:
        return WindowLayout(position, metrics.collapsed_size, Point(0, 0), position)
    pet_offset = metrics.expanded_pet_offset
    root_origin = Point(position.x - pet_offset.x, position.y - pet_offset.y)
    return WindowLayout(root_origin, metrics.expanded_size, pet_offset, position)


def safe_pet_work_area(work_area: WorkArea, controls_visible: bool, metrics: DpiMetrics) -> WorkArea:
    if not controls_visible:
        return work_area
    left_inset = metrics.expanded_pet_offset.x
    top_inset = metrics.expanded_pet_offset.y
    right_inset = metrics.expanded_size.width - left_inset - metrics.pet_size.width
    return WorkArea(
        work_area.left + left_inset,
        work_area.top + top_inset,
        work_area.right - right_inset,
        work_area.bottom,
    )
