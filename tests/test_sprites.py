import unittest

from mikan_pet.core.sprites import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
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


if __name__ == "__main__":
    unittest.main()
