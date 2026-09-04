"""Versioned application settings with atomic persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from mikan_pet.core.types import Point, SkinId


@dataclass(frozen=True)
class AppSettings:
    schema_version: int = 1
    position: Point | None = None
    monitor_id: str | None = None
    skin: SkinId = SkinId.MIKAN
    walking: bool = True
    controls_visible: bool = True
    always_on_top: bool = True


def default_settings() -> AppSettings:
    return AppSettings()


def settings_path() -> Path:
    return Path(os.environ["APPDATA"]) / "MikanPet" / "settings.json"


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def load(self) -> AppSettings:
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
            return self._parse(document)
        except (OSError, UnicodeError, TypeError, ValueError, KeyError):
            return default_settings()

    @staticmethod
    def _parse(document: object) -> AppSettings:
        if not isinstance(document, dict):
            raise ValueError("settings document must be an object")
        allowed = {
            "schema_version",
            "position",
            "monitor_id",
            "skin",
            "walking",
            "controls_visible",
            "always_on_top",
        }
        if set(document) - allowed or type(document.get("schema_version")) is not int:
            raise ValueError("invalid schema")
        if document["schema_version"] != 1:
            raise ValueError("unsupported schema")

        position_value = document.get("position")
        if position_value is None:
            position = None
        else:
            if not isinstance(position_value, dict) or set(position_value) != {"x", "y"}:
                raise ValueError("invalid position")
            if type(position_value["x"]) is not int or type(position_value["y"]) is not int:
                raise ValueError("invalid position")
            position = Point(position_value["x"], position_value["y"])

        monitor_id = document.get("monitor_id")
        if monitor_id is not None and not isinstance(monitor_id, str):
            raise ValueError("invalid monitor")

        skin_value = document.get("skin", SkinId.MIKAN.value)
        try:
            skin = SkinId(skin_value)
        except (TypeError, ValueError):
            raise ValueError("invalid skin") from None

        boolean_values = {
            name: document.get(name, True)
            for name in ("walking", "controls_visible", "always_on_top")
        }
        if any(type(value) is not bool for value in boolean_values.values()):
            raise ValueError("invalid boolean")
        return AppSettings(
            schema_version=1,
            position=position,
            monitor_id=monitor_id,
            skin=skin,
            **boolean_values,
        )

    def save(self, settings: AppSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_name("settings.tmp")
        document = {
            "schema_version": settings.schema_version,
            "position": None if settings.position is None else {
                "x": settings.position.x,
                "y": settings.position.y,
            },
            "monitor_id": settings.monitor_id,
            "skin": settings.skin.value,
            "walking": settings.walking,
            "controls_visible": settings.controls_visible,
            "always_on_top": settings.always_on_top,
        }
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
        except Exception:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise
