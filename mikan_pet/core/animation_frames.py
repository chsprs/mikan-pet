"""Hand-pixelled 32x32 cat frames composed from shared parts.

Every frame faces right; the renderer mirrors it for left. Parts are pasted
whole, never scaled or rotated, so the face and markings keep their exact
shape in every pose.

Characters: X outline, O body, S shade/stripes, B light belly, P pink,
W eye color, Z accent (yarn, sleep Zs, music notes), '.' transparent.
While painting, ',' erases a pixel back to transparent.
"""
from mikan_pet.core.types import Pose


# Full cycles remain 1440ms (activities), 1080ms (jump/stretch), 720ms (landing).
FRAME_INTERVAL_MS = {
    Pose.GROOM: 120, Pose.STRETCH: 120, Pose.SCRATCH: 120,
    Pose.TAIL: 120, Pose.LOOK: 180, Pose.JUMP: 90,
    Pose.MUSIC: 180, Pose.YAWN: 120, Pose.SIT: 180,
    Pose.PLAY: 120, Pose.CARRIED: 180, Pose.LAND: 90,
}
YARN_X = (26, 26, 26, 27, 27, 26, 25, 25, 26, 27, 27, 26)
# Accent pixels in these poses float beside the cat and must never be mirrored.
OVERLAY_POSES = frozenset({Pose.SLEEP, Pose.MUSIC})
GROUND_Y = 29
SIZE = 32

Grid = list[str]


def _blank() -> list[list[str]]:
    return [["."] * SIZE for _ in range(SIZE)]


def _paint(canvas: list[list[str]], x: int, y: int, rows) -> None:
    for dy, row in enumerate(rows):
        for dx, char in enumerate(row):
            if char == ".":
                continue
            if not (0 <= x + dx < SIZE and 0 <= y + dy < SIZE):
                raise ValueError("Animation paint outside 32x32 frame")
            canvas[y + dy][x + dx] = "." if char == "," else char


def _freeze(canvas: list[list[str]]) -> Grid:
    return ["".join(row) for row in canvas]


def _shift(grid: Grid, dx: int = 0, dy: int = 0) -> Grid:
    canvas = _blank()
    for y, row in enumerate(grid):
        for x, char in enumerate(row):
            if char != ".":
                if not (0 <= x + dx < SIZE and 0 <= y + dy < SIZE):
                    raise ValueError("Animation silhouette would be clipped")
                canvas[y + dy][x + dx] = char
    return _freeze(canvas)


def _squash(grid: Grid, row: int) -> Grid:
    """Drop one body row; everything above it settles down by one pixel."""
    if any(char != "." for char in grid[0]):
        raise ValueError("Squash would need a row above the frame")
    return ["." * SIZE] + grid[:row] + grid[row + 1:]


def _stretch(grid: Grid, row: int) -> Grid:
    """Repeat one row; everything above it rises by one pixel."""
    if any(char != "." for char in grid[0]):
        raise ValueError("Stretch would push pixels out of the frame")
    return grid[1:row + 1] + [grid[row]] + grid[row + 1:]


# ---------------------------------------------------------------- head
# A 15x11 three-quarter head. Eyes and mouth are painted into fixed slots.
_HEAD = (
    ".X...........X.",
    "XPX.........XPX",
    "XPOX.......XOPX",
    "XPPOXXXXXXXOPPX",
    "XOOOOOSOSOOOOOX",
    "XOOOOOOSOOOOOOX",
    "XOOOOOOOOOOOOOX",
    "XOOOOOOOOOOOOOX",
    "XSOOOOOPOOOOOSX",
    ".XOOOOXOXOOOOX.",
    "..XXXXXXXXXXX..",
)
# Two rows painted at head columns 2-5 and 9-12, starting on head row 6.
_EYES = {
    "open": ("OWXO", "OWXO"),
    "back": ("OXWO", "OXWO"),
    "turn": ("OOWX", "OOWX"),
    "turn_back": ("XWOO", "XWOO"),
    "closed": ("OOOO", "OXXO"),
    "happy": ("OXXO", "XOOX"),
}
# Rows 8-10 of head columns 5-9: nose, mouth and chin.
_MOUTHS = {
    "closed": ("OOPOO", "OXOXO", "XXXXX"),
    "tongue": ("OOPOO", "OXOXO", "XXPXX"),
    "small": ("OOPOO", "OXPXO", "XXXXX"),
    "open": ("OXPXO", "XPPPX", "XXXXX"),
}
# The back ear flicks down one pixel; its base stays on the head.
_EAR_TWITCH = (",,,,,", ",X,,,", "XPXX.", "XPPOX")


