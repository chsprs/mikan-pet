"""Physical-coordinate placement shared by movement and monitor recovery."""

from mikan_pet.core.types import Point, Size, WorkArea


def clamp_position(position: Point, pet_size: Size, area: WorkArea) -> Point:
    """Keep a pet inside an area, anchoring oversized pets at its top-left."""
    maximum_x = max(area.left, area.right - pet_size.width)
    maximum_y = max(area.top, area.bottom - pet_size.height)
    return Point(
        min(max(position.x, area.left), maximum_x),
        min(max(position.y, area.top), maximum_y),
    )
