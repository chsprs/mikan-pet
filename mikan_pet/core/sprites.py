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


# 32x32 Pixel Art Grids (facing RIGHT, mirrored horizontally for LEFT)
_GRID_STAND = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............XXX.....XXX........",
    "............XOOPXXXXXOOPX.......",
    "............XPOOSSSSOOPPX.......",
    "............XOOOSOOOSOOOX.......",
    "............XOOOOOOOOOOOX.......",
    "............XSOOWOOOWOOSX.......",
    "..........XXXOOOXOXOXOOOXXX.....",
    "............XSOOOOOOOOOSX.......",
    "..........XXXOOOOOOOOOOOXXX.....",
    "......XXX....XXOOOOOOOXX........",
    ".....XOSSX.....XOOOOOX..........",
    ".....XOSOSX...XSSOOBBX..........",
    "......XXXSOX.XSSOOBBBX..........",
    ".........XOOXSSOOBBBBX..........",
    "..........XOSOOOOBBBBX..........",
    "...........XXOOXOOXOOX..........",
    ".............XXXXXXXX...........",
    "................................",
    "................................",
]

_GRID_BLINK = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............XXX.....XXX........",
    "............XOOPXXXXXOOPX.......",
    "............XPOOSSSSOOPPX.......",
    "............XOOOSOOOSOOOX.......",
    "............XOOOOOOOOOOOX.......",
    "............XSOOOOOOOOOSX.......",
    "..........XXXOOOXXXOXOOOXXX.....",
    "............XSOOOOOOOOOSX.......",
    "..........XXXOOOOOOOOOOOXXX.....",
    "......XXX....XXOOOOOOOXX........",
    ".....XOSSX.....XOOOOOX..........",
    ".....XOSOSX...XSSOOBBX..........",
    "......XXXSOX.XSSOOBBBX..........",
    ".........XOOXSSOOBBBBX..........",
    "..........XOSOOOOBBBBX..........",
    "...........XXOOXOOXOOX..........",
    ".............XXXXXXXX...........",
    "................................",
    "................................",
]

# Forward Walk Cycle (4-frame natural quadruped stride)
_GRID_WALK_0 = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............XXX.....XXX........",
    "............XOOPXXXXXOOPX.......",
    "............XPOOSSSSOOPPX.......",
    "............XOOOSOOOSOOOX.......",
    "............XOOOOOOOOOOOX.......",
    "............XSOOWOOOWOOSX.......",
    "..........XXXOOOXOXOXOOOXXX.....",
    "............XSOOOOOOOOOSX.......",
    "......XXX.XXXOOOOOOOOOOOXXX.....",
    ".....XOSSX...XXOOOOOOOXX........",
    ".....XOSOSX....XOOOOOX..........",
    "......XXXSOX..XSSOOBBX..........",
    ".........XOOXXSSOOBBBX..........",
    "..........XOSOOOOBBBBX..........",
    ".........XOOXOOOOBBBBOXX........",
    "........XXOOXOOXOOXOOXOX........",
    ".........XXXX...XXXXXXXX........",
    "................................",
    "................................",
]

_GRID_WALK_1 = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............XXX.....XXX........",
    "............XOOPXXXXXOOPX.......",
    "............XPOOSSSSOOPPX.......",
    "............XOOOSOOOSOOOX.......",
    "............XOOOOOOOOOOOX.......",
    "............XSOOWOOOWOOSX.......",
    "..........XXXOOOXOXOXOOOXXX.....",
    "............XSOOOOOOOOOSX.......",
    "..........XXXOOOOOOOOOOOXXX.....",
    "......XXX....XXOOOOOOOXX........",
    ".....XOSSX.....XOOOOOX..........",
    ".....XOSOSX...XSSOOBBX..........",
    "......XXXSOX.XSSOOBBBX..........",
    ".........XOOXSSOOBBBBX..........",
    "..........XOSOOOOBBBBX..........",
    "...........XXOOXOOXOOX..........",
    "............XOOXOOXOOX..........",
    "............XXXXXXXXXX..........",
    "................................",
    "................................",
]

_GRID_WALK_2 = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............XXX.....XXX........",
    "............XOOPXXXXXOOPX.......",
    "............XPOOSSSSOOPPX.......",
    "............XOOOSOOOSOOOX.......",
    "............XOOOOOOOOOOOX.......",
    "............XSOOWOOOWOOSX.......",
    "..........XXXOOOXOXOXOOOXXX.....",
    "............XSOOOOOOOOOSX.......",
    "..........XXXOOOOOOOOOOOXXX.....",
    "......XXX....XXOOOOOOOXX........",
    ".....XOSSX.....XOOOOOX..........",
    ".....XOSOSX...XSSOOBBX..........",
    "......XXXSOX.XSSOOBBBX..........",
    ".........XOOXSSOOBBBBX..........",
    "..........XOSOOOOBBBBX..........",
    "...........XOOXXOOXXOOX.........",
    "............XXXX..XXXXX.........",
    "................................",
    "................................",
]

_GRID_WALK_3 = _GRID_WALK_1

