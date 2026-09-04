from collections.abc import Callable, Iterable

from mikan_pet.core.sprites import FRAME_HEIGHT, FRAME_WIDTH, rasterize_frame
from mikan_pet.core.types import Direction, Pose, SkinId


def tk_color_rows(rows: Iterable[Iterable[str | None]], transparent_color: str) -> tuple[str, ...]:
    """Return raster rows in Tk's braced color-list syntax."""
    return tuple(
        "{" + " ".join(transparent_color if color is None else color for color in row) + "}"
        for row in rows
    )


class SpriteCache:
    def __init__(
        self,
        photo_factory: Callable[..., object],
        scale: int = 4,
        transparent_color: str = "#FF00FF",
    ) -> None:
        self.photo_factory = photo_factory
        self.scale = scale
        self.transparent_color = transparent_color
        self._cache: dict[tuple[SkinId, Pose, int, Direction], object] = {}

    def get(self, skin: SkinId, pose: Pose, frame_index: int, direction: Direction) -> object:
        key = (skin, pose, frame_index, direction)
        if key not in self._cache:
            rows = rasterize_frame(skin, pose, frame_index, direction)
            image = self.photo_factory(width=FRAME_WIDTH, height=FRAME_HEIGHT)
            image.put(" ".join(tk_color_rows(rows, self.transparent_color)))
            self._cache[key] = image.zoom(self.scale, self.scale)
        return self._cache[key]

    def clear(self, scale: int | None = None) -> None:
        if scale is not None:
            self.scale = scale
        self._cache.clear()
