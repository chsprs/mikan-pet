from dataclasses import dataclass
from enum import Enum

from mikan_pet.core.types import Direction, Pose, SkinId


FRAME_WIDTH = 32
FRAME_HEIGHT = 32


class ColorRole(str, Enum):
    BODY = "body"
    SHADE = "shade"
    DARK = "dark"
    LIGHT = "light"
    EYE = "eye"
    COLLAR = "collar"
    PATCH_ONE = "patch_one"
    PATCH_TWO = "patch_two"


@dataclass(frozen=True)
class PixelRect:
    x: int
    y: int
    width: int
    height: int
    role: ColorRole


@dataclass(frozen=True)
class FrameTemplate:
    rectangles: tuple[PixelRect, ...]


@dataclass(frozen=True)
class SkinDefinition:
    id: SkinId
    display_name: str
    palette: dict[ColorRole, str]


MIKAN = {
    ColorRole.BODY: "#E78145", ColorRole.SHADE: "#B95D32", ColorRole.DARK: "#7F4528",
    ColorRole.LIGHT: "#FFF2D8", ColorRole.EYE: "#2A2430", ColorRole.COLLAR: "#3C6E91",
    ColorRole.PATCH_ONE: "#E78145", ColorRole.PATCH_TWO: "#B95D32",
}
BYTE = {
    ColorRole.BODY: "#3E467E", ColorRole.SHADE: "#303767", ColorRole.DARK: "#22284F",
    ColorRole.LIGHT: "#C9D1FF", ColorRole.EYE: "#89F7D4", ColorRole.COLLAR: "#FF76B7",
    ColorRole.PATCH_ONE: "#343B70", ColorRole.PATCH_TWO: "#89F7D4",
}
MOCHI = {
    ColorRole.BODY: "#FFFAF1", ColorRole.SHADE: "#DED5CA", ColorRole.DARK: "#51434B",
    ColorRole.LIGHT: "#FFF6EA", ColorRole.EYE: "#3B343A", ColorRole.COLLAR: "#4F7E78",
    ColorRole.PATCH_ONE: "#D07A43", ColorRole.PATCH_TWO: "#51434B",
}

SKINS = {
    SkinId.MIKAN: SkinDefinition(SkinId.MIKAN, "Mikan", MIKAN),
    SkinId.BYTE: SkinDefinition(SkinId.BYTE, "Byte", BYTE),
    SkinId.MOCHI: SkinDefinition(SkinId.MOCHI, "Mochi", MOCHI),
}


def _r(x: int, y: int, width: int, height: int, role: ColorRole) -> PixelRect:
    return PixelRect(x, y, width, height, role)


_UPRIGHT = (
    _r(8, 15, 17, 11, ColorRole.BODY), _r(10, 8, 14, 11, ColorRole.BODY),
    _r(10, 5, 4, 5, ColorRole.SHADE), _r(20, 5, 4, 5, ColorRole.SHADE),
    _r(25, 18, 5, 3, ColorRole.SHADE), _r(28, 14, 3, 6, ColorRole.SHADE),
    _r(12, 11, 2, 3, ColorRole.EYE), _r(20, 11, 2, 3, ColorRole.EYE),
    _r(16, 14, 2, 2, ColorRole.DARK), _r(14, 17, 6, 2, ColorRole.LIGHT),
    _r(12, 20, 10, 2, ColorRole.COLLAR), _r(16, 21, 2, 2, ColorRole.COLLAR),
    _r(10, 24, 5, 5, ColorRole.SHADE), _r(19, 24, 5, 5, ColorRole.SHADE),
    _r(11, 8, 5, 3, ColorRole.PATCH_ONE), _r(20, 8, 4, 4, ColorRole.PATCH_TWO),
)


def _shift(rectangles: tuple[PixelRect, ...], dx: int = 0, dy: int = 0) -> tuple[PixelRect, ...]:
    return tuple(PixelRect(r.x + dx, r.y + dy, r.width, r.height, r.role) for r in rectangles)


def _with(rectangles: tuple[PixelRect, ...], *extra: PixelRect) -> FrameTemplate:
    return FrameTemplate(rectangles + extra)


