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

    def test_walk_passing_frames_lift_the_body_and_contacts_swap_legs(self) -> None:
        walk_frames = FRAMES[Pose.WALK]
        self.assertEqual(4, len(walk_frames))
        tops = [min(rect.y for rect in frame.rectangles) for frame in walk_frames]
        self.assertEqual(tops[0] - 1, tops[1])
        self.assertEqual(tops[0], tops[2])
        paws_f0 = [r for r in walk_frames[0].rectangles if r.y >= 27]
        paws_f2 = [r for r in walk_frames[2].rectangles if r.y >= 27]
        self.assertNotEqual(paws_f0, paws_f2)

    def test_sleeping_cat_keeps_its_eyes_closed(self) -> None:
        for frame in FRAMES[Pose.SLEEP]:
            self.assertFalse([rect for rect in frame.rectangles if rect.role is ColorRole.EYE])

    def test_react_perks_ears_and_smiles(self) -> None:
        react_top = min(rect.y for rect in FRAMES[Pose.REACT][0].rectangles)
        idle_top = min(rect.y for rect in FRAMES[Pose.IDLE][0].rectangles)
        self.assertEqual(idle_top - 1, react_top)
        self.assertFalse([rect for rect in FRAMES[Pose.REACT][0].rectangles if rect.role is ColorRole.EYE])

    def test_sleep_breathes_while_zs_rise_in_every_frame(self) -> None:
        sleep_frames = FRAMES[Pose.SLEEP]
        self.assertEqual(8, len(sleep_frames))
        z_layouts = []
        for frame in sleep_frames:
            zs = sorted((r.x, r.y) for r in frame.rectangles if r.role is ColorRole.PATCH_TWO)
            self.assertTrue(zs)
            z_layouts.append(zs)
        for current, following in zip(z_layouts, z_layouts[1:] + z_layouts[:1]):
            self.assertNotEqual(current, following)
        backs = {min(r.y for r in frame.rectangles if r.role is not ColorRole.PATCH_TWO and r.x < 10)
                 for frame in sleep_frames}
        self.assertEqual(2, len(backs))


if __name__ == "__main__":
    unittest.main()
