"""Generate the deterministic Mikan Pet application icon."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageColor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mikan_pet.core.sprites import rasterize_frame
from mikan_pet.core.types import Direction, Pose, SkinId


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def generate_icon(output_path: Path = ROOT / "assets" / "MikanPet.ico") -> Path:
    """Render the Mikan idle frame into a multi-resolution transparent ICO."""
    raster = rasterize_frame(SkinId.MIKAN, Pose.IDLE, 0, Direction.RIGHT)
    image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for y, row in enumerate(raster):
        for x, color in enumerate(row):
            if color is not None:
                image.putpixel((x, y), (*ImageColor.getrgb(color), 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((256, 256), Image.Resampling.NEAREST).save(
        output_path,
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
    )
    return output_path


if __name__ == "__main__":
    generate_icon()
