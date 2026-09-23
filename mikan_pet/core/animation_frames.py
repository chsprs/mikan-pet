"""Small, hand-pixelled motions composed from the original cat silhouette.

All frames share a 32x32 canvas. Heads are translated as complete pieces;
no interpolation, scaling, or rotation can distort the face or skin markings.
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


def _paint(base: list[str], x: int, y: int, rows: list[str]) -> list[str]:
    grid = [list(row) for row in base]
    for dy, row in enumerate(rows):
        for dx, char in enumerate(row):
            if not (0 <= x + dx < 32 and 0 <= y + dy < 32):
                raise ValueError("Animation paint outside 32x32 frame")
            grid[y + dy][x + dx] = char
    return ["".join(row) for row in grid]


def _shift(base: list[str], dx: int = 0, dy: int = 0) -> list[str]:
    grid = [list('.' * 32) for _ in range(32)]
    for y, row in enumerate(base):
        for x, char in enumerate(row):
            if char != '.':
                if not (0 <= x + dx < 32 and 0 <= y + dy < 32):
                    raise ValueError("Animation silhouette would be clipped")
                grid[y + dy][x + dx] = char
    return ["".join(row) for row in grid]


def _head(base: list[str], dy: int) -> list[str]:
    # Preserve the full head including ears, whiskers, eyes, and tabby marks.
    grid = _paint(base, 10, 13, ['.' * 17] * 11)
    if dy < 0:
        grid = _paint(grid, 15, 23, [base[23][15:22]])
    return _paint(grid, 10, 13 + dy, [row[10:27] for row in base[13:24]])


def _tail(base: list[str], raised: bool) -> list[str]:
    grid = _paint(base, 4, 22, ['.' * 9] * 8)
    if raised:
        rows = ['..XXX....', '.XOSOX...', '.XOSOX...', '..XOSX...',
                '...XOSX..', '....XOSXX', '.....XXOO', '.......XX']
    else:
        rows = ['.........', '.........', '.........', '.........',
                '..XXXXX..', '.XOSSSOXX', '..XXXOOOO', '.....XXXX']
    return _paint(grid, 4, 22, rows)


def extra_grids(stand: list[str], blink: list[str]) -> dict[Pose, tuple[list[str], ...]]:
    # Blink keeps the original muzzle; yawn changes only the mouth pixels.
    yawn_small = _paint(blink, 18, 20, ['XX', 'PX'])
    yawn_open = _paint(blink, 17, 20, ['XXXX', 'XPPX', '.XX.'])
    # A single forepaw reaches the mouth, then wipes the cheek.
    lick = _paint(blink, 18, 22, ['.XXX', 'XBBX', 'XOOX', '.XOX', '.XOX', '.XXX'])
    lick_tongue = _paint(lick, 19, 21, ['P'])
    wipe = _paint(blink, 20, 19, ['.XX', 'XBB', 'XOO', 'XOX', 'XOX', '.XX'])
    # The hind paw stays connected at the hip while reaching the ear.
    scratch_low = _paint(stand, 10, 23, ['..XXX', '.XOOX', 'XOOOX', 'XOOXX', '.XXX.'])
    scratch_high = _paint(stand, 10, 21, ['..XX.', '.XBBX', '.XOOX', 'XOOOX', 'XOOXX', '.XXX.'])
    tail_low, tail_high = _tail(stand, False), _tail(stand, True)
    ear_twitch = _paint(tail_high, 12, 13, ['.XX..', 'XOPXX'])
    look_left = _paint(stand, 15, 18, ['WOOOWOO'])
    look_right = _paint(stand, 15, 18, ['OOWOOOW'])
    # Bow forward into a stretch: head keeps its exact size, forelegs extend.
    stretch = _head(blink, -1)
    stretch = _paint(stretch, 13, 23, ['XSSOOBBX.', 'XSSOOBBX.', 'XSOOBBBX.',
                                     'XOOOBBBX.', 'XOOXOOOX.', 'XOOXOOOX.', 'XXXXXXXX.'])
    stretch_deep = _paint(stretch, 14, 27, ['OOXXOOOX', 'OOXXOOOX', 'XXXXXXXX'])
    stretch_start = _head(blink, 0)
    crouch = _head(blink, 1)
    crouch = _paint(crouch, 13, 25, ['XSSOBBBX', 'XSOOBBBX', 'XOOOBBBX', 'XOOXOOOX', 'XXXXXXXX'])
    # Jump translates the WHOLE cat, never stretches or separates limbs.
    jump = (stand, crouch, stand, _shift(stand, dy=-1), _shift(stand, dy=-2),
            _shift(stand, dy=-3), _shift(stand, dy=-4), _shift(stand, dy=-4),
            _shift(stand, dy=-3), _shift(stand, dy=-2), _shift(stand, dy=-1), crouch)
    # Hanging neck and head are fixed; only the relaxed lower body sways.
    carried = ['.' * 32 for _ in range(32)]
    carried = _paint(carried, 10, 9, [row[10:27] for row in blink[13:24]])
    body = ['....XSSOBBX...', '...XXSOOBBXX..', '..XOOXOOBXOOX.',
            '...XXXOOBXXX..', '...XSOOOBBX...', '..XOSXOOOBX...',
            '..XOSXXOXXOX..', '...XSXXOXXOX..', '....XXXX..XX..']
    carried = _paint(carried, 10, 20, body)
    carried_left = _paint(carried, 0, 24, ['.' * 32] * 8)
    carried_left = _paint(carried_left, 9, 24, body[4:])
    carried_right = _paint(carried, 0, 24, ['.' * 32] * 8)
    carried_right = _paint(carried_right, 11, 24, body[4:])
    # Yarn is a separate prop, nudged by an extended forepaw during a small pounce.
    play_frames = []
    for step, ball_x in enumerate(YARN_X):
        cat = crouch if step in (1, 2, 7) else stand
        if step in (3, 4, 8, 9):
            cat = _shift(stand, dx=1, dy=-1)
        if step in (3, 4, 5, 8, 9, 10):
            cat = _paint(cat, 20, 26, ['XXXX...', 'XOOOXXX', '.XXOOOX', '...XXXX'])
        yarn = ['.XXX.', 'XZPZX', 'XZZZX', '.XXX.'] if ball_x % 2 else ['.XXX.', 'XZZZX', 'XZPZX', '.XXX.']
        cat = _paint(cat, ball_x, 27, yarn)
        play_frames.append(cat)
    return {
        Pose.GROOM: (stand, blink, lick, lick_tongue, lick, lick_tongue,
                     lick, wipe, wipe, lick, blink, stand),
        Pose.STRETCH: (stand, stretch_start, stretch, stretch_deep, stretch_deep,
                       stretch_deep, stretch, stretch_start, stand),
        Pose.SCRATCH: (stand, scratch_low, scratch_high, scratch_low,
                       scratch_high, scratch_low, scratch_high, scratch_low,
                       scratch_high, scratch_low, stand, stand),
        Pose.TAIL: (stand, stand, tail_low, tail_low, stand, tail_high,
                    ear_twitch, tail_high, tail_high, stand, stand, stand),
        Pose.LOOK: (stand, look_left, look_left, stand, look_right, look_right, stand, stand),
        Pose.JUMP: jump,
        Pose.MUSIC: (stand, _head(stand, 1), _head(stand, 1), stand,
                     _head(stand, -1), _head(stand, -1), stand, blink),
        Pose.YAWN: (stand, blink, blink, yawn_small, yawn_open, yawn_open,
                    yawn_open, yawn_open, yawn_small, blink, blink, stand),
        Pose.SIT: (stand, stand, look_left, stand, look_right, stand, blink, stand),
        Pose.PLAY: tuple(play_frames),
        Pose.CARRIED: (carried, carried_left, carried_right),
        Pose.LAND: (carried, _shift(carried, dy=1), _head(blink, -1),
                    stand, crouch, crouch, blink, stand),
    }
