import unittest

from mikan_pet.core.sprites import (
    ColorRole,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    FRAMES,
    SKINS,
    frame_count,
    rasterize_frame,
    validate_registry,
)
from mikan_pet.core.types import Direction, Pose, SkinId


class SpriteRegistryTests(unittest.TestCase):
    def test_every_skin_and_pose_is_complete(self) -> None:
        self.assertEqual([], validate_registry())
        self.assertEqual(set(SkinId), set(SKINS))
        for pose in Pose:
            self.assertGreaterEqual(frame_count(pose), 1)
        self.assertGreaterEqual(frame_count(Pose.WALK), 2)
        self.assertGreaterEqual(frame_count(Pose.IDLE), 10)
        self.assertGreaterEqual(frame_count(Pose.SLEEP), 2)
        for skin in SKINS.values():
            self.assertNotIn("#FF00FF", skin.palette.values())

    def test_raster_has_fixed_dimensions(self) -> None:
        rows = rasterize_frame(SkinId.MIKAN, Pose.WALK, 0, Direction.RIGHT)
        self.assertEqual(FRAME_HEIGHT, len(rows))
        self.assertTrue(all(len(row) == FRAME_WIDTH for row in rows))

    def test_left_frame_is_horizontal_mirror(self) -> None:
        right = rasterize_frame(SkinId.MOCHI, Pose.REACT, 0, Direction.RIGHT)
        left = rasterize_frame(SkinId.MOCHI, Pose.REACT, 0, Direction.LEFT)
        self.assertEqual(tuple(tuple(reversed(row)) for row in right), left)

    def test_skin_palettes_are_visibly_distinct(self) -> None:
        mikan = rasterize_frame(SkinId.MIKAN, Pose.IDLE, 0, Direction.RIGHT)
        byte = rasterize_frame(SkinId.BYTE, Pose.IDLE, 0, Direction.RIGHT)
        mochi = rasterize_frame(SkinId.MOCHI, Pose.IDLE, 0, Direction.RIGHT)
        ash = rasterize_frame(SkinId.ASH, Pose.IDLE, 0, Direction.RIGHT)
        self.assertNotEqual(mikan, byte)
        self.assertNotEqual(mikan, mochi)
        self.assertNotEqual(mikan, ash)
        self.assertNotEqual(byte, mochi)
        self.assertNotEqual(byte, ash)
        self.assertNotEqual(mochi, ash)

    def test_walk_only_shifts_body_and_alternates_legs(self) -> None:
        walk_frames = FRAMES[Pose.WALK]
        self.assertEqual(4, len(walk_frames))
        # Frame 1 bobs body up compared to Frame 0
        ears_f0 = [r for r in walk_frames[0].rectangles if r.role is ColorRole.DARK and r.y == 13]
        ears_f1 = [r for r in walk_frames[1].rectangles if r.role is ColorRole.DARK and r.y == 12]
        self.assertTrue(len(ears_f0) > 0)
        self.assertTrue(len(ears_f1) > 0)
        # Frame 0 and Frame 2 have distinct alternating paw coordinates
        paws_f0 = [r for r in walk_frames[0].rectangles if r.y >= 27]
        paws_f2 = [r for r in walk_frames[2].rectangles if r.y >= 27]
        self.assertNotEqual(paws_f0, paws_f2)

    def test_sleep_closed_eyes_are_dark_rectangles(self) -> None:
        eyes = [rect for rect in FRAMES[Pose.SLEEP][0].rectangles if rect.role is ColorRole.DARK and rect.y == 20]
        self.assertTrue(any(rect.width >= 3 for rect in eyes))

    def test_react_replaces_ears_with_raised_ears(self) -> None:
        react_ears = [rect for rect in FRAMES[Pose.REACT][0].rectangles if rect.role is ColorRole.COLLAR and rect.y == 13]
        stand_ears = [rect for rect in FRAMES[Pose.IDLE][0].rectangles if rect.role is ColorRole.COLLAR and rect.y == 13]
        self.assertEqual(2, len(react_ears))
        self.assertEqual(0, len(stand_ears))

    def test_sleep_pose_has_four_animated_frames_with_z_indicators(self) -> None:
        sleep_frames = FRAMES[Pose.SLEEP]
        self.assertEqual(4, len(sleep_frames))
        self.assertGreater(len(sleep_frames[3].rectangles), len(sleep_frames[0].rectangles))


if __name__ == "__main__":
    unittest.main()
