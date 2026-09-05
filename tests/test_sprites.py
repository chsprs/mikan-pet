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
        self.assertNotEqual(mikan, byte)
        self.assertNotEqual(mikan, mochi)
        self.assertNotEqual(byte, mochi)

    def test_walk_only_shifts_body_and_alternates_legs(self) -> None:
        first, second = (frame.rectangles for frame in FRAMES[Pose.WALK])
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[0].y + 1, second[0].y)
        self.assertEqual((11, 18), (second[12].x, second[13].x))

    def test_sleep_closed_eyes_are_dark_two_by_one_rectangles(self) -> None:
        eyes = [rect for rect in FRAMES[Pose.SLEEP][0].rectangles if rect.role is ColorRole.DARK]
        self.assertEqual([(2, 1), (2, 1)], [(rect.width, rect.height) for rect in eyes])

    def test_react_replaces_ears_with_raised_ears(self) -> None:
        ears = [rect for rect in FRAMES[Pose.REACT][0].rectangles if rect.x in (10, 20) and rect.width == 4 and rect.height == 5]
        self.assertEqual([(10, 4), (20, 4)], [(rect.x, rect.y) for rect in ears])

    def test_sleep_pose_has_four_animated_frames_with_z_indicators(self) -> None:
        sleep_frames = FRAMES[Pose.SLEEP]
        self.assertEqual(4, len(sleep_frames))
        self.assertGreater(len(sleep_frames[3].rectangles), len(sleep_frames[0].rectangles))


if __name__ == "__main__":
    unittest.main()
