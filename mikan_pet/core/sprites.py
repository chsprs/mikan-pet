from dataclasses import dataclass
from enum import Enum

from mikan_pet.core.animation_frames import OVERLAY_POSES, pose_grids
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
    ColorRole.BODY: "#D9783D", ColorRole.SHADE: "#AC5327", ColorRole.DARK: "#1A1A1A",
    ColorRole.LIGHT: "#EED0BD", ColorRole.EYE: "#FFFFFF", ColorRole.COLLAR: "#F6A99A",
    ColorRole.PATCH_ONE: "#EED0BD", ColorRole.PATCH_TWO: "#70B5FF",
}
BYTE = {
    ColorRole.BODY: "#2D2D2D", ColorRole.SHADE: "#202020", ColorRole.DARK: "#1A1A1A",
    ColorRole.LIGHT: "#2D2D2D", ColorRole.EYE: "#FBB03B", ColorRole.COLLAR: "#F6A99A",
    ColorRole.PATCH_ONE: "#2D2D2D", ColorRole.PATCH_TWO: "#89F7D4",
}
MOCHI = {
    ColorRole.BODY: "#FFFFFF", ColorRole.SHADE: "#E0E0E6", ColorRole.DARK: "#1A1A1A",
    ColorRole.LIGHT: "#FFFFFF", ColorRole.EYE: "#3FA9F5", ColorRole.COLLAR: "#F6A99A",
    ColorRole.PATCH_ONE: "#FFFFFF", ColorRole.PATCH_TWO: "#70B5FF",
}
ASH = {
    ColorRole.BODY: "#9E9E9E", ColorRole.SHADE: "#616161", ColorRole.DARK: "#1A1A1A",
    ColorRole.LIGHT: "#F4A7B9", ColorRole.EYE: "#FFFFFF", ColorRole.COLLAR: "#F6A99A",
    ColorRole.PATCH_ONE: "#F4A7B9", ColorRole.PATCH_TWO: "#70B5FF",
}

SKINS = {
    SkinId.MIKAN: SkinDefinition(SkinId.MIKAN, "Mikan", MIKAN),
    SkinId.BYTE: SkinDefinition(SkinId.BYTE, "Byte", BYTE),
    SkinId.MOCHI: SkinDefinition(SkinId.MOCHI, "Mochi", MOCHI),
    SkinId.ASH: SkinDefinition(SkinId.ASH, "Ash", ASH),
}


_CHAR_ROLE = {
    "X": ColorRole.DARK,
    "N": ColorRole.DARK,
    "O": ColorRole.BODY,
    "S": ColorRole.SHADE,
    "B": ColorRole.LIGHT,
    "P": ColorRole.COLLAR,
    "E": ColorRole.EYE,
    "W": ColorRole.EYE,
    "Z": ColorRole.PATCH_TWO,
}


def _ascii_to_template(grid: list[str]) -> FrameTemplate:
    row_runs: list[list[PixelRect]] = []
    for y, row in enumerate(grid):
        runs: list[PixelRect] = []
        x = 0
        while x < len(row):
            ch = row[x]
            if ch in _CHAR_ROLE:
                role = _CHAR_ROLE[ch]
                start_x = x
                while x < len(row) and row[x] in _CHAR_ROLE and _CHAR_ROLE[row[x]] == role:
                    x += 1
                runs.append(PixelRect(start_x, y, x - start_x, 1, role))
            else:
                x += 1
        row_runs.append(runs)

    merged: list[PixelRect] = []
    active: list[PixelRect] = []

    for runs in row_runs:
        next_active: list[PixelRect] = []
        for r in runs:
            matched = False
            for a in active:
                if a.x == r.x and a.width == r.width and a.role == r.role and a.y + a.height == r.y:
                    idx = active.index(a)
                    active[idx] = PixelRect(a.x, a.y, a.width, a.height + 1, a.role)
                    next_active.append(active[idx])
                    matched = True
                    break
            if not matched:
                next_active.append(r)
        for a in active:
            if a not in next_active:
                merged.append(a)
        active = next_active

    merged.extend(active)
    return FrameTemplate(tuple(merged))


FRAMES = {pose: tuple(_ascii_to_template(grid) for grid in grids)
          for pose, grids in pose_grids().items()}


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


def _overlay_glyphs(rects) -> list[set[tuple[int, int]]]:
    """Group floating accent pixels into separately placed glyphs (8-connected)."""
    pending = {(x, y) for rect in rects
               for y in range(rect.y, rect.y + rect.height)
               for x in range(rect.x, rect.x + rect.width)}
    glyphs = []
    while pending:
        stack = [pending.pop()]
        glyph = set(stack)
        while stack:
            x, y = stack.pop()
            for neighbor in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if neighbor in pending:
                    pending.remove(neighbor)
                    glyph.add(neighbor)
                    stack.append(neighbor)
        glyphs.append(glyph)
    return glyphs


def rasterize_frame(skin: SkinId, pose: Pose, frame_index: int, direction: Direction) -> tuple[tuple[str | None, ...], ...]:
    frame = FRAMES[pose][frame_index % frame_count(pose)]
    pixels: list[list[str | None]] = [[None] * FRAME_WIDTH for _ in range(FRAME_HEIGHT)]
    palette = SKINS[skin].palette
    overlay = pose in OVERLAY_POSES
    for rect in frame.rectangles:
        if overlay and rect.role is ColorRole.PATCH_TWO:
            continue
        color = palette[rect.role]
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                pixels[y][x] = color

    if direction is Direction.LEFT:
        pixels = [list(reversed(row)) for row in pixels]

    if overlay:
        # Zs and notes move to the mirrored side but keep their readable shape.
        color = palette[ColorRole.PATCH_TWO]
        accents = [rect for rect in frame.rectangles if rect.role is ColorRole.PATCH_TWO]
        for glyph in _overlay_glyphs(accents):
            left = min(x for x, _ in glyph)
            right = max(x for x, _ in glyph)
            shift = FRAME_WIDTH - 1 - right - left if direction is Direction.LEFT else 0
            for x, y in glyph:
                pixels[y][x + shift] = color

    return tuple(tuple(row) for row in pixels)
