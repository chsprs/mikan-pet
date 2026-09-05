"""Generate a PyInstaller Windows version-resource definition."""

from __future__ import annotations

import argparse
from pathlib import Path


def render_version_info(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError("version must use X.Y.Z numeric format")
    major, minor, patch = (int(part) for part in parts)
    numeric = f"({major}, {minor}, {patch}, 0)"
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric},
    prodvers={numeric},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Mikan Pet'),
        StringStruct('FileDescription', 'Mikan Pet desktop companion'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'MikanPet'),
        StringStruct('OriginalFilename', 'MikanPet.exe'),
        StringStruct('ProductName', 'Mikan Pet'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_version_info(args.version), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
