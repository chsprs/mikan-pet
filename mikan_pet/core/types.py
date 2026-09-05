from dataclasses import dataclass
from enum import Enum


class SkinId(str, Enum):
    MIKAN = "mikan"
    BYTE = "byte"
    MOCHI = "mochi"
    ASH = "ash"


class MotionMode(str, Enum):
    AUTOMATIC = "automatic"
    STOPPED = "stopped"
    DRAGGING = "dragging"


class Pose(str, Enum):
    WALK = "walk"
    IDLE = "idle"
    SLEEP = "sleep"
    REACT = "react"


class Direction(int, Enum):
    LEFT = -1
    RIGHT = 1


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Size:
    width: int
    height: int


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top
