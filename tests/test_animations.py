"""Behavior and anatomy contracts for the additional pet animations."""
import unittest
from dataclasses import replace

from mikan_pet.core.animation_frames import (
    _HEAD, _Z_LARGE, _Z_SMALL, FRAME_INTERVAL_MS, GROUND_Y, OVERLAY_POSES, YARN_X, pose_grids,
)
from mikan_pet.core.sprites import SKINS, frame_count, rasterize_frame
from mikan_pet.core.state import BehaviorDurations, PetController, PetState
from mikan_pet.ui.pet_window import AnimationClock
from mikan_pet.core.sprites import ColorRole
from mikan_pet.core.types import Direction, MotionMode, Point, Pose, Size, SkinId, WorkArea

AREA = WorkArea(-1000, -1000, 1000, 1000)
SIZE = Size(144, 128)


def controller(pose=Pose.IDLE, motion=MotionMode.STOPPED):
    return PetController(PetState(Point(0, 0), Direction.RIGHT, motion, pose,
                                  SkinId.MIKAN, True, True),
                         BehaviorDurations(walk_ms=300, idle_ms=100, sleep_ms=300,
                                           activity_ms=300, stretch_ms=300,
                                           jump_ms=300, land_ms=300))


class AnimationBehaviorTests(unittest.TestCase):
    def test_all_ambient_animations_are_reachable_with_and_without_music(self):
        for playing in (False, True):
            pet = controller()
            pet.set_music_playing(playing)
            observed = set()
            for _ in range(1500):
                observed.add(pet.tick(100, AREA, SIZE).pose)
                self.assertEqual(Point(0, 0), pet.state.position)
            expected = set(pet.REST_ACTIVITIES) | {Pose.SIT, Pose.YAWN, Pose.SLEEP, Pose.STRETCH}
            if playing:
                expected.add(Pose.MUSIC)
            self.assertTrue(expected <= observed, expected - observed)
            if not playing:
                self.assertNotIn(Pose.MUSIC, observed)

    def test_drag_from_each_ambient_pose_lands_then_restores_pose_and_timer(self):
        ambient = set(Pose) - {Pose.CARRIED, Pose.LAND, Pose.REACT, Pose.JUMP}
        for mode in (MotionMode.STOPPED, MotionMode.AUTOMATIC):
            for pose in ambient:
                with self.subTest(mode=mode, pose=pose):
                    pet = controller(pose, mode)
                    pet.set_music_playing(True)
                    pet.phase_elapsed_ms = 80
                    pet.begin_drag()
                    pet.begin_drag()  # repeated motion events must not overwrite the saved pose
                    pet.drag_to(Point(-400, 250))
                    self.assertEqual(Pose.CARRIED, pet.state.pose)
                    pet.react(jump=True)
                    self.assertEqual(Pose.CARRIED, pet.tick(2000, AREA, SIZE).pose)
                    self.assertEqual(Point(-400, 250), pet.state.position)
                    pet.end_drag()
                    self.assertEqual(Pose.LAND, pet.state.pose)
                    self.assertEqual(mode, pet.state.motion)
                    pet.tick(300, AREA, SIZE)
                    self.assertEqual(pose, pet.state.pose)
                    self.assertEqual(80, pet.phase_elapsed_ms)

    def test_drag_sway_follows_motion_and_settles_when_pointer_stops(self):
        pet = controller()
        pet.begin_drag()
        pet.drag_to(Point(50, 0))
        self.assertEqual(1, pet.carried_frame)
        pet.drag_to(Point(20, 0))
        self.assertEqual(2, pet.carried_frame)
        pet.tick(200, AREA, SIZE)
        self.assertEqual(0, pet.carried_frame)
        pet.state = replace(pet.state, direction=Direction.LEFT)
        pet.drag_to(Point(50, 0))
        self.assertEqual(2, pet.carried_frame)

    def test_drag_ignores_jitter_but_detects_slow_deliberate_movement(self):
        pet = controller()
        pet.begin_drag()
        for x in (1, 0, 1, 0, 1, 0):
            pet.drag_to(Point(x, 0))
            self.assertEqual(0, pet.carried_frame)
        for x in (1, 2, 3):
            pet.drag_to(Point(x, 0))
        self.assertEqual(1, pet.carried_frame)
        self.assertEqual(Point(3, 0), pet.state.position)

    def test_repeated_click_then_drag_does_not_restore_a_transient_pose(self):
        pet = controller(Pose.SLEEP)
        pet.phase_elapsed_ms = 90
        pet.react(jump=True)
        pet.react(jump=True)
        pet.begin_drag()
        pet.end_drag()
        pet.tick(300, AREA, SIZE)
        self.assertEqual(Pose.SLEEP, pet.state.pose)
        self.assertEqual(90, pet.phase_elapsed_ms)

    def test_pointer_attention_has_cooldown_and_restores_interrupted_phase(self):
        pet = controller()
        pet.phase_elapsed_ms = 40
        pet.look_at(Direction.LEFT)
        self.assertEqual(Pose.LOOK, pet.state.pose)
        self.assertEqual(1, pet.look_frame)
        pet.look_at(Direction.RIGHT)
        self.assertEqual(4, pet.look_frame)
        pet.tick(300, AREA, SIZE)
        self.assertEqual(Pose.IDLE, pet.state.pose)
        self.assertEqual(40, pet.phase_elapsed_ms)
        pet.look_at(Direction.LEFT)
        self.assertEqual(Pose.IDLE, pet.state.pose)

    def test_music_pause_stops_nodding(self):
        pet = controller(Pose.MUSIC)
        pet.set_music_playing(False)
        self.assertEqual(Pose.IDLE, pet.state.pose)

    def test_music_paused_during_drag_or_jump_is_not_resumed_afterward(self):
        for drag in (False, True):
            pet = controller(Pose.MUSIC)
            pet.set_music_playing(True)
            if drag:
                pet.begin_drag()
            else:
                pet.react(jump=True)
            pet.set_music_playing(False)
            if drag:
                pet.end_drag()
            pet.tick(300, AREA, SIZE)
            self.assertEqual(Pose.IDLE, pet.state.pose)

    def test_no_pointer_distraction_during_sleep_yawn_stretch_or_drag(self):
        for pose in (Pose.SLEEP, Pose.YAWN, Pose.STRETCH, Pose.CARRIED, Pose.LAND):
            pet = controller(pose)
            pet.look_at(Direction.LEFT)
            self.assertEqual(pose, pet.state.pose)