def _head(canvas, x: int, y: int, *, eyes="open", mouth="closed", ears="up", whiskers=True) -> None:
    _paint(canvas, x, y, _HEAD)
    _paint(canvas, x + 2, y + 6, _EYES[eyes])
    _paint(canvas, x + 9, y + 6, _EYES[eyes])
    _paint(canvas, x + 5, y + 8, _MOUTHS[mouth])
    if ears == "twitch":
        _paint(canvas, x, y, _EAR_TWITCH)
    elif ears == "perk":
        _paint(canvas, x + 1, y - 1, ["X"])
        _paint(canvas, x + 13, y - 1, ["X"])
    if whiskers:
        _paint(canvas, x - 2, y + 7, ["XX"])
        _paint(canvas, x + 15, y + 7, ["XX"])
        _paint(canvas, x - 1, y + 9, ["XX"])
        _paint(canvas, x + 14, y + 9, ["XX"])


# ---------------------------------------------------------------- sitting
_SIT_HEAD = (11, 10)
_SIT_BODY = (
    "............XOOOOOBBBBBX........",
    "...........XOOOOOOBBBBBX........",
    "..........XOOOOOOOBBBBBX........",
    ".........XOOSOOOOOBBBBBX........",
    ".........XOSOOOOOXBBXBBX........",
    "........XOOSOOOOOXBBXBBX........",
    "........XOOOOOOOOXBBXBBX........",
    "........XOOOOOOOOXBBXBBX........",
    "........XOOOSOOOOXOOXOOX........",
    ".........XXXXXXXXXXXXXXX........",
)
# Lifting the near forepaw closes the chest and leaves only the far leg standing.
_NEAR_LEG_LIFTED = (20, 24, ("XXXX", "X,,,", "X,,,", "X,,,", "X,,,", "X,,,"))
# Tails join the haunch at its lower back; each is (x, y, rows).
_TAILS = {
    "curl": (2, 23, (".XX....", "XOOX...", "XOSX...", ".XOX...",
                     ".XOOXXX", "..XOOOS", "...XXXX")),
    "flick": (2, 22, ("..XX...", ".XOOX..", ".XOX...", "XOSX...", ".XOX...",
                      ".XOOXXX", "..XOOOS", "...XXXX")),
    "up": (4, 13, (".XXX.", "XOOOX", "XOXX.", "XOX..", "XOX..", "XSX..",
                   "XOX..", "XOX..", "XSX..", "XOOX.", ".XOOX", "..XOOX",
                   "...XOO", "....XO")),
    "mid": (1, 18, ("..XX....", ".XOOX...", ".XOX....", "XOX.....", "XOX.....",
                    "XSX.....", "XOOX....", ".XOOX...", "..XOOXX.", "...XOOOX",
                    "....XOOO", ".....XXX")),
    "low": (0, 27, (".XXXXXXXX", "XOOSOOSOO", ".XXXXXXXX")),
}


def _sit(*, eyes="open", mouth="closed", ears="up", tail="curl", head_dy=0, paw=None, legs="down") -> Grid:
    canvas = _blank()
    _paint(canvas, 0, 20, _SIT_BODY)
    tail_x, tail_y, tail_rows = _TAILS[tail]
    _paint(canvas, tail_x, tail_y, tail_rows)
    if legs == "lifted":
        _paint(canvas, *_NEAR_LEG_LIFTED)
    head_x, head_y = _SIT_HEAD
    _head(canvas, head_x, head_y + head_dy, eyes=eyes, mouth=mouth, ears=ears)
    if paw is not None:
        _paint(canvas, *paw)
    return _freeze(canvas)


# A raised forepaw, drawn over the chin or cheek.
_PAW_MOUTH = (19, 19, (".XXX.", "XBBBX", "XBBBX", ".XBBX", ".XBBX"))
_PAW_CHEEK = (20, 17, (".XXX.", "XBBBX", "XBBBX", ".XBBX", ".XBBX", "..XBX", "..XBX"))
# A hind paw reaching the ear; the haunch below stays connected.
_SCRATCH_LOW = (6, 17, (".XXX.", "XBBBX", "XOOOX", ".XOOX", ".XOOX", "..XOX",
                        "..XOOX", "...XOX"))