_WALK = (
    _with(_UPRIGHT, _r(28, 12, 3, 2, ColorRole.SHADE)),
    _with(_shift(_UPRIGHT, dy=1), _r(28, 14, 3, 2, ColorRole.SHADE),
          _r(9, 25, 5, 5, ColorRole.SHADE), _r(20, 24, 5, 5, ColorRole.SHADE)),
)
_IDLE = tuple(FrameTemplate(_UPRIGHT) for _ in range(3))
_IDLE += tuple(FrameTemplate(_shift(_UPRIGHT, dy=1)) for _ in range(2))
_IDLE += tuple(FrameTemplate(_UPRIGHT) for _ in range(3))
_IDLE += (_with(_UPRIGHT, _r(28, 13, 3, 2, ColorRole.SHADE)),)
_IDLE += (_with(tuple(r for r in _UPRIGHT if r.role is not ColorRole.EYE),
                  _r(12, 12, 2, 1, ColorRole.EYE), _r(20, 12, 2, 1, ColorRole.EYE)),)

_SLEEP_BASE = (
    _r(6, 19, 20, 8, ColorRole.BODY), _r(5, 16, 9, 8, ColorRole.BODY),
    _r(22, 20, 8, 3, ColorRole.SHADE), _r(27, 18, 3, 5, ColorRole.SHADE),
    _r(8, 17, 3, 3, ColorRole.SHADE), _r(11, 20, 2, 1, ColorRole.EYE),
    _r(16, 20, 2, 1, ColorRole.EYE), _r(8, 22, 7, 2, ColorRole.LIGHT),
    _r(10, 24, 10, 2, ColorRole.COLLAR), _r(14, 25, 2, 2, ColorRole.COLLAR),
)
_SLEEP = (_with(_SLEEP_BASE, _r(28, 17, 2, 3, ColorRole.SHADE)),
          _with(_SLEEP_BASE, _r(29, 17, 1, 3, ColorRole.SHADE)))
_REACT = (_with(tuple(r for r in _UPRIGHT if r.role is not ColorRole.EYE),
                 _r(12, 10, 3, 3, ColorRole.EYE), _r(20, 10, 3, 3, ColorRole.EYE),
                 _r(10, 4, 4, 5, ColorRole.SHADE), _r(20, 4, 4, 5, ColorRole.SHADE),
                 _r(28, 12, 3, 2, ColorRole.SHADE)),)

FRAMES = {Pose.WALK: _WALK, Pose.IDLE: _IDLE, Pose.SLEEP: _SLEEP, Pose.REACT: _REACT}


def validate_registry() -> list[str]:
    errors: list[str] = []
    for skin_id in SkinId:
        if skin_id not in SKINS:
            errors.append(f"missing skin: {skin_id.value}")
    for pose in Pose:
        frames = FRAMES.get(pose, ())
        if not frames:
            errors.append(f"missing frames: {pose.value}")
        for index, frame in enumerate(frames):
            for rect_index, rect in enumerate(frame.rectangles):
                if rect.x < 0 or rect.y < 0 or rect.width <= 0 or rect.height <= 0 or rect.x + rect.width > FRAME_WIDTH or rect.y + rect.height > FRAME_HEIGHT:
                    errors.append(f"{pose.value}[{index}] rectangle {rect_index} outside frame")
                for skin in SKINS.values():
                    if rect.role not in skin.palette:
                        errors.append(f"{skin.id.value} missing role: {rect.role.value}")
    for skin in SKINS.values():
        if "#FF00FF" in skin.palette.values():
            errors.append(f"{skin.id.value} uses transparent key color")
    return errors


def frame_count(pose: Pose) -> int:
    return len(FRAMES.get(pose, ()))


def rasterize_frame(skin: SkinId, pose: Pose, frame_index: int, direction: Direction) -> tuple[tuple[str | None, ...], ...]:
    frame = FRAMES[pose][frame_index % frame_count(pose)]
    pixels: list[list[str | None]] = [[None] * FRAME_WIDTH for _ in range(FRAME_HEIGHT)]
    palette = SKINS[skin].palette
    for rect in frame.rectangles:
        color = palette[rect.role]
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                pixels[y][x] = color
    rows = tuple(tuple(row) for row in pixels)
    if direction is Direction.LEFT:
        rows = tuple(tuple(reversed(row)) for row in rows)
    return rows