# Sleep Grids with animated Z floating (Loaf Sleeping Pose)
_GRID_SLEEP_BASE = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "..................XXX.....XXX...",
    ".......XXXXX.....XOOPXXXXXOOPX..",
    ".....XXOOOOOXXXXXPOOSSSSOOPPX...",
    "....XOOOOOOOOOOOOOOOSOOOSOOOX...",
    "...XOOOOOOOOOOOOOOOOOOOOOOOOX...",
    "...XOOOOOOOOOOOOOOOOOOOOOOOOX...",
    "...XOOOOOOOOOOOOOOOOOOOOOOOOX...",
    "...XOOOOOOOOOOOOOXOOOXXXOXOOOXXX",
    "...XSSSOOOOOOOOOOXOOOOOOOOOSX...",
    "...XSSSOOOOOOOOOOXOOOOOOOOOOXXX.",
    "....XOOOOOOOOOOOOOOOOOOOOOOX....",
    ".....XXXXXXXXXXXXXXXXXXXXXX.....",
    "................................",
    "................................",
    "................................",
    "................................",
]


def _with_z(base: list[str], coords: list[tuple[int, int]]) -> list[str]:
    grid = [list(r) for r in base]
    for x, y in coords:
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            grid[y][x] = "Z"
    return ["".join(r) for r in grid]


_Z_SMALL = lambda ox, oy: [(ox, oy), (ox + 1, oy), (ox + 2, oy), (ox + 1, oy + 1), (ox, oy + 2), (ox + 1, oy + 2), (ox + 2, oy + 2)]
_Z_BIG = lambda ox, oy: [(ox, oy), (ox + 1, oy), (ox + 2, oy), (ox + 3, oy), (ox + 2, oy + 1), (ox + 1, oy + 2), (ox, oy + 3), (ox + 1, oy + 3), (ox + 2, oy + 3), (ox + 3, oy + 3)]

_GRID_SLEEP_0 = _with_z(_GRID_SLEEP_BASE, _Z_SMALL(22, 10))
_GRID_SLEEP_1 = _with_z(_GRID_SLEEP_BASE, _Z_SMALL(24, 7) + _Z_SMALL(20, 11))
_GRID_SLEEP_2 = _with_z(_GRID_SLEEP_BASE, _Z_BIG(24, 4) + _Z_SMALL(21, 8))
_GRID_SLEEP_3 = _with_z(_GRID_SLEEP_BASE, _Z_BIG(25, 2) + _Z_BIG(22, 6) + _Z_SMALL(18, 10))

# React: alert ears, front-facing cheerful happy face with open mouth
_GRID_REACT = [
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "...........XXX.....XXX..........",
    "..........XPPPXXXXXPPPX.........",
    "..........XPOOSSSSOOPPX.........",
    "..........XOOOSOOOSOOOX.........",
    "..........XOOOOOOOOOOOX.........",
    "..........XSWWWOWWWOOSX.........",
    "........XXXSWNWXWNWOOSXXX.......",
    "..........XSOOOXXXOOOSX.........",
    "........XXXOOOOXXXOOOOXXX.......",
    "....XXX...XXOOOOOOOOOXX...XXX...",
    "...XOOX.....XOBBBBBOX.....XOOX..",
    "...XOOX....XOBBBBBBBOX....XOOX..",
    "...XOOX...XOBBBBBBBBBOX...XOOX..",
    "....XOOX..XOBBBBBBBBBOX..XOOX...",
    ".....XOOXXXOBBBBBBBBBOXXXOOX....",
    "......XXOOXOOXBBBBBXOOXOOXX.....",
    "........XXOOOXBBBBBXOOOXX.......",
    "..........XXXXXXXXXXXXXXXX......",
    "................................",
    "................................",
    "................................",
    "................................",
]


# Compile templates
_T_STAND = _ascii_to_template(_GRID_STAND)
_T_BLINK = _ascii_to_template(_GRID_BLINK)
_T_WALK_0 = _ascii_to_template(_GRID_WALK_0)
_T_WALK_1 = _ascii_to_template(_GRID_WALK_1)
_T_WALK_2 = _ascii_to_template(_GRID_WALK_2)
_T_WALK_3 = _ascii_to_template(_GRID_WALK_3)

_T_SLEEP_0 = _ascii_to_template(_GRID_SLEEP_0)
_T_SLEEP_1 = _ascii_to_template(_GRID_SLEEP_1)
_T_SLEEP_2 = _ascii_to_template(_GRID_SLEEP_2)
_T_SLEEP_3 = _ascii_to_template(_GRID_SLEEP_3)

_T_REACT = _ascii_to_template(_GRID_REACT)

_WALK = (_T_WALK_0, _T_WALK_1, _T_WALK_2, _T_WALK_3)

_IDLE = (
    _T_STAND, _T_STAND, _T_STAND,
    _T_WALK_1, _T_WALK_1,
    _T_STAND, _T_STAND, _T_STAND,
    _T_BLINK,
    _T_STAND,
)

_SLEEP = (_T_SLEEP_0, _T_SLEEP_1, _T_SLEEP_2, _T_SLEEP_3)
_REACT = (_T_REACT,)

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