_SCRATCH_HIGH = (6, 15, (".XXX.", "XBBBX", "XOOOX", ".XOOX", ".XOOX", "..XOX",
                         "..XOX", "..XOOX", "...XOOX", "....XOX"))

# Crouches drop a row from the chest; airborne frames hang the legs one row longer.
_CHEST_ROW = 22
_LEG_ROW = 26


def _crouch(grid: Grid) -> Grid:
    return _squash(grid, _CHEST_ROW)


def _airborne(grid: Grid, height: int) -> Grid:
    """Raise the head by ``height`` pixels; the first pixel only lets the legs dangle."""
    return _shift(_stretch(grid, _LEG_ROW), dy=1 - height)


# ---------------------------------------------------------------- walking
_WALK_TORSO = (
    "...XXXXXXXXXXXXX...",
    "..XOOSOOOSOOOOOOX..",
    ".XOOSOOOSOOOOOOBBX.",
    "XOOOOOOOOOOOOOBBBBX",
    "XOOOOOOOOOOOOOOBBBX",
    ".XXOOOOOOOOOOOOOOX.",
)
_WALK_TAIL = ("..XX.", ".XOOX", ".XOX.", "XOOX.", "XOX..", "XOX..", "XOOX.", ".XOOX")
# (near hind, near front), (far hind, far front) for contact, passing, contact, passing.
_WALK_LEGS = (
    (("back", "fwd"), ("fwd", "back")),
    (("lift", "down"), ("down", "lift")),
    (("fwd", "back"), ("back", "fwd")),
    (("down", "lift"), ("lift", "down")),
)


def _leg(kind: str, height: int, fill: str) -> tuple[str, ...]:
    """A leg from the torso's lower edge to the ground, resting at column 1."""
    body = f"X{fill}{fill}X"
    upper = (height - 1) // 2
    lower = height - 1 - upper
    if kind == "down":
        return ("." + body + ".",) * (height - 1) + (".XXXX.",)
    if kind == "fwd":
        return ("." + body + ".",) * upper + (".." + body,) * lower + ("..XXXX",)
    if kind == "back":
        return ("." + body + ".",) * upper + (body + "..",) * lower + ("XXXX..",)
    if kind == "lift":
        return ("." + body + ".",) * (height - 2) + (".XXXX.",)
    raise ValueError(kind)


def _walk(phase: int) -> Grid:
    canvas = _blank()
    top = 19 - phase % 2
    bottom = top + 5
    height = GROUND_Y - bottom + 1
    (near_hind, near_front), (far_hind, far_front) = _WALK_LEGS[phase]
    for x, kind in ((6, far_hind), (16, far_front)):
        _paint(canvas, x, bottom, _leg(kind, height, "S"))
    _paint(canvas, 3, top, _WALK_TORSO)
    for x, kind in ((3, near_hind), (13, near_front)):
        _paint(canvas, x, bottom, _leg(kind, height, "O"))
    _paint(canvas, 0, top - 6, _WALK_TAIL)
    _head(canvas, 14, top - 9)
    return _freeze(canvas)


# ---------------------------------------------------------------- stretching
# A play bow: rump and tail high, chest low, forepaws reaching past the chin.
_BOW_DEEP = (
    ".XX.............................",
    "XOOX............................",
    "XOX.XXXX........................",
    "XOXXOOOOXX......................",
    ".XOOOSOOOOXX....................",
    "..XOSOOOOOOOXX..................",
    "..XOOOOOOOOOOOXX................",
    "..XOOOOOOOOOOOOOXX..............",
    "..XOOOXXOOOOOOOOOOX.............",
    "..XOOX.XXOOOOOOOOOOX............",
    "..XOOX...XXXOOOOOOOX............",
    "..XOOX.....XOOOOOOOX............",
    "..XOOX.....XOOOOOOX.............",
    "..XOOX......XOOOOOXXXXXXXXXXXX..",
    "..XOOX......XOOOOOOOOOOOOOOOOOX.",
    "..XXXX.......XXXXXXXXXXXXXXXXX..",
)
_BOW_HALF = (
    "................................",
    "................................",
    "..XX............................",
    ".XOOX...........................",
    ".XOX..XXXX......................",
    "XOX.XXOOOOXXX...................",
    "XOOXOOSOOSOOOXX.................",
    ".XOOSOOSOOOOOOOXX...............",
    "..XOOOOOOOOOOOOOOX..............",
    "..XOOOOOOOOOOOOOOOX.............",
    "..XOOOXXXOOOOOOOOOX.............",
    "..XOOX...XOOOOOOOOX.............",
    "..XOOX...XOOOOOOOX..............",
    "..XOOX....XOOOOOOXXXXXXX........",
    "..XOOX....XOOOOOOOOOOOOOX.......",
    "..XXXX.....XXXXXXXXXXXXX........",
)