class AnimationTimingTests(unittest.TestCase):
    def test_complete_cycles_fit_controller_durations(self):
        durations = BehaviorDurations()
        for pose, interval in FRAME_INTERVAL_MS.items():
            if pose is Pose.CARRIED:
                continue
            expected = {Pose.JUMP: durations.jump_ms, Pose.LAND: durations.land_ms,
                        Pose.STRETCH: durations.stretch_ms}.get(pose, durations.activity_ms)
            self.assertEqual(expected, frame_count(pose) * interval, pose.value)

    def test_one_shot_holds_final_frame_until_controller_transitions(self):
        clock = AnimationClock()
        for pose in (Pose.JUMP, Pose.LAND, Pose.STRETCH, Pose.YAWN):
            frames = frame_count(pose)
            self.assertEqual(frames - 1, clock.advance(pose, 0, frames, phase_elapsed_ms=10000))

    def test_resuming_grooming_restores_visual_phase_after_drag(self):
        pet = controller(Pose.GROOM)
        pet.phase_elapsed_ms = 960
        pet.begin_drag()
        pet.end_drag()
        pet.tick(300, AREA, SIZE)
        clock = AnimationClock()
        self.assertEqual(8, clock.advance(pet.state.pose, 0, frame_count(Pose.GROOM),
                                         phase_elapsed_ms=pet.phase_elapsed_ms))

    def test_jump_advances_in_90ms_steps_and_music_keeps_looping(self):
        clock = AnimationClock()
        self.assertEqual(0, clock.advance(Pose.JUMP, 0, frame_count(Pose.JUMP)))
        self.assertEqual(1, clock.advance(Pose.JUMP, 90, frame_count(Pose.JUMP)))
        self.assertEqual(0, clock.advance(Pose.MUSIC, 0, frame_count(Pose.MUSIC)))
        self.assertEqual(0, clock.advance(Pose.MUSIC, 1440, frame_count(Pose.MUSIC)))


GRIDS = pose_grids()
SIT = GRIDS[Pose.IDLE][0]
# Head block of the sitting cat above the chin, whiskers included: rows 10-19, columns 9-27.
HEAD_ROWS, HEAD_COLS = range(10, 20), slice(9, 28)
# Held up by the scruff, or mid-jump; every other frame stands on the ground line.
AIRBORNE = ({(Pose.JUMP, index) for index in range(3, 9)} | {(Pose.LAND, 0), (Pose.LAND, 2)}
            | {(Pose.CARRIED, index) for index in range(3)})


def head_block(grid, top):
    return [grid[top + row][HEAD_COLS] for row in range(len(HEAD_ROWS))]


def body_points(pose, index, grid):
    points = {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c not in ".Z"}
    if pose is Pose.PLAY:
        ball_x = YARN_X[index]
        points -= {(x, y) for x in range(ball_x, ball_x + 5) for y in range(26, 30)}
    return points


def components(points, diagonal=False):
    pending, found = set(points), []
    steps = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if (dx or dy) and (diagonal or not (dx and dy))]
    while pending:
        stack = [pending.pop()]
        group = set(stack)
        while stack:
            x, y = stack.pop()
            for dx, dy in steps:
                neighbor = (x + dx, y + dy)
                if neighbor in pending:
                    pending.remove(neighbor)
                    group.add(neighbor)
                    stack.append(neighbor)
        found.append(group)
    return found


