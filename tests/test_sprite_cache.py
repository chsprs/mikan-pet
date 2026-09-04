import unittest
from unittest.mock import patch

from mikan_pet.core.types import Direction, Pose, SkinId
from mikan_pet.ui.sprite_cache import SpriteCache, tk_color_rows


class SpriteCacheTests(unittest.TestCase):
    def test_transparent_pixels_use_window_key_color(self) -> None:
        rows = ((None, "#112233"), ("#445566", None))
        self.assertEqual(
            ("{#FF00FF #112233}", "{#445566 #FF00FF}"),
            tk_color_rows(rows, "#FF00FF"),
        )

    def test_get_reuses_the_same_zoomed_image_for_a_frame_key(self) -> None:
        factory = _PhotoFactory()
        cache = SpriteCache(factory, scale=4)
        with patch("mikan_pet.ui.sprite_cache.rasterize_frame", return_value=((None,),)) as rasterize:
            first = cache.get(SkinId.MIKAN, Pose.IDLE, 0, Direction.RIGHT)
            second = cache.get(SkinId.MIKAN, Pose.IDLE, 0, Direction.RIGHT)
        self.assertIs(first, second)
        self.assertEqual(1, rasterize.call_count)
        self.assertEqual((4, 4), first.zoom_args)

    def test_clear_with_new_scale_discards_old_image_and_rescales(self) -> None:
        factory = _PhotoFactory()
        cache = SpriteCache(factory, scale=4)
        with patch("mikan_pet.ui.sprite_cache.rasterize_frame", return_value=((None,),)):
            old = cache.get(SkinId.BYTE, Pose.WALK, 1, Direction.LEFT)
            cache.clear(scale=6)
            new = cache.get(SkinId.BYTE, Pose.WALK, 1, Direction.LEFT)
        self.assertIsNot(old, new)
        self.assertEqual((6, 6), new.zoom_args)


class _PhotoFactory:
    def __init__(self) -> None:
        self.created: list[_FakePhoto] = []

    def __call__(self, **kwargs: int) -> "_FakePhoto":
        image = _FakePhoto(kwargs)
        self.created.append(image)
        return image


class _FakePhoto:
    def __init__(self, kwargs: dict[str, int]) -> None:
        self.kwargs = kwargs
        self.put_value: str | None = None
        self.zoom_args: tuple[int, int] | None = None

    def put(self, value: str) -> None:
        self.put_value = value

    def zoom(self, x: int, y: int) -> "_FakePhoto":
        self.zoom_args = (x, y)
        return self


if __name__ == "__main__":
    unittest.main()