def _bow(deep: bool) -> Grid:
    canvas = _blank()
    _paint(canvas, 0, 14, _BOW_DEEP if deep else _BOW_HALF)
    _head(canvas, 15, 17 if deep else 15, eyes="closed")
    return _freeze(canvas)


# ---------------------------------------------------------------- sleeping
# Curled up with the tail wrapped along the floor and tucked under the chin.
_SLEEP_BODY = (
    "......XXXXXXX.......",
    "....XXOOSOOSOXX.....",
    "...XOOSOOSOOOOOX....",
    "..XOOOOOOOOOOOOOX...",
    ".XOOOOOOOOOOOOOOOX..",
    ".XOOOOOOOOOOOOOOOOX.",
    "XOOXXXXXXXXXXOOOOOX.",
    "XOSSOSSOSSOSSXOOOOX.",
    "XOOSSOSSOSSOSXOOOOX.",
    ".XXXXXXXXXXXXXXXXXX.",
)
# Small and large Z glyphs: the diagonal always runs from top right to bottom left.
_Z_SMALL = ("ZZZ", "..Z", ".Z.", "ZZZ")
_Z_LARGE = ("ZZZZ", "...Z", "..Z.", ".Z..", "ZZZZ")
# Each Z rises along this path; a second one follows half a cycle behind.
_Z_PATH = ((25, 14, _Z_SMALL), (26, 12, _Z_SMALL), (26, 10, _Z_LARGE), (27, 8, _Z_LARGE),
           (27, 6, _Z_LARGE), (28, 4, _Z_LARGE), (28, 2, _Z_LARGE), None)


def _sleep(frame: int) -> Grid:
    canvas = _blank()
    # Breathing in lifts the back by one pixel; the belly stays on the ground.
    inhale = frame in (2, 3, 4, 5)
    body = _SLEEP_BODY[:3] + _SLEEP_BODY[2:] if inhale else _SLEEP_BODY
    _paint(canvas, 2, GROUND_Y + 1 - len(body), body)
    _head(canvas, 15, 19, eyes="closed")
    for offset in (0, 4):
        step = _Z_PATH[(frame + offset) % 8]
        if step is not None:
            x, y, glyph = step
            _paint(canvas, x, y, glyph)
    return _freeze(canvas)


# ---------------------------------------------------------------- carried
_CARRIED_HEAD = (11, 7)
_CARRIED_UPPER = (
    "..XOOOOOOBBBOX...",
    ".XOXOOOOBBBXOX...",
    ".XOXOOOOBBBXOX...",
    ".XOXOOOOBBBXOX...",
    ".XBXOOOOBBBXBX...",
    ".XXXOOOOOOOXXX...",
)
_CARRIED_LOWER = (
    "...XOOSOOSOOX....",
    "...XOOOOOOOOX....",
    "..XOOXOOOOXOOX...",
    "..XOOXXOOXXOOX...",
    "..XXXX.XOX.XXXX..",
    "........X........",
)


def _carried(sway: int) -> Grid:
    canvas = _blank()
    _paint(canvas, 11 + sway, 23, _CARRIED_LOWER)
    _paint(canvas, 11, 17, _CARRIED_UPPER)
    _head(canvas, *_CARRIED_HEAD, eyes="closed")
    return _freeze(canvas)


# ---------------------------------------------------------------- yarn & notes
_YARN = ((".XXX.", "XZPZX", "XZZZX", ".XXX."), (".XXX.", "XZZZX", "XZPZX", ".XXX."))
_SWAT = (20, 23, ("XXX....", "XBBXX..", ".XBBBX.", "..XBBBX", "...XXX."))
_NOTE = (".Z..", ".ZZ.", ".Z.Z", "ZZ..", "ZZ..")
# Two notes drift up in turn; the second rises further left, clear of the ear.
_NOTE_PATHS = (((27, 6), (27, 5), (28, 3), (28, 2)), ((24, 4), (24, 3), (25, 1), (25, 0)))