def normalized(glyph):
    left, top = min(x for x, _ in glyph), min(y for _, y in glyph)
    return {(x - left, y - top) for x, y in glyph}


class AnimationAnatomyTests(unittest.TestCase):
    def test_every_frame_fits_canvas_and_uses_only_existing_palette_roles(self):
        for pose, grids in GRIDS.items():
            self.assertEqual(frame_count(pose), len(grids))
            for index, grid in enumerate(grids):
                with self.subTest(pose=pose, frame=index):
                    self.assertEqual(32, len(grid))
                    self.assertTrue(all(len(row) == 32 for row in grid))
                    for skin in SkinId:
                        right = rasterize_frame(skin, pose, index, Direction.RIGHT)
                        used = {pixel for row in right for pixel in row if pixel}
                        self.assertTrue(used <= set(SKINS[skin].palette.values()))
                        if pose not in OVERLAY_POSES:
                            left = rasterize_frame(skin, pose, index, Direction.LEFT)
                            self.assertEqual(tuple(tuple(reversed(row)) for row in right), left)

    def test_head_and_ears_are_symmetric(self):
        # The old sprite scattered the left ear's pink pixels; both ears must match.
        for row in _HEAD:
            self.assertEqual(row, row[::-1])

    def test_yarn_rolls_without_teleporting_and_jump_preserves_head(self):
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(YARN_X, YARN_X[1:])))
        for index, height in ((2, 1), (3, 3), (4, 5), (5, 6), (6, 6), (7, 5), (8, 3), (9, 1)):
            with self.subTest(frame=index):
                self.assertEqual(head_block(SIT, 10), head_block(GRIDS[Pose.JUMP][index], 10 - height))

    def test_feet_stay_on_the_ground_unless_airborne(self):
        for pose, grids in GRIDS.items():
            for index, grid in enumerate(grids):
                bottom = max(y for _, y in body_points(pose, index, grid))
                with self.subTest(pose=pose, frame=index):
                    if (pose, index) in AIRBORNE:
                        self.assertLess(bottom, GROUND_Y)
                    else:
                        self.assertEqual(GROUND_Y, bottom)

    def test_carried_head_keeps_original_size_ears_and_markings(self):
        sleepy = GRIDS[Pose.IDLE][8]
        for grid in GRIDS[Pose.CARRIED]:
            self.assertEqual(head_block(sleepy, 10), head_block(grid, 7))

    def test_walk_cycle_bobs_and_alternates_legs(self):
        walk = GRIDS[Pose.WALK]
        tops = [min(y for y, row in enumerate(grid) if row.strip(".")) for grid in walk]
        self.assertEqual([tops[0], tops[0] - 1, tops[0], tops[0] - 1], tops)
        self.assertNotEqual([row[:] for row in walk[0][25:]], [row[:] for row in walk[2][25:]])

    def test_body_is_one_connected_silhouette_except_floating_accents(self):
        for pose, grids in GRIDS.items():
            for index, grid in enumerate(grids):
                found = components(body_points(pose, index, grid))
                self.assertEqual(1, len(found), f'Detached pixels in {pose.value} frame {index}')

    def test_accents_float_free_of_the_body_and_only_where_expected(self):
        for pose, grids in GRIDS.items():
            for index, grid in enumerate(grids):
                accents = {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == "Z"}
                if pose not in OVERLAY_POSES | {Pose.PLAY}:
                    self.assertFalse(accents, f'{pose.value} frame {index}')
                elif pose in OVERLAY_POSES:
                    self.assertTrue(accents, f'{pose.value} frame {index} has no Z or note')
                    body = body_points(pose, index, grid)
                    halo = {(x + dx, y + dy) for x, y in accents for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
                    self.assertFalse(halo & body, f'{pose.value} frame {index} accent touches the cat')

    def test_sleep_zs_read_as_z_in_both_directions(self):
        for glyph in (_Z_SMALL, _Z_LARGE):
            middle = [row.index("Z") for row in glyph[1:-1]]
            # The diagonal runs from top right to bottom left, never straight down like an I.
            self.assertEqual(sorted(middle, reverse=True), middle)
            self.assertEqual(len(set(middle)), len(middle))
        for index in range(frame_count(Pose.SLEEP)):
            accent = SKINS[SkinId.MIKAN].palette[ColorRole.PATCH_TWO]
            shapes = {}
            for direction in Direction:
                raster = rasterize_frame(SkinId.MIKAN, Pose.SLEEP, index, direction)
                points = {(x, y) for y, row in enumerate(raster) for x, c in enumerate(row) if c == accent}
                shapes[direction] = sorted(map(sorted, map(normalized, components(points, diagonal=True))))
            self.assertEqual(shapes[Direction.RIGHT], shapes[Direction.LEFT])