def _with(grid: Grid, x: int, y: int, rows) -> Grid:
    canvas = [list(row) for row in grid]
    _paint(canvas, x, y, rows)
    return _freeze(canvas)


def pose_grids() -> dict[Pose, tuple[Grid, ...]]:
    sit = _sit()
    blink = _sit(eyes="closed")
    flick = _sit(tail="flick")
    look_back, look_turn = _sit(eyes="turn_back"), _sit(eyes="turn")
    glance_back = _sit(eyes="back")

    paw_mouth = _sit(eyes="closed", legs="lifted", paw=_PAW_MOUTH)
    lick = _sit(eyes="closed", mouth="tongue", legs="lifted", paw=_PAW_MOUTH)
    wipe = _sit(eyes="closed", legs="lifted", paw=_PAW_CHEEK)

    scratch_low = _sit(eyes="closed", tail="low", paw=_SCRATCH_LOW)
    scratch_high = _sit(eyes="closed", tail="low", head_dy=1, paw=_SCRATCH_HIGH)

    tail_mid, tail_low, tail_up = _sit(tail="mid"), _sit(tail="low"), _sit(tail="up")
    ear_twitch = _sit(tail="up", ears="twitch")

    crouch = _crouch(sit)
    jump = (sit, crouch, _airborne(sit, 1), _airborne(sit, 3), _airborne(sit, 5),
            _airborne(sit, 6), _airborne(sit, 6), _airborne(sit, 5), _airborne(sit, 3),
            _airborne(sit, 1), crouch, sit)

    happy = _sit(eyes="happy", tail="up")
    nod_down = _sit(eyes="happy", tail="up", head_dy=1)
    music = tuple(
        _with(base, *_NOTE_PATHS[index // 4][index % 4], _NOTE)
        for index, base in enumerate((happy, nod_down, nod_down, happy,
                                      happy, nod_down, nod_down, happy))
    )

    yawn_small = _sit(eyes="closed", mouth="small")
    yawn_open = _sit(eyes="closed", mouth="open", head_dy=-1)

    play = []
    for step, ball_x in enumerate(YARN_X):
        if step in (3, 4, 8, 9):
            cat = _sit(eyes="turn", legs="lifted", paw=_SWAT, tail="flick")
        elif step in (1, 2, 7):
            cat = _crouch(_sit(eyes="turn"))
        else:
            cat = _sit(eyes="turn")
        play.append(_with(cat, ball_x, 26, _YARN[ball_x % 2]))

    carried = _carried(0)
    return {
        Pose.WALK: tuple(_walk(phase) for phase in range(4)),
        Pose.IDLE: (sit, sit, sit, flick, flick, sit, sit, sit, blink, sit),
        Pose.SLEEP: tuple(_sleep(frame) for frame in range(8)),
        Pose.REACT: (_sit(eyes="happy", mouth="small", ears="perk", tail="up"),),
        Pose.GROOM: (sit, blink, paw_mouth, lick, paw_mouth, lick,
                     lick, wipe, wipe, paw_mouth, blink, sit),
        Pose.STRETCH: (sit, crouch, _bow(False), _bow(True), _bow(True),
                       _bow(True), _bow(False), crouch, sit),
        Pose.SCRATCH: (sit, scratch_low, scratch_high, scratch_low,
                       scratch_high, scratch_low, scratch_high, scratch_low,
                       scratch_high, scratch_low, blink, sit),
        Pose.TAIL: (sit, tail_mid, tail_low, tail_low, tail_mid, sit,
                    tail_up, ear_twitch, tail_up, tail_mid, sit, sit),
        Pose.LOOK: (sit, look_back, look_back, sit, look_turn, look_turn, sit, sit),
        Pose.JUMP: jump,
        Pose.MUSIC: music,
        Pose.YAWN: (sit, blink, blink, yawn_small, yawn_open, yawn_open,
                    yawn_open, yawn_open, yawn_small, blink, blink, sit),
        Pose.SIT: (sit, sit, glance_back, glance_back, sit, look_turn, blink, sit),
        Pose.PLAY: tuple(play),
        Pose.CARRIED: (carried, _carried(-1), _carried(1)),
        Pose.LAND: (carried, _shift(carried, dy=1), _airborne(sit, 2), _airborne(sit, 1),
                    _crouch(blink), _crouch(blink), blink, sit),
    }
