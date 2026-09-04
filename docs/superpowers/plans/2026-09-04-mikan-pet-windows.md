# Mikan Pet for Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build an installable animated pixel-cat desktop pet for Windows 10/11 x64 with universal media controls, autonomous movement, runtime skin selection, and persistent preferences.

**Architecture:** A small transparent Tkinter window renders cached procedural pixel frames while a GUI-independent state machine controls walking, idle, sleep, dragging, and reactions. pywin32 adapters provide monitor discovery, media-key delivery, and a Windows mutex; JSON settings persist under AppData. PyInstaller creates the standalone application folder and Inno Setup wraps it in a per-user installer.

**Tech Stack:** Python 3.14, Tkinter/Tcl 8.6, pywin32 312, standard-library unittest, Pillow 12.2.0 for icon generation, PyInstaller 6.22.2, PowerShell 7, and Inno Setup 6.7.3 or newer.

**Spec:** docs/superpowers/specs/2026-09-04-mikan-pet-windows-design.md

## Global Constraints

- Support Windows 10 and Windows 11, 64-bit.
- Windows 11 on ARM is supported through x64 emulation; no native ARM64 package is required.
- Installed and portable builds must run without a separate Python installation.
- Use a compact transparent window around the pet and expanded controls; never create a full-screen click-blocking overlay.
- Use only three universal media actions: previous, play/pause, and next.
- Do not add track metadata, volume controls, autostart, tray controls, networking, telemetry, accounts, or automatic updates.
- Store settings at %APPDATA%\MikanPet\settings.json with schema version 1.
- Keep Mikan, Byte, and Mochi behaviorally identical; skins may change only rendered colors and markings.
- Keep Tkinter work on its event-loop thread; do not mutate widgets from worker threads.
- Use standard-library unittest for automated tests.
- Produce dist\MikanPet-Setup-x64.exe and dist\MikanPet-portable-x64.zip.
- The locally produced installer is unsigned because no code-signing certificate is available; document the possible Windows SmartScreen warning.

---

## File Map

The implementation creates these focused units:

- pyproject.toml — project metadata, Python floor, runtime dependency, and console entry point.
- requirements-build.txt — exact build-only dependency pins.
- mikan_pet/__main__.py — command-line entry point.
- mikan_pet/app.py — dependency composition, singleton lifetime, settings load/save, smoke mode, and shutdown.
- mikan_pet/core/types.py — shared enums and immutable geometry/value objects.
- mikan_pet/core/state.py — deterministic pet state machine with no GUI imports.
- mikan_pet/core/sprites.py — skin palettes, semantic pixel rectangles, animation frames, registry validation, and rasterization.
- mikan_pet/core/gesture.py — click-versus-drag classifier.
- mikan_pet/core/window_layout.py — DPI-scaled collapsed/expanded window geometry derived from pet coordinates.
- mikan_pet/services/settings.py — schema validation and atomic JSON persistence.
- mikan_pet/services/monitors.py — Windows monitor enumeration and work-area selection.
- mikan_pet/services/media_keys.py — universal media virtual-key emission.
- mikan_pet/services/singleton.py — named Windows mutex.
- mikan_pet/ui/sprite_cache.py — raster-to-Tk PhotoImage conversion and frame caching.
- mikan_pet/ui/dpi.py — HWND DPI query, WM_DPICHANGED subclassing, and suggested-rectangle handling.
- mikan_pet/ui/pet_window.py — transparent window, Canvas controls, animation loop, pointer bindings, and context menu.
- scripts/generate_icon.py — deterministic ICO generation from the Mikan skin.
- scripts/build.ps1 — clean test, executable, portable ZIP, and installer build.
- packaging/MikanPet.manifest — packaged-process Per-Monitor-V2 DPI declaration.
- installer/MikanPet.iss — per-user Windows installer definition.
- README.md — install, usage, controls, build, troubleshooting, and unsigned-build disclosure.
- tests/ — one test module for each testable unit and integration boundary.

---

### Task 1: Project Foundation and Pet State Machine

**Files:**
- Create: pyproject.toml
- Create: requirements-build.txt
- Create: mikan_pet/__init__.py
- Create: mikan_pet/core/__init__.py
- Create: mikan_pet/core/types.py
- Create: mikan_pet/core/state.py
- Create: tests/__init__.py
- Create: tests/test_state.py

**Interfaces:**
- Consumes: no application code.
- Produces: SkinId, MotionMode, Pose, Direction, Point, Size, WorkArea, BehaviorDurations, PetState, and PetController.

- [ ] **Step 1: Add project metadata and the failing state-machine tests**

Create pyproject.toml with this dependency and entry-point contract:

~~~toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "mikan-pet"
version = "0.1.0"
description = "Animated pixel-cat desktop pet and media controller for Windows"
requires-python = ">=3.11,<3.15"
dependencies = [
  "pywin32==312; sys_platform == 'win32'",
]

[project.scripts]
mikan-pet = "mikan_pet.__main__:main"

[tool.setuptools.packages.find]
include = ["mikan_pet*"]
~~~

Create requirements-build.txt:

~~~text
pywin32==312
Pillow==12.2.0
pyinstaller==6.22.2
~~~

Create tests/test_state.py with these cases:

~~~python
import unittest

from mikan_pet.core.state import BehaviorDurations, PetController, PetState
from mikan_pet.core.types import Direction, MotionMode, Point, Pose, Size, SkinId, WorkArea


class PetControllerTests(unittest.TestCase):
    def make_controller(self) -> PetController:
        state = PetState(
            position=Point(70, 40),
            direction=Direction.RIGHT,
            motion=MotionMode.AUTOMATIC,
            pose=Pose.WALK,
            skin=SkinId.MIKAN,
            controls_visible=True,
            always_on_top=True,
        )
        return PetController(
            state,
            BehaviorDurations(walk_ms=1000, idle_ms=500, sleep_ms=800, react_ms=300, sleep_every=2),
        )

    def test_walk_clamps_and_reverses_at_right_edge(self) -> None:
        controller = self.make_controller()
        controller.tick(500, WorkArea(0, 0, 100, 100), Size(20, 20))
        self.assertEqual(Point(80, 40), controller.state.position)
        self.assertEqual(Direction.LEFT, controller.state.direction)

    def test_stop_and_resume_change_motion_and_pose(self) -> None:
        controller = self.make_controller()
        controller.toggle_walking()
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual(Pose.IDLE, controller.state.pose)
        stopped_at = controller.state.position
        controller.tick(1000, WorkArea(0, 0, 100, 100), Size(20, 20))
        self.assertEqual(stopped_at, controller.state.position)
        controller.toggle_walking()
        self.assertEqual(MotionMode.AUTOMATIC, controller.state.motion)
        self.assertEqual(Pose.WALK, controller.state.pose)

    def test_stopped_pet_can_sleep_without_moving(self) -> None:
        controller = self.make_controller()
        controller.toggle_walking()
        stopped_at = controller.state.position
        controller.tick(1500, WorkArea(0, 0, 500, 300), Size(20, 20))
        self.assertEqual(Pose.SLEEP, controller.state.pose)
        self.assertEqual(stopped_at, controller.state.position)

    def test_drag_suspends_motion_and_keeps_new_position(self) -> None:
        controller = self.make_controller()
        controller.begin_drag()
        controller.drag_to(Point(12, 18))
        controller.tick(900, WorkArea(0, 0, 100, 100), Size(20, 20))
        self.assertEqual(Point(12, 18), controller.state.position)
        controller.end_drag()
        self.assertEqual(MotionMode.AUTOMATIC, controller.state.motion)

    def test_drag_preserves_stopped_mode(self) -> None:
        controller = self.make_controller()
        controller.toggle_walking()
        controller.begin_drag()
        controller.drag_to(Point(12, 18))
        controller.end_drag()
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual(Pose.IDLE, controller.state.pose)

    def test_drag_position_is_unbounded_until_release_policy_clamps_it(self) -> None:
        controller = self.make_controller()
        controller.begin_drag()
        controller.drag_to(Point(-450, 12))
        self.assertEqual(Point(-450, 12), controller.state.position)
        controller.place_within(WorkArea(-400, 0, 0, 300), Size(20, 20))
        self.assertEqual(Point(-400, 12), controller.state.position)

    def test_motion_speed_scales_from_logical_to_current_dpi(self) -> None:
        controller = self.make_controller()
        controller.tick(
            250,
            WorkArea(0, 0, 500, 300),
            Size(20, 20),
            dpi_scale=1.5,
        )
        self.assertEqual(Point(85, 40), controller.state.position)

    def test_fractional_physical_motion_is_carried_between_ticks(self) -> None:
        controller = self.make_controller()
        area = WorkArea(0, 0, 500, 300)
        controller.tick(50, area, Size(20, 20), dpi_scale=1.25)
        controller.tick(50, area, Size(20, 20), dpi_scale=1.25)
        self.assertEqual(Point(75, 40), controller.state.position)

    def test_idle_cycle_enters_sleep_on_configured_interval(self) -> None:
        controller = self.make_controller()
        area = WorkArea(0, 0, 500, 300)
        controller.tick(1000, area, Size(20, 20))
        self.assertEqual(Pose.IDLE, controller.state.pose)
        controller.tick(500, area, Size(20, 20))
        self.assertEqual(Pose.WALK, controller.state.pose)
        controller.tick(1000, area, Size(20, 20))
        self.assertEqual(Pose.SLEEP, controller.state.pose)

    def test_reaction_returns_to_prior_motion_pose(self) -> None:
        controller = self.make_controller()
        controller.react()
        self.assertEqual(Pose.REACT, controller.state.pose)
        controller.tick(300, WorkArea(0, 0, 500, 300), Size(20, 20))
        self.assertEqual(Pose.WALK, controller.state.pose)

    def test_repeated_reaction_extends_without_getting_stuck(self) -> None:
        controller = self.make_controller()
        area = WorkArea(0, 0, 500, 300)
        controller.react()
        controller.tick(100, area, Size(20, 20))
        controller.react()
        controller.tick(300, area, Size(20, 20))
        self.assertEqual(Pose.WALK, controller.state.pose)

    def test_stop_and_idle_recovers_from_any_pose(self) -> None:
        controller = self.make_controller()
        controller.react()
        controller.stop_and_idle()
        controller.end_drag()
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual(Pose.IDLE, controller.state.pose)


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Create the isolated project environment**

Run:

~~~powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
~~~

Expected: the repository-local environment contains pywin32 312, Pillow 12.2.0,
and PyInstaller 6.22.2.

- [ ] **Step 3: Run the focused tests and confirm the expected failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_state -v
~~~

Expected: import failure because mikan_pet.core.state and mikan_pet.core.types do not exist.

- [ ] **Step 4: Implement the shared types and deterministic state machine**

Create the enums and value objects with these exact public fields:

~~~python
# mikan_pet/core/types.py
from dataclasses import dataclass
from enum import Enum


class SkinId(str, Enum):
    MIKAN = "mikan"
    BYTE = "byte"
    MOCHI = "mochi"


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
~~~

Implement PetController with a speed of 40 logical pixels per second. tick()
accepts dpi_scale: float = 1.0 and converts that speed to physical pixels for the
current monitor. Clamp automatic movement inside the supplied work area.
Reject a non-positive dpi_scale. Carry fractional physical movement between
ticks so 125% scaling does not round every 50-ms update in the same direction.
Dragging itself is deliberately unbounded; the UI selects a monitor and calls
place_within() only at release. Preserve the pre-drag motion mode so ending a
drag resumes automatic movement only when requested. Use phase_elapsed_ms and
completed_idle_count so pose transitions are deterministic:

~~~python
# mikan_pet/core/state.py
from dataclasses import dataclass, replace

from mikan_pet.core.types import Direction, MotionMode, Point, Pose, Size, SkinId, WorkArea


@dataclass(frozen=True)
class BehaviorDurations:
    walk_ms: int = 9000
    idle_ms: int = 3500
    sleep_ms: int = 7000
    react_ms: int = 450
    sleep_every: int = 3


@dataclass(frozen=True)
class PetState:
    position: Point
    direction: Direction
    motion: MotionMode
    pose: Pose
    skin: SkinId
    controls_visible: bool
    always_on_top: bool


class PetController:
    SPEED_LOGICAL_PX_PER_SECOND = 40.0

    def __init__(self, state: PetState, durations: BehaviorDurations | None = None) -> None:
        self.state = state
        self.durations = durations or BehaviorDurations()
        self.phase_elapsed_ms = 0
        self.completed_idle_count = 0
        self._movement_remainder = 0.0
        self._pre_drag_motion = state.motion
        self._pose_before_reaction = state.pose

    def tick(
        self,
        elapsed_ms: int,
        area: WorkArea,
        pet_size: Size,
        dpi_scale: float = 1.0,
    ) -> PetState:
        if elapsed_ms <= 0:
            return self.state
        if self.state.motion is MotionMode.DRAGGING:
            return self.state
        if self.state.pose is Pose.REACT:
            self.phase_elapsed_ms += elapsed_ms
            if self.phase_elapsed_ms >= self.durations.react_ms:
                restored = self._pose_before_reaction if self.state.motion is MotionMode.AUTOMATIC else Pose.IDLE
                self.state = replace(self.state, pose=restored)
                self.phase_elapsed_ms = 0
            return self.state
        if self.state.motion is MotionMode.STOPPED:
            self.phase_elapsed_ms += elapsed_ms
            if self.state.pose is Pose.IDLE and self.phase_elapsed_ms >= self.durations.idle_ms * 3:
                self.state = replace(self.state, pose=Pose.SLEEP)
                self.phase_elapsed_ms = 0
            elif self.state.pose is Pose.SLEEP and self.phase_elapsed_ms >= self.durations.sleep_ms:
                self.state = replace(self.state, pose=Pose.IDLE)
                self.phase_elapsed_ms = 0
            return self.state
        self.phase_elapsed_ms += elapsed_ms
        if self.state.pose is Pose.WALK:
            self._move(elapsed_ms, area, pet_size, dpi_scale)
            if self.phase_elapsed_ms >= self.durations.walk_ms:
                self.phase_elapsed_ms = 0
                self.completed_idle_count += 1
                next_pose = Pose.SLEEP if self.completed_idle_count % self.durations.sleep_every == 0 else Pose.IDLE
                self.state = replace(self.state, pose=next_pose)
        elif self.state.pose is Pose.IDLE and self.phase_elapsed_ms >= self.durations.idle_ms:
            self.phase_elapsed_ms = 0
            self.state = replace(self.state, pose=Pose.WALK)
        elif self.state.pose is Pose.SLEEP and self.phase_elapsed_ms >= self.durations.sleep_ms:
            self.phase_elapsed_ms = 0
            self.state = replace(self.state, pose=Pose.WALK)
        return self.state

    def _move(self, elapsed_ms: int, area: WorkArea, pet_size: Size, dpi_scale: float) -> None:
        distance = (
            self.SPEED_LOGICAL_PX_PER_SECOND * dpi_scale * elapsed_ms / 1000
            + self._movement_remainder
        )
        pixels = int(distance)
        self._movement_remainder = distance - pixels
        delta = pixels * self.state.direction.value
        minimum = area.left
        maximum = area.right - pet_size.width
        candidate = self.state.position.x + delta
        direction = self.state.direction
        if candidate <= minimum:
            candidate, direction = minimum, Direction.RIGHT
            self._movement_remainder = 0.0
        elif candidate >= maximum:
            candidate, direction = maximum, Direction.LEFT
            self._movement_remainder = 0.0
        maximum_y = area.bottom - pet_size.height
        y = min(max(self.state.position.y, area.top), maximum_y)
        self.state = replace(self.state, position=Point(candidate, y), direction=direction)

    def toggle_walking(self) -> None:
        if self.state.motion is MotionMode.STOPPED:
            self.state = replace(self.state, motion=MotionMode.AUTOMATIC, pose=Pose.WALK)
        else:
            self.state = replace(self.state, motion=MotionMode.STOPPED, pose=Pose.IDLE)
        self.phase_elapsed_ms = 0
        self._movement_remainder = 0.0

    def begin_drag(self) -> None:
        self._pre_drag_motion = self.state.motion
        self.state = replace(self.state, motion=MotionMode.DRAGGING)
        self._movement_remainder = 0.0

    def drag_to(self, position: Point) -> None:
        self.state = replace(self.state, position=position)

    def place_within(self, area: WorkArea, pet_size: Size) -> None:
        x = min(max(self.state.position.x, area.left), area.right - pet_size.width)
        y = min(max(self.state.position.y, area.top), area.bottom - pet_size.height)
        self.state = replace(self.state, position=Point(x, y))

    def end_drag(self) -> None:
        motion = self._pre_drag_motion
        if motion not in (MotionMode.AUTOMATIC, MotionMode.STOPPED):
            motion = MotionMode.AUTOMATIC
        pose = Pose.WALK if motion is MotionMode.AUTOMATIC else Pose.IDLE
        self.state = replace(self.state, motion=motion, pose=pose)
        self.phase_elapsed_ms = 0

    def react(self) -> None:
        if self.state.pose is not Pose.REACT:
            self._pose_before_reaction = self.state.pose
        self.state = replace(self.state, pose=Pose.REACT)
        self.phase_elapsed_ms = 0

    def set_controls_visible(self, visible: bool) -> None:
        self.state = replace(self.state, controls_visible=visible)

    def set_skin(self, skin: SkinId) -> None:
        self.state = replace(self.state, skin=skin)

    def set_always_on_top(self, enabled: bool) -> None:
        self.state = replace(self.state, always_on_top=enabled)

    def stop_and_idle(self) -> None:
        self._pre_drag_motion = MotionMode.STOPPED
        self.state = replace(self.state, motion=MotionMode.STOPPED, pose=Pose.IDLE)
        self.phase_elapsed_ms = 0
        self._movement_remainder = 0.0
~~~

If a test exposes a boundary discrepancy, adjust the implementation while preserving the public interfaces above.

- [ ] **Step 5: Run the state tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_state -v
~~~

Expected: twelve tests pass.

- [ ] **Step 6: Commit the foundation**

~~~powershell
git add pyproject.toml requirements-build.txt mikan_pet tests
git commit -m "feat: add pet state machine"
~~~

---

### Task 2: Procedural Pixel Skins and Animation Frames

**Files:**
- Create: mikan_pet/core/sprites.py
- Create: tests/test_sprites.py

**Interfaces:**
- Consumes: SkinId, Pose, and Direction from mikan_pet.core.types.
- Produces: ColorRole, PixelRect, FrameTemplate, SkinDefinition, SKINS, FRAMES, validate_registry(), frame_count(), and rasterize_frame().

- [ ] **Step 1: Write failing registry and rasterization tests**

~~~python
# tests/test_sprites.py
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
~~~

- [ ] **Step 2: Run the sprite tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_sprites -v
~~~

Expected: import failure because mikan_pet.core.sprites does not exist.

- [ ] **Step 3: Implement semantic pixel frames and all three palettes**

Use a 32 by 32 logical-pixel frame. PixelRect fields are x, y, width, height, and semantic color role. Rectangles later in a frame overwrite earlier rectangles, which allows face details and Mochi patches to sit over the base body.

Define the public data model exactly:

~~~python
FRAME_WIDTH = 32
FRAME_HEIGHT = 32


class ColorRole(str, Enum):
    BODY = "body"
    SHADE = "shade"
    DARK = "dark"
    LIGHT = "light"
    EYE = "eye"
    COLLAR = "collar"
    PATCH_ONE = "patch_one"
    PATCH_TWO = "patch_two"


@dataclass(frozen=True)
class PixelRect:
    x: int
    y: int
    width: int
    height: int
    role: ColorRole


@dataclass(frozen=True)
class FrameTemplate:
    rectangles: tuple[PixelRect, ...]


@dataclass(frozen=True)
class SkinDefinition:
    id: SkinId
    display_name: str
    palette: dict[ColorRole, str]
~~~

FRAMES is dict[Pose, tuple[FrameTemplate, ...]]. SKINS is
dict[SkinId, SkinDefinition] and uses display names Mikan, Byte, and Mochi.

Define these exact palettes:

~~~python
MIKAN = {
    ColorRole.BODY: "#E78145",
    ColorRole.SHADE: "#B95D32",
    ColorRole.DARK: "#7F4528",
    ColorRole.LIGHT: "#FFF2D8",
    ColorRole.EYE: "#2A2430",
    ColorRole.COLLAR: "#3C6E91",
    ColorRole.PATCH_ONE: "#E78145",
    ColorRole.PATCH_TWO: "#B95D32",
}

BYTE = {
    ColorRole.BODY: "#3E467E",
    ColorRole.SHADE: "#303767",
    ColorRole.DARK: "#22284F",
    ColorRole.LIGHT: "#C9D1FF",
    ColorRole.EYE: "#89F7D4",
    ColorRole.COLLAR: "#FF76B7",
    ColorRole.PATCH_ONE: "#343B70",
    ColorRole.PATCH_TWO: "#89F7D4",
}

MOCHI = {
    ColorRole.BODY: "#FFFAF1",
    ColorRole.SHADE: "#DED5CA",
    ColorRole.DARK: "#51434B",
    ColorRole.LIGHT: "#FFF6EA",
    ColorRole.EYE: "#3B343A",
    ColorRole.COLLAR: "#4F7E78",
    ColorRole.PATCH_ONE: "#D07A43",
    ColorRole.PATCH_TWO: "#51434B",
}
~~~

Build the upright cat from these logical rectangles before pose-specific changes:

~~~python
[
    PixelRect(8, 15, 17, 11, ColorRole.BODY),
    PixelRect(10, 8, 14, 11, ColorRole.BODY),
    PixelRect(10, 5, 4, 5, ColorRole.SHADE),
    PixelRect(20, 5, 4, 5, ColorRole.SHADE),
    PixelRect(25, 18, 5, 3, ColorRole.SHADE),
    PixelRect(28, 14, 3, 6, ColorRole.SHADE),
    PixelRect(12, 11, 2, 3, ColorRole.EYE),
    PixelRect(20, 11, 2, 3, ColorRole.EYE),
    PixelRect(16, 14, 2, 2, ColorRole.DARK),
    PixelRect(14, 17, 6, 2, ColorRole.LIGHT),
    PixelRect(12, 20, 10, 2, ColorRole.COLLAR),
    PixelRect(16, 21, 2, 2, ColorRole.COLLAR),
    PixelRect(10, 24, 5, 5, ColorRole.SHADE),
    PixelRect(19, 24, 5, 5, ColorRole.SHADE),
    PixelRect(11, 8, 5, 3, ColorRole.PATCH_ONE),
    PixelRect(20, 8, 4, 4, ColorRole.PATCH_TWO),
]
~~~

Generate frames with small rectangle offsets instead of duplicating palettes:

- WALK has two frames. Alternate the left and right leg x coordinates by one pixel, shift the body vertically by one pixel in the second frame, and alternate tail tip y between 12 and 14.
- IDLE is a ten-frame sequence. Frames 0–2 use the upright open-eye frame,
  frames 3–4 use a one-pixel lowered breathing frame, frames 5–7 return to the
  upright frame, frame 8 moves the tail tip by one pixel, and frame 9 replaces
  each eye with a 2 by 1 closed-eye rectangle. This gives a deliberate blink
  rather than rapid continuous blinking.
- SLEEP has two frames. Use a horizontal 20 by 8 body at x=6, y=19; a 9 by 8 head at x=5, y=16; a curled tail along x=22 to x=29; closed eyes are two 2 by 1 dark rectangles. Shift the tail tip one pixel between frames.
- REACT has one upright frame with 3 by 3 eyes, ears raised one pixel, and the tail tip raised two pixels.

Implement rasterize_frame() by filling a list of FRAME_HEIGHT rows with None, painting rectangles in list order, converting to immutable tuples, and reversing every row for Direction.LEFT. frame_index wraps with modulo so animation callers never receive IndexError.

validate_registry() returns human-readable errors and checks:

1. every SkinId is registered;
2. every Pose has at least one frame;
3. every rectangle stays inside 32 by 32;
4. every semantic role used by a frame exists in each skin palette;
5. no skin palette uses the transparent window key color #FF00FF.

- [ ] **Step 4: Run the sprite tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_sprites -v
~~~

Expected: four tests pass.

- [ ] **Step 5: Commit the sprite registry**

~~~powershell
git add mikan_pet/core/sprites.py tests/test_sprites.py
git commit -m "feat: add animated pixel skins"
~~~

---

### Task 3: Versioned Settings with Atomic Persistence

**Files:**
- Create: mikan_pet/services/__init__.py
- Create: mikan_pet/services/settings.py
- Create: tests/test_settings.py

**Interfaces:**
- Consumes: Point and SkinId.
- Produces: AppSettings, default_settings(), settings_path(), and SettingsStore.load()/save().

- [ ] **Step 1: Write failing settings tests**

~~~python
# tests/test_settings.py
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mikan_pet.core.types import Point, SkinId
from mikan_pet.services.settings import AppSettings, SettingsStore, default_settings


class SettingsStoreTests(unittest.TestCase):
    def test_missing_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(Path(folder) / "settings.json")
            self.assertEqual(default_settings(), store.load())

    def test_round_trip_preserves_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            settings = AppSettings(
                schema_version=1,
                position=Point(-120, 450),
                monitor_id=r"\\.\DISPLAY2",
                skin=SkinId.BYTE,
                walking=False,
                controls_visible=False,
                always_on_top=True,
            )
            store = SettingsStore(path)
            store.save(settings)
            self.assertEqual(settings, store.load())
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_corrupt_or_invalid_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"skin":"unknown","position":"bad"}', encoding="utf-8")
            self.assertEqual(default_settings(), SettingsStore(path).load())

    def test_truncated_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"schema_version": 1,', encoding="utf-8")
            self.assertEqual(default_settings(), SettingsStore(path).load())

    def test_save_writes_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            SettingsStore(path).save(default_settings())
            self.assertEqual(1, json.loads(path.read_text(encoding="utf-8"))["schema_version"])

    def test_save_atomically_replaces_the_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("old", encoding="utf-8")
            with patch("mikan_pet.services.settings.os.replace", wraps=os.replace) as replace:
                SettingsStore(path).save(default_settings())
            replace.assert_called_once_with(path.with_name("settings.tmp"), path)
            self.assertEqual(1, json.loads(path.read_text(encoding="utf-8"))["schema_version"])

    def test_failed_replace_preserves_existing_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("old", encoding="utf-8")
            with patch("mikan_pet.services.settings.os.replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    SettingsStore(path).save(default_settings())
            self.assertEqual("old", path.read_text(encoding="utf-8"))
            self.assertFalse(path.with_name("settings.tmp").exists())


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the settings tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_settings -v
~~~

Expected: import failure because mikan_pet.services.settings does not exist.

- [ ] **Step 3: Implement strict parsing and atomic replacement**

AppSettings must use these fields and defaults:

~~~python
@dataclass(frozen=True)
class AppSettings:
    schema_version: int = 1
    position: Point | None = None
    monitor_id: str | None = None
    skin: SkinId = SkinId.MIKAN
    walking: bool = True
    controls_visible: bool = True
    always_on_top: bool = True
~~~

default_settings() returns AppSettings() with no mutations. settings_path()
returns Path(os.environ["APPDATA"]) / "MikanPet" / "settings.json". The store
constructor accepts an explicit path for tests. load() must reject the entire
document and return defaults when:

- schema_version is not exactly integer 1;
- x or y is present but type(value) is not exactly int (reject bool);
- monitor_id is neither string nor null;
- skin is not one of the SkinId values;
- any Boolean field is not a real bool;
- JSON decoding or file reading fails.

save() creates the parent directory, writes UTF-8 JSON with indent=2 to
settings.tmp, flushes and calls os.fsync(), then calls os.replace(temp_path,
final_path). Never write directly over the final file. If flushing or replacement
fails, preserve the prior final file, best-effort remove only settings.tmp, and
re-raise the exception.

- [ ] **Step 4: Run the settings tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_settings -v
~~~

Expected: seven tests pass.

- [ ] **Step 5: Commit settings persistence**

~~~powershell
git add mikan_pet/services tests/test_settings.py
git commit -m "feat: persist pet settings safely"
~~~

---

### Task 4: Multi-Monitor Work-Area Service

**Files:**
- Create: mikan_pet/services/monitors.py
- Create: tests/test_monitors.py

**Interfaces:**
- Consumes: Point, Size, and WorkArea.
- Produces: MonitorInfo, intersection_area(), clamp_position(),
  select_monitor(), select_drag_monitor(), default_position(),
  enable_per_monitor_dpi_awareness(), Win32MonitorBackend, and MonitorService.

- [ ] **Step 1: Write failing geometry and selection tests**

~~~python
# tests/test_monitors.py
import unittest
from unittest.mock import Mock

from mikan_pet.core.types import Point, Size, WorkArea
from mikan_pet.services.monitors import (
    MonitorInfo,
    clamp_position,
    default_position,
    enable_per_monitor_dpi_awareness,
    MonitorService,
    select_drag_monitor,
    select_monitor,
)


MONITOR_1 = MonitorInfo("DISPLAY1", WorkArea(0, 0, 1920, 1040), True)
MONITOR_2 = MonitorInfo("DISPLAY2", WorkArea(-1280, 0, 0, 984), False)


class MonitorGeometryTests(unittest.TestCase):
    def test_selects_monitor_with_largest_pet_intersection(self) -> None:
        selected = select_monitor(Point(-140, 300), Size(176, 160), [MONITOR_1, MONITOR_2])
        self.assertEqual("DISPLAY2", selected.id)

    def test_off_screen_position_falls_back_to_primary(self) -> None:
        selected = select_monitor(Point(9000, 9000), Size(176, 160), [MONITOR_1, MONITOR_2])
        self.assertEqual("DISPLAY1", selected.id)

    def test_recover_position_really_moves_off_screen_saved_point(self) -> None:
        backend = Mock()
        backend.enumerate.return_value = [MONITOR_1, MONITOR_2]
        service = MonitorService(backend)
        service.refresh()
        recovered = service.recover_position(Point(9000, 9000), Size(176, 160))
        self.assertEqual(Point(1720, 856), recovered)
        self.assertEqual(MONITOR_1, service.primary())

    def test_clamp_keeps_pet_inside_work_area(self) -> None:
        self.assertEqual(
            Point(-1280, 824),
            clamp_position(Point(-2000, 1000), Size(176, 160), MONITOR_2.work_area),
        )

    def test_default_position_is_lower_right_with_margin(self) -> None:
        self.assertEqual(Point(1720, 856), default_position(MONITOR_1.work_area, Size(176, 160), 24))

    def test_dpi_awareness_falls_back_to_legacy_per_monitor(self) -> None:
        backend = Mock()
        backend.is_per_monitor.side_effect = [False, True]
        backend.set_per_monitor_v2.return_value = False
        backend.set_per_monitor_legacy.return_value = True
        result = enable_per_monitor_dpi_awareness(backend)
        self.assertTrue(result)
        backend.set_per_monitor_v2.assert_called_once()
        backend.set_per_monitor_legacy.assert_called_once()

    def test_drag_monitor_sequence_handles_adjacent_gap_and_negative_coordinates(self) -> None:
        gap_monitor = MonitorInfo("DISPLAY3", WorkArea(3000, 0, 4280, 984), False)
        monitors = [MONITOR_1, MONITOR_2, gap_monitor]
        last = "DISPLAY1"
        selected_ids = []
        for position in (
            Point(100, 200),
            Point(-120, 200),
            Point(2200, 200),
            Point(3050, 200),
        ):
            target = select_drag_monitor(position, Size(176, 160), monitors, last)
            last = target.id
            selected_ids.append(last)
        self.assertEqual(
            ["DISPLAY1", "DISPLAY2", "DISPLAY1", "DISPLAY3"],
            selected_ids,
        )


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the monitor tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_monitors -v
~~~

Expected: import failure because mikan_pet.services.monitors does not exist.

- [ ] **Step 3: Implement pure geometry and the pywin32 adapter**

MonitorInfo has id: str, work_area: WorkArea, and primary: bool.
intersection_area() computes overlapping width times height for the pet
rectangle. select_monitor() returns the monitor with the largest positive
overlap, otherwise the primary monitor, otherwise the first monitor.

select_drag_monitor(position, pet_size, monitors, last_intersected_id) implements
the release policy separately: return the monitor with the largest positive pet
body intersection; when the pet is wholly in a physical gap, choose the work area
whose rectangle is nearest to the pet center and use last_intersected_id only as
a deterministic tie-breaker. This supports adjacent, gapped, and
negative-coordinate layouts without snapping to the primary monitor during
pointer motion.

Win32MonitorBackend.enumerate() must call:

~~~python
for handle, _, _ in win32api.EnumDisplayMonitors():
    info = win32api.GetMonitorInfo(handle)
    left, top, right, bottom = info["Work"]
    monitors.append(
        MonitorInfo(
            id=info["Device"],
            work_area=WorkArea(left, top, right, bottom),
            primary=bool(info["Flags"] & 1),
        )
    )
~~~

MonitorService.refresh() replaces its current list with backend results and
raises RuntimeError only if Windows returns no monitors. current_for(position,
pet_size) delegates to select_monitor(). primary() returns the primary entry or
the first entry. drag_target() delegates to select_drag_monitor().
recover_position() returns the clamped saved position when it intersects a
monitor and otherwise returns default_position() on primary().

enable_per_monitor_dpi_awareness() accepts an injectable backend for tests and
must run before Tk creates the root window. The production backend first queries
the current process awareness and accepts an existing per-monitor setting from
the executable manifest. Otherwise it calls the one-argument
user32.SetProcessDpiAwarenessContext(c_void_p(-4)), then falls back to the
one-argument shcore.SetProcessDpiAwareness(2), where 2 is
PROCESS_PER_MONITOR_DPI_AWARE and the HRESULT must be checked. The legacy path
is available on early Windows 10 versions. Return True only if the backend
confirms per-monitor awareness after those attempts. The application factory
treats False as a startup error instead of silently running with virtualized
coordinates.

- [ ] **Step 4: Run monitor tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_monitors -v
~~~

Expected: seven tests pass.

- [ ] **Step 5: Commit monitor support**

~~~powershell
git add mikan_pet/services/monitors.py tests/test_monitors.py
git commit -m "feat: keep pet inside monitor work areas"
~~~

---

### Task 5: Windows Media Keys and Single-Instance Guard

**Files:**
- Create: mikan_pet/services/media_keys.py
- Create: mikan_pet/services/singleton.py
- Create: tests/test_windows_services.py

**Interfaces:**
- Consumes: pywin32.
- Produces: MediaAction, MEDIA_VIRTUAL_KEYS, MediaKeyService.send(), and SingleInstance.acquire()/release().

- [ ] **Step 1: Write failing tests with injected Windows backends**

~~~python
# tests/test_windows_services.py
import unittest

from mikan_pet.services.media_keys import KEYEVENTF_KEYUP, MediaAction, MediaKeyService
from mikan_pet.services.singleton import ERROR_ALREADY_EXISTS, SingleInstance


class FakeMediaBackend:
    def __init__(self) -> None:
        self.events: list[tuple[int, int]] = []

    def key_event(self, virtual_key: int, flags: int) -> None:
        self.events.append((virtual_key, flags))


class FakeMutexBackend:
    def __init__(self, last_error: int) -> None:
        self.last_error = last_error
        self.closed: list[object] = []
        self.handle = object()

    def create_mutex(self, name: str) -> object:
        return self.handle

    def get_last_error(self) -> int:
        return self.last_error

    def close_handle(self, handle: object) -> None:
        self.closed.append(handle)


class WindowsServiceTests(unittest.TestCase):
    def test_every_media_action_emits_exact_key_down_then_key_up(self) -> None:
        expected = {
            MediaAction.PREVIOUS: 0xB1,
            MediaAction.PLAY_PAUSE: 0xB3,
            MediaAction.NEXT: 0xB0,
        }
        for action, virtual_key in expected.items():
            with self.subTest(action=action):
                backend = FakeMediaBackend()
                MediaKeyService(backend).send(action)
                self.assertEqual(
                    [(virtual_key, 0), (virtual_key, KEYEVENTF_KEYUP)],
                    backend.events,
                )

    def test_duplicate_mutex_returns_false_and_closes_handle(self) -> None:
        backend = FakeMutexBackend(ERROR_ALREADY_EXISTS)
        guard = SingleInstance("Local\\MikanPet", backend)
        self.assertFalse(guard.acquire())
        self.assertEqual([backend.handle], backend.closed)

    def test_owned_mutex_is_released_once(self) -> None:
        backend = FakeMutexBackend(0)
        guard = SingleInstance("Local\\MikanPet", backend)
        self.assertTrue(guard.acquire())
        guard.release()
        guard.release()
        self.assertEqual([backend.handle], backend.closed)


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run service tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_windows_services -v
~~~

Expected: import failure because the two Windows service modules do not exist.

- [ ] **Step 3: Implement the adapters and exact key map**

Use this public mapping:

~~~python
class MediaAction(str, Enum):
    PREVIOUS = "previous"
    PLAY_PAUSE = "play_pause"
    NEXT = "next"


MEDIA_VIRTUAL_KEYS = {
    MediaAction.PREVIOUS: 0xB1,
    MediaAction.PLAY_PAUSE: 0xB3,
    MediaAction.NEXT: 0xB0,
}
KEYEVENTF_KEYUP = 0x0002
~~~

The production media backend calls win32api.keybd_event(virtual_key, 0, flags, 0). MediaKeyService.send() calls it once with flags 0 and once with KEYEVENTF_KEYUP.

The production mutex backend calls win32event.CreateMutex(None, False, name), win32api.GetLastError(), and win32api.CloseHandle(). SingleInstance closes and clears a duplicate handle immediately, makes release idempotent, and supports with-statement use.

- [ ] **Step 4: Run Windows service tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_windows_services -v
~~~

Expected: three tests pass without emitting a real media key.

- [ ] **Step 5: Commit Windows services**

~~~powershell
git add mikan_pet/services/media_keys.py mikan_pet/services/singleton.py tests/test_windows_services.py
git commit -m "feat: add Windows media and singleton services"
~~~

---

### Task 6: Pointer Gesture, Window Layout, and Tk Sprite Cache

**Files:**
- Create: mikan_pet/core/gesture.py
- Create: mikan_pet/core/window_layout.py
- Create: mikan_pet/ui/__init__.py
- Create: mikan_pet/ui/sprite_cache.py
- Create: tests/test_gesture_layout.py
- Create: tests/test_sprite_cache.py

**Interfaces:**
- Consumes: Point, Size, WorkArea, SkinId, Pose, Direction, and rasterize_frame().
- Produces: GestureResult, PointerGesture, drag_offset_to_logical(),
  position_from_pointer(), DpiMetrics, metrics_for_dpi(), WindowLayout,
  calculate_window_layout(), safe_pet_work_area(), tk_color_rows(),
  SpriteCache.get(), and SpriteCache.clear().

- [ ] **Step 1: Write failing click/drag and geometry tests**

~~~python
# tests/test_gesture_layout.py
import unittest

from mikan_pet.core.gesture import (
    GestureResult,
    PointerGesture,
    drag_offset_to_logical,
    position_from_pointer,
)
from mikan_pet.core.types import Point, WorkArea
from mikan_pet.core.window_layout import (
    calculate_window_layout,
    metrics_for_dpi,
    safe_pet_work_area,
)


class GestureAndLayoutTests(unittest.TestCase):
    def test_four_pixel_motion_remains_click(self) -> None:
        gesture = PointerGesture(threshold=5)
        gesture.press(Point(100, 100))
        gesture.move(Point(104, 100))
        self.assertEqual(GestureResult.CLICK, gesture.release(Point(104, 100)))

    def test_five_pixel_motion_becomes_drag(self) -> None:
        gesture = PointerGesture(threshold=5)
        gesture.press(Point(100, 100))
        gesture.move(Point(103, 104))
        self.assertEqual(GestureResult.DRAG, gesture.release(Point(103, 104)))

    def test_expanded_window_grows_up_around_same_pet(self) -> None:
        metrics = metrics_for_dpi(96)
        collapsed = calculate_window_layout(Point(500, 700), False, metrics)
        expanded = calculate_window_layout(Point(500, 700), True, metrics)
        self.assertEqual(collapsed.pet_screen_origin, expanded.pet_screen_origin)
        self.assertLess(expanded.root_origin.y, collapsed.root_origin.y)
        self.assertGreater(expanded.window_size.height, collapsed.window_size.height)

    def test_visible_controls_shrink_safe_body_bounds(self) -> None:
        monitor = WorkArea(0, 0, 1920, 1040)
        metrics = metrics_for_dpi(96)
        self.assertEqual(
            WorkArea(28, 80, 1892, 1040),
            safe_pet_work_area(monitor, True, metrics),
        )
        self.assertEqual(monitor, safe_pet_work_area(monitor, False, metrics))

    def test_standard_windows_dpi_values_keep_integer_pixel_scale(self) -> None:
        self.assertEqual(
            [4, 5, 6, 7, 8],
            [metrics_for_dpi(dpi).pixel_scale for dpi in (96, 120, 144, 168, 192)],
        )

    def test_150_percent_metrics_scale_layout_in_physical_pixels(self) -> None:
        metrics = metrics_for_dpi(144)
        self.assertEqual(6, metrics.pixel_scale)
        self.assertEqual(216, metrics.pet_size.width)
        self.assertEqual(312, metrics.expanded_size.height)

    def test_drag_threshold_remains_five_logical_pixels(self) -> None:
        self.assertEqual(8, metrics_for_dpi(144).drag_threshold_px)
        self.assertEqual(10, metrics_for_dpi(192).drag_threshold_px)

    def test_drag_anchor_stays_under_pointer_when_dpi_changes(self) -> None:
        logical = drag_offset_to_logical(Point(40, 20), dpi=96)
        self.assertEqual(
            Point(840, 570),
            position_from_pointer(Point(900, 600), logical, dpi=144),
        )


if __name__ == "__main__":
    unittest.main()
~~~

Create tests/test_sprite_cache.py around the pure Tk row formatter:

~~~python
import unittest

from mikan_pet.ui.sprite_cache import tk_color_rows


class SpriteCacheTests(unittest.TestCase):
    def test_transparent_pixels_use_window_key_color(self) -> None:
        rows = ((None, "#112233"), ("#445566", None))
        self.assertEqual(
            ("{#FF00FF #112233}", "{#445566 #FF00FF}"),
            tk_color_rows(rows, "#FF00FF"),
        )


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gesture_layout tests.test_sprite_cache -v
~~~

Expected: import failures for the new modules.

- [ ] **Step 3: Implement the gesture threshold and stable pet anchor**

PointerGesture stores the press point, marks itself dragged when squared distance
is at least threshold squared, and returns GestureResult.CLICK or
GestureResult.DRAG exactly once on release. move() returns True once the
threshold has been crossed and exposes dragged as a read-only property, allowing
the UI to enter MotionMode.DRAGGING only for a real drag rather than every
click. set_threshold() accepts the DPI-scaled integer threshold while preserving
an already-dragged gesture.
drag_offset_to_logical(offset, dpi) converts a physical press offset to 96-DPI
logical units. position_from_pointer(pointer, logical_offset, dpi) scales that
offset to the active DPI and subtracts it from the physical screen pointer.
Both use the same positive-integer validation and half-up coordinate rounding as
metrics_for_dpi().

Treat all saved pet positions and Win32 monitor rectangles as physical screen
pixels. Define the 96-DPI logical baseline and derive an immutable DpiMetrics
instance from the current window DPI:

~~~python
BASE_DPI = 96
BASE_PIXEL_SCALE = 4
BASE_PET_SIZE = Size(144, 128)
BASE_COLLAPSED_SIZE = Size(144, 128)
BASE_EXPANDED_SIZE = Size(200, 208)
BASE_EXPANDED_PET_OFFSET = Point(28, 80)
BASE_PET_IMAGE_OFFSET = Point(8, 0)
BASE_DRAG_THRESHOLD_PX = 5


@dataclass(frozen=True)
class DpiMetrics:
    dpi: int
    pixel_scale: int
    pet_size: Size
    collapsed_size: Size
    expanded_size: Size
    expanded_pet_offset: Point
    pet_image_offset: Point
    drag_threshold_px: int
~~~

metrics_for_dpi(dpi) rejects non-positive values. Scale logical lengths with
(value * dpi + 48) // 96 and use max(1, round(BASE_PIXEL_SCALE * dpi / 96)) for
the integer sprite zoom. The common Windows values 96, 120, 144, 168, and 192
therefore use crisp 4x, 5x, 6x, 7x, and 8x nearest-neighbor pixels. Window and
control coordinates use the physical-pixel dimensions in DpiMetrics.

The input Point to calculate_window_layout(position, controls_visible, metrics)
is always the pet body's physical screen origin. For collapsed controls, the
root origin equals that point and pet offset is (0, 0). For expanded controls,
root origin is pet origin minus metrics.expanded_pet_offset. Return:

~~~python
@dataclass(frozen=True)
class WindowLayout:
    root_origin: Point
    window_size: Size
    pet_offset: Point
    pet_screen_origin: Point
~~~

safe_pet_work_area(work_area, controls_visible, metrics) returns the original
work area when controls are hidden. When controls are visible at 96 DPI, it
returns WorkArea(left + 28, top + 80, right - 28, bottom); the right inset is
expanded_size.width - expanded_pet_offset.x - pet_size.width, and every value is
derived from DpiMetrics. Passing this adjusted area and metrics.pet_size to
PetController means its existing body-size clamp reverses direction before the
expanded root crosses a monitor edge at every DPI.

The 32 by 32 sprite at base 4x zoom is 128 by 128 inside the 144 by 128 pet body.
Draw it with Canvas anchor="nw" at layout.pet_offset +
metrics.pet_image_offset, which is (8, 0) at 96 DPI. The state position and
pointer offset refer to the 144 by 128 body origin; the image tag supplies the
actual drag/click hit target. Scale the 8-pixel side padding in DpiMetrics just
like every other logical coordinate.

- [ ] **Step 4: Implement Tk color conversion and cached PhotoImages**

tk_color_rows() converts each row to Tk's braced color-list form, replacing None with the transparent key color. SpriteCache accepts a photo_factory callable so tests do not need a display:

~~~python
class SpriteCache:
    def __init__(self, photo_factory, scale: int = 4, transparent_color: str = "#FF00FF") -> None:
        self.photo_factory = photo_factory
        self.scale = scale
        self.transparent_color = transparent_color
        self._cache: dict[tuple[SkinId, Pose, int, Direction], object] = {}

    def get(self, skin: SkinId, pose: Pose, frame_index: int, direction: Direction):
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
~~~

Keep the zoomed images referenced by the cache until clear() or window shutdown.
The DPI-change path calls clear(new_metrics.pixel_scale) before drawing the next
frame so the cache cannot return images rendered for the old monitor DPI.

- [ ] **Step 5: Run gesture, layout, and cache tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gesture_layout tests.test_sprite_cache -v
~~~

Expected: nine tests pass.

- [ ] **Step 6: Commit interaction primitives**

~~~powershell
git add mikan_pet/core/gesture.py mikan_pet/core/window_layout.py mikan_pet/ui tests/test_gesture_layout.py tests/test_sprite_cache.py
git commit -m "feat: add pet interaction primitives"
~~~

---

### Task 7: Transparent Animated Pet Window

**Files:**
- Create: mikan_pet/ui/dpi.py
- Create: mikan_pet/ui/pet_window.py
- Create: tests/test_dpi.py
- Create: tests/test_pet_window.py

**Interfaces:**
- Consumes: PetController, SpriteCache, MonitorService, MediaKeyService,
  PointerGesture, BASE_DPI, DpiMetrics, calculate_window_layout(), and
  AppSettings.
- Produces: dpi_from_wparam(), DpiWatcher.install()/close(),
  AnimationClock, configure_pet_root(), context_menu_labels(), and
  PetWindow.run()/close_after()/snapshot_settings()/close().

- [ ] **Step 1: Write failing tests for root configuration and menu state**

~~~python
# tests/test_pet_window.py
import unittest
from unittest.mock import Mock, call

from mikan_pet.core.types import Pose
from mikan_pet.ui.pet_window import AnimationClock, configure_pet_root, context_menu_labels


class PetWindowHelpersTests(unittest.TestCase):
    def test_configures_borderless_transparent_topmost_root(self) -> None:
        root = Mock()
        configure_pet_root(root, "#FF00FF", True)
        root.overrideredirect.assert_called_once_with(True)
        root.configure.assert_called_once_with(bg="#FF00FF")
        root.wm_attributes.assert_has_calls(
            [call("-transparentcolor", "#FF00FF"), call("-topmost", True)]
        )

    def test_menu_label_reflects_walking_state(self) -> None:
        self.assertIn("Berhenti berjalan", context_menu_labels(True))
        self.assertIn("Mulai berjalan", context_menu_labels(False))
        self.assertIn("Pilih skin", context_menu_labels(True))
        self.assertIn("Always on top", context_menu_labels(True))
        self.assertIn("Reset posisi", context_menu_labels(True))
        self.assertIn("Keluar", context_menu_labels(True))

    def test_animation_clock_advances_and_resets_on_pose_change(self) -> None:
        clock = AnimationClock(frame_ms=180)
        self.assertEqual(0, clock.advance(Pose.WALK, 0, frame_count=2))
        self.assertEqual(0, clock.advance(Pose.WALK, 179, frame_count=2))
        self.assertEqual(1, clock.advance(Pose.WALK, 1, frame_count=2))
        self.assertEqual(0, clock.advance(Pose.IDLE, 180, frame_count=10))


if __name__ == "__main__":
    unittest.main()
~~~

Create tests/test_dpi.py without constructing Tk or touching a real HWND:

~~~python
import unittest
from unittest.mock import Mock

from mikan_pet.ui.dpi import WM_DPICHANGED, DpiWatcher, dpi_from_wparam


class DpiWatcherTests(unittest.TestCase):
    def test_extracts_new_dpi_from_wparam(self) -> None:
        self.assertEqual(144, dpi_from_wparam(144 | (144 << 16)))

    def test_schedules_callback_and_applies_suggested_rectangle(self) -> None:
        root = Mock()
        backend = Mock()
        backend.read_suggested_rect.return_value = (100, 200, 400, 520)
        callback = Mock()
        watcher = DpiWatcher(root, callback, backend)
        watcher.handle_message(WM_DPICHANGED, 144 | (144 << 16), 1234)
        backend.apply_suggested_rect.assert_called_once_with((100, 200, 400, 520))
        root.after_idle.assert_called_once()
        root.after_idle.call_args.args[0]()
        callback.assert_called_once_with(144, (100, 200, 400, 520))

    def test_install_resolves_top_level_hwnd_and_reports_initial_dpi(self) -> None:
        root = Mock()
        root.winfo_id.return_value = 123
        backend = Mock()
        backend.resolve_top_level.return_value = 456
        backend.get_window_dpi.return_value = 144
        watcher = DpiWatcher(root, Mock(), backend)
        self.assertEqual(144, watcher.install())
        root.update_idletasks.assert_called_once()
        backend.resolve_top_level.assert_called_once_with(123)
        backend.install_subclass.assert_called_once()


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the window-helper tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pet_window -v
~~~

Expected: import failures because mikan_pet.ui.dpi and pet_window do not exist.

- [ ] **Step 3: Implement the HWND DPI watcher**

In mikan_pet/ui/dpi.py, keep Win32 mechanics behind an injectable backend.
dpi_from_wparam() returns wParam & 0xFFFF. The production backend must:

1. obtain root.winfo_id() after root.update_idletasks(), then use
   win32gui.GetParent() when it returns Tk's child wrapper; retain the resulting
   nonzero top-level HWND and cover this resolution with an injected-backend
   test;
2. read its starting DPI with user32.GetDpiForWindow, falling back to 96 only
   when that API is unavailable;
3. subclass the window using win32gui.SetWindowLong(hwnd,
   win32con.GWL_WNDPROC, callback), retaining both the previous procedure and a
   strong reference to the Python callback;
4. on WM_DPICHANGED (0x02E0), decode the RECT pointed to by lParam, immediately
   apply the suggested x, y, width, and height using SetWindowPos with
   SWP_NOZORDER | SWP_NOACTIVATE, and schedule the UI callback with
   root.after_idle();
5. delegate every other message with win32gui.CallWindowProc; and
6. restore the previous window procedure exactly once during close, before Tk
   destroys the HWND.

DpiWatcher.handle_message() is independently testable as shown above. Ignore a
late DPI callback after close. WM_DPICHANGED can arrive inside a native window
callback, so all Tk widget mutation occurs only in the scheduled after_idle
callback, never directly in the subclass procedure.

- [ ] **Step 4: Implement window setup, Canvas visuals, and native menu**

configure_pet_root() must call overrideredirect(True), configure(bg=transparent_color), wm_attributes("-transparentcolor", transparent_color), and wm_attributes("-topmost", requested_value). Set the root title to "Mikan Pet".

PetWindow creates one Canvas with highlightthickness=0 and the same transparent key background. Draw:

- one cached pet image tagged pet;
- three pixel-style button groups tagged media_previous, media_play_pause, and media_next;
- each button as a cream rectangle with dark outline and brown offset shadow;
- text glyphs "|<", ">", and ">|" using TkFixedFont;
- the play/pause button in Mikan orange;
- all bubble items additionally tagged controls so Canvas item state can be switched together.

At 96 DPI, use the 200 by 208 expanded coordinate system: the three 48 by 48
button hit regions start at (16, 12), (76, 12), and (136, 12); draw each visible
face as 44 by 44 with a 4-pixel down-right shadow. Place two small cream
connector pixels between the center bubble and pet, then place the pet body at
(28, 80) and its 128 by 128 image at (36, 80). Scale every coordinate and stroke
width through DpiMetrics. In collapsed mode the root is 144 by 128 and the image
is at (8, 0). Keep all clickable rectangles entirely within the declared window
size.

Use this constructor boundary; dpi_watcher_factory defaults to DpiWatcher and is
injectable for the window tests:

~~~python
def __init__(
    self,
    root,
    controller: PetController,
    sprite_cache: SpriteCache,
    monitor_service: MonitorService,
    media_service: MediaKeyService,
    on_settings_changed: Callable[[AppSettings], None],
    dpi_watcher_factory=DpiWatcher,
) -> None:
~~~

Realize the root, query its initial DPI, create metrics_for_dpi(initial_dpi), set
Tk's point scaling with root.tk.call("tk", "scaling", initial_dpi / 72.0), set
the SpriteCache integer scale, construct PointerGesture with
metrics.drag_threshold_px, then install the DpiWatcher. Canvas geometry and all
pet/control coordinates are derived from the current DpiMetrics; do not mix
96-DPI constants into event handling.

AnimationClock owns last_pose and elapsed_ms. advance(pose, elapsed_ms,
frame_count) rejects non-positive frame_count, resets elapsed_ms to zero and
returns frame zero whenever pose changes, otherwise adds the non-negative elapsed
time, reduces it modulo frame_ms * frame_count, and returns
elapsed_ms // frame_ms. PetWindow creates exactly one clock during initialization;
skin changes may keep the current phase, while every pose transition starts from
frame zero.

Build a Tk Menu with walking toggle, a Skin submenu with three radiobuttons, an always-on-top checkbutton, reset position, a separator, and exit. The visible walking label must be rebuilt or itemconfigured after every toggle.

- [ ] **Step 5: Implement click, drag, media, and skin event handlers**

Use PointerGesture for the pet tag. On press, convert the physical
pointer-to-body-origin offset to a 96-DPI logical drag offset, remember the
current monitor id as last_intersected_id, but do not change PetController motion
yet. During motion, feed PointerGesture first. On the first event at or beyond
the threshold call controller.begin_drag(); PetController then remembers whether
it was automatic or stopped. While dragged, derive the proposed physical
position with position_from_pointer() and the current DPI, call
controller.drag_to(proposed_position) without clamping, update
last_intersected_id through MonitorService.drag_target(), and apply window
geometry directly. This is essential at an adjacent seam or a gap: never clamp
to either monitor during pointer motion. On release, recompute the final proposed
position from the release pointer in case no final motion event arrived:

~~~python
result = self.gesture.release(Point(event.x_root, event.y_root))
if result is GestureResult.CLICK:
    visible = not self.controller.state.controls_visible
    self.controller.set_controls_visible(visible)
    target = self.monitor_service.current_for(
        self.controller.state.position,
        self.metrics.pet_size,
    )
else:
    if self.controller.state.motion is not MotionMode.DRAGGING:
        self.controller.begin_drag()
    self.controller.drag_to(
        position_from_pointer(
            Point(event.x_root, event.y_root),
            self.logical_drag_offset,
            self.metrics.dpi,
        )
    )
    target = self.monitor_service.drag_target(
        self.controller.state.position,
        self.metrics.pet_size,
        self.last_intersected_id,
    )
self.controller.place_within(
    safe_pet_work_area(target.work_area, self.controller.state.controls_visible, self.metrics),
    self.metrics.pet_size,
)
if result is GestureResult.DRAG:
    self.controller.end_drag()
self._apply_window_layout()
self._settings_changed()
~~~

A click never enters or ends drag mode, so toggling bubbles does not wake a
sleeping pet or resume a stopped pet. A real drag restores only the motion mode
remembered by PetController.

Do not bind the media controls to the pet click handler. Each control calls MediaKeyService.send(action), then controller.react(), then redraws immediately.

Skin menu callbacks call controller.set_skin(SkinId(value)), redraw, update the
selected Tk variable, and persist. The always-on-top callback updates both
controller state and root wm_attributes. Reset uses
monitor_service.primary().work_area with default_position() and persists.

- [ ] **Step 6: Implement the animation, movement, and DPI-change loop**

Schedule one callback every 50 ms with root.after(). Use time.monotonic_ns() to calculate elapsed milliseconds and cap one update at 200 ms so resume-from-sleep does not jump across a monitor. Each tick:

1. refresh the active monitor from the current pet body rectangle;
2. derive movement_area = safe_pet_work_area(active.work_area, controls_visible, self.metrics);
3. call controller.tick(elapsed_ms, movement_area, self.metrics.pet_size,
   dpi_scale=self.metrics.dpi / BASE_DPI);
4. choose frame index with animation_clock.advance(current_pose, elapsed_ms,
   frame_count(current_pose));
5. fetch the cached image for skin, pose, frame, and direction;
6. update the Canvas image and window geometry;
7. schedule the next tick unless closing.

Apply calculate_window_layout(position, controls_visible, self.metrics) after
every movement or control-visibility change. Geometry format is:

~~~python
f"{width}x{height}{x:+d}{y:+d}"
~~~

When controls become visible, immediately clamp the pet origin through
controller.place_within() using safe_pet_work_area() with current metrics before applying geometry. This
keeps the whole expanded window visible and lets the next automatic tick reverse
direction at the same adjusted boundary instead of repeatedly nudging the pet.

When controls are hidden, shrink the root to metrics.collapsed_size while keeping
the pet's screen origin unchanged. This prevents a transparent control area from
intercepting desktop clicks.

_on_dpi_changed(new_dpi, suggested_rect) must set Tk point scaling, replace
self.metrics with metrics_for_dpi(new_dpi), clear the SpriteCache with the new
integer pixel scale, and rebuild the Canvas controls at the new physical-pixel
coordinates. Also call gesture.set_threshold(new_metrics.drag_threshold_px).
If motion is DRAGGING, query the current physical pointer position and recompute
the unbounded body origin with position_from_pointer() and the stored logical
drag offset; do not clamp until pointer release. Otherwise, derive a proposed pet
origin from the suggested root rectangle plus the new pet offset and clamp it
through the active monitor's DPI-adjusted safe work area. Update controller
position and apply the final layout. This honors WM_DPICHANGED placement, avoids
a cross-monitor drag jump, and keeps the complete pet/controls on screen after
release. State coordinates remain physical pixels between events.

snapshot_settings() returns AppSettings from controller state, the current
monitor id, and current pet position. close() is idempotent: cancel the last
after identifier, restore the DPI window procedure, and destroy the root. Returning from mainloop lets the
application coordinator perform the final settings save.
close_after(delay_ms) schedules close() through root.after() and exists only to
support the bounded GUI packaging smoke path.

Register root.report_callback_exception. Its handler calls
controller.stop_and_idle() so recovery is deterministic from WALK, SLEEP, or
REACT, cancels the failing animation callback, and shows one concise error dialog
while leaving the context menu and Exit action available.

- [ ] **Step 7: Run automated window tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pet_window -v
.\.venv\Scripts\python.exe -m unittest tests.test_dpi -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

Expected: DPI watcher tests and all automated tests pass.

- [ ] **Step 8: Commit the window**

~~~powershell
git add mikan_pet/ui/dpi.py mikan_pet/ui/pet_window.py tests/test_dpi.py tests/test_pet_window.py
git commit -m "feat: add transparent animated pet window"
~~~

---

### Task 8: Application Composition, Persistence Hooks, and Smoke Mode

**Files:**
- Create: mikan_pet/app.py
- Create: mikan_pet/__main__.py
- Create: tests/test_app.py

**Interfaces:**
- Consumes: every core, service, and UI interface from Tasks 1–7.
- Produces: MikanPetApplication.run(), validate_smoke_contract(),
  run_gui_smoke_test(), and main(argv=None).

- [ ] **Step 1: Write failing composition and smoke tests**

~~~python
# tests/test_app.py
import unittest
from unittest.mock import Mock, patch

from mikan_pet.app import (
    MikanPetApplication,
    default_window_factory,
    run_gui_smoke_test,
    validate_smoke_contract,
)
from mikan_pet.services.settings import default_settings


class AppTests(unittest.TestCase):
    def test_duplicate_instance_exits_without_window(self) -> None:
        singleton = Mock()
        singleton.acquire.return_value = False
        window_factory = Mock()
        app = MikanPetApplication(
            singleton=singleton,
            settings_store=Mock(),
            monitor_service=Mock(),
            media_service=Mock(),
            window_factory=window_factory,
        )
        self.assertEqual(0, app.run())
        window_factory.assert_not_called()

    def test_normal_run_loads_and_saves_settings(self) -> None:
        singleton = Mock()
        singleton.acquire.return_value = True
        store = Mock()
        store.load.return_value = default_settings()
        window = Mock()
        window.snapshot_settings.return_value = default_settings()
        app = MikanPetApplication(
            singleton=singleton,
            settings_store=store,
            monitor_service=Mock(),
            media_service=Mock(),
            window_factory=Mock(return_value=window),
        )
        self.assertEqual(0, app.run())
        window.run.assert_called_once()
        store.save.assert_called_with(default_settings())
        window.close.assert_called_once()
        singleton.release.assert_called_once()

    def test_smoke_contract_validates_registry_and_media_map(self) -> None:
        self.assertEqual([], validate_smoke_contract())

    def test_gui_smoke_is_bounded_and_always_closes(self) -> None:
        window = Mock()
        factory = Mock(return_value=window)
        self.assertEqual(0, run_gui_smoke_test(window_factory=factory))
        window.close_after.assert_called_once_with(1500)
        window.run.assert_called_once()
        window.close.assert_called_once()

    def test_window_factory_fails_before_tk_when_dpi_awareness_is_unavailable(self) -> None:
        with patch(
            "mikan_pet.app.enable_per_monitor_dpi_awareness",
            return_value=False,
        ):
            with self.assertRaises(RuntimeError):
                default_window_factory(
                    default_settings(),
                    Mock(),
                    Mock(),
                    Mock(),
                )


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run application tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app -v
~~~

Expected: import failure because mikan_pet.app does not exist.

- [ ] **Step 3: Implement dependency composition and guaranteed cleanup**

MikanPetApplication.run() follows this control flow:

~~~python
def run(self) -> int:
    if not self.singleton.acquire():
        return 0
    window = None
    try:
        settings = self.settings_store.load()
        window = self.window_factory(
            settings=settings,
            monitor_service=self.monitor_service,
            media_service=self.media_service,
            on_settings_changed=self.settings_store.save,
        )
        window.run()
        return 0
    finally:
        try:
            if window is not None:
                try:
                    self.settings_store.save(window.snapshot_settings())
                finally:
                    window.close()
        finally:
            self.singleton.release()
~~~

The production default_window_factory() has this signature:

~~~python
def default_window_factory(
    settings: AppSettings,
    monitor_service: MonitorService,
    media_service: MediaKeyService,
    on_settings_changed: Callable[[AppSettings], None],
) -> PetWindow:
~~~

It:

1. calls enable_per_monitor_dpi_awareness() before creating Tk and raises a
   startup RuntimeError if it cannot confirm per-monitor awareness;
2. refreshes MonitorService;
3. resolves or recovers the saved position;
4. creates PetState from AppSettings;
5. creates PetController, SpriteCache, and PetWindow; PetWindow realizes the
   HWND and installs its DpiWatcher;
6. provides SettingsStore.save as the change callback.

Catch exceptions only at the outer main() boundary. In normal GUI mode, show a concise tkinter.messagebox error and return 1. Do not swallow callback errors silently.

- [ ] **Step 4: Implement command-line entry and side-effect-free smoke mode**

main(argv=None) recognizes:

- --smoke-test: run validate_smoke_contract(), return 0 when no errors and 1 otherwise, without acquiring the mutex, creating Tk, or sending media keys;
- --gui-smoke-test: use default settings and the production window factory,
  schedule PetWindow.close() after 1500 ms, run the real Tk loop, and return 0;
  do not read/write user settings, acquire the production mutex, or send a media
  key;
- --version: print 0.1.0 and return 0;
- no arguments: launch the real application;
- any other argument: return 2.

validate_smoke_contract() combines validate_registry() with checks that MEDIA_VIRTUAL_KEYS contains exactly PREVIOUS, PLAY_PAUSE, and NEXT and that settings defaults use schema version 1.

run_gui_smoke_test() is a bounded packaging diagnostic, not a user feature. It
must exercise the actual Tk root, DPI setup, Canvas creation, procedural sprite
rasterization, PhotoImage caching, and clean close path. Keep its root/window
factories injectable so tests can assert the 1500-ms scheduling without opening a
real window; installed and freshly extracted packages exercise the real path in
Task 10.

Create mikan_pet/__main__.py:

~~~python
from mikan_pet.app import main


if __name__ == "__main__":
    raise SystemExit(main())
~~~

- [ ] **Step 5: Run integration and full test suites**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m mikan_pet --smoke-test
.\.venv\Scripts\python.exe -m mikan_pet --gui-smoke-test
~~~

Expected: all tests pass, the non-GUI smoke mode exits without a window, and the
GUI smoke mode briefly renders and exits with code 0.

- [ ] **Step 6: Run the source application manually**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m mikan_pet
~~~

Verify Mikan appears, walks, idles, sleeps, reverses at work-area edges, can be stopped and resumed, can be dragged, switches all three skins, toggles control bubbles, persists changes after relaunch, and exits from its menu. Test media buttons only while a disposable media session is open so state changes are intentional.

- [ ] **Step 7: Commit the runnable application**

~~~powershell
git add mikan_pet/app.py mikan_pet/__main__.py tests/test_app.py
git commit -m "feat: compose runnable Mikan Pet app"
~~~

---

### Task 9: Icon, Portable Build, and Windows Installer

**Files:**
- Create: scripts/generate_icon.py
- Create: scripts/build.ps1
- Create: installer/MikanPet.iss
- Create: packaging/MikanPet.manifest
- Create: tests/test_packaging.py
- Create at build time and ignore: assets/MikanPet.ico
- Modify: .gitignore

**Interfaces:**
- Consumes: rasterize_frame(), Python environment, PyInstaller 6.22.2, Pillow 12.2.0, PowerShell Compress-Archive, and Inno Setup ISCC.exe.
- Produces: dist/MikanPet/MikanPet.exe, dist/MikanPet-portable-x64.zip, and dist/MikanPet-Setup-x64.exe.

- [ ] **Step 1: Write failing packaging-contract tests**

~~~python
# tests/test_packaging.py
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_inno_script_is_per_user_win10_x64(self) -> None:
        text = (ROOT / "installer" / "MikanPet.iss").read_text(encoding="utf-8")
        for directive in (
            "ArchitecturesAllowed=x64compatible",
            "ArchitecturesInstallIn64BitMode=x64compatible",
            "MinVersion=10.0",
            "PrivilegesRequired=lowest",
            "AppMutex={#MyAppMutex}",
        ):
            self.assertIn(directive, text)
        self.assertIn('#define MyAppId "{{8BC15C2A-D035-4EE2-A984-39137E4294E1}"', text)
        self.assertIn('#define MyOutputBaseFilename "MikanPet-Setup-x64"', text)
        self.assertIn("OutputBaseFilename={#MyOutputBaseFilename}", text)
        self.assertIn(r'#define MyAppMutex "Local\MikanPet"', text)
        self.assertIn("#if MySmokeBuild == 0", text)

    def test_build_script_runs_tests_and_produces_both_packages(self) -> None:
        text = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("-m unittest discover", text)
        self.assertIn("-m PyInstaller", text)
        self.assertIn('--paths "$ProjectRoot"', text)
        self.assertIn("MikanPet-portable-x64.zip", text)
        self.assertIn("MikanPet-Setup-x64.exe", text)
        self.assertIn('--manifest "$ProjectRoot\\packaging\\MikanPet.manifest"', text)
        self.assertIn("AMD64", text)
        self.assertIn("0x8664", text)

    def test_manifest_declares_per_monitor_v2(self) -> None:
        text = (ROOT / "packaging" / "MikanPet.manifest").read_text(encoding="utf-8")
        self.assertIn("PerMonitorV2,PerMonitor", text)
        self.assertIn('level="asInvoker"', text)


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run packaging tests and confirm failure**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_packaging -v
~~~

Expected: FileNotFoundError for the missing build, manifest, and installer files.

- [ ] **Step 3: Generate the deterministic application icon**

scripts/generate_icon.py must:

1. call rasterize_frame(SkinId.MIKAN, Pose.IDLE, 0, Direction.RIGHT);
2. create a 32 by 32 transparent RGBA Pillow image;
3. paint each non-None pixel from its hex color;
4. resize with Image.Resampling.NEAREST to 256 by 256;
5. create assets if absent;
6. save assets/MikanPet.ico with sizes 16, 24, 32, 48, 64, 128, and 256.

Add assets/MikanPet.ico to .gitignore because it is deterministically generated by the build.

- [ ] **Step 4: Add the packaged-process DPI manifest**

Create packaging/MikanPet.manifest as UTF-8 XML. Include the Microsoft Windows
settings namespaces and declare both the modern and fallback values:

~~~xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1"
          xmlns:asmv3="urn:schemas-microsoft-com:asm.v3"
          manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <asmv3:application>
    <asmv3:windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2,PerMonitor</dpiAwareness>
    </asmv3:windowsSettings>
  </asmv3:application>
</assembly>
~~~

The manifest is the authoritative declaration for the packaged executable.
enable_per_monitor_dpi_awareness() remains necessary for source-mode launches
and must still run before Tk creates a window.

- [ ] **Step 5: Add the per-user Inno Setup script**

Use this setup contract, which works with Inno Setup 6.7.3 and newer:

~~~ini
#define MyAppName "Mikan Pet"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Mikan Pet"
#define MyAppExeName "MikanPet.exe"
#ifndef MyAppId
  #define MyAppId "{{8BC15C2A-D035-4EE2-A984-39137E4294E1}"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "MikanPet-Setup-x64"
#endif
#ifndef MySmokeBuild
  #define MySmokeBuild 0
#endif
#ifndef MyAppMutex
  #define MyAppMutex "Local\MikanPet"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Mikan Pet
DefaultGroupName=Mikan Pet
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=lowest
AppMutex={#MyAppMutex}
OutputDir=..\dist
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile=..\assets\MikanPet.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Shortcut tambahan:"; Flags: unchecked

[Files]
Source: "..\dist\MikanPet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

#if MySmokeBuild == 0
[Icons]
Name: "{group}\Mikan Pet"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Mikan Pet"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Jalankan Mikan Pet"; Flags: nowait postinstall skipifsilent
#endif
~~~

The production AppMutex prevents install, update, or uninstall while the pet is
running. The smoke preprocessor flag must omit every [Icons] and [Run] entry so
a test installer cannot create or remove the production Start Menu/Desktop
shortcuts; its compiler command also overrides MyAppMutex with a unique name.
Do not add elevation overrides. The app stores mutable settings in AppData,
never in the installation folder.

- [ ] **Step 6: Implement the fail-fast PowerShell build**

scripts/build.ps1 accepts -Python and -SkipInstaller. -Python defaults to the
current interpreter returned by (Get-Command python).Source. It performs these
steps from the repository root:

1. query pointer width and platform.machine() from the selected interpreter;
   require 64 bits and machine AMD64 or x86_64, rejecting ARM64 Python rather
   than publishing an ARM64 executable with x64 filenames, then print the
   interpreter version;
2. run python -m unittest discover -s tests -v;
3. run scripts/generate_icon.py;
4. remove only the repository-local build directory, dist\MikanPet directory,
   dist\MikanPet-portable-x64.zip, dist\MikanPet-Setup-x64.exe, and generated
   root MikanPet.spec after resolving and verifying each target is under the
   repository root;
5. run:

~~~powershell
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name MikanPet --paths "$ProjectRoot" --manifest "$ProjectRoot\packaging\MikanPet.manifest" --icon "$ProjectRoot\assets\MikanPet.ico" "$ProjectRoot\mikan_pet\__main__.py"
~~~

6. read the PE header of dist\MikanPet\MikanPet.exe and require Machine
   0x8664 (IMAGE_FILE_MACHINE_AMD64);
7. run dist\MikanPet\MikanPet.exe --smoke-test and fail on nonzero exit;
8. create dist\MikanPet-portable-x64.zip from the complete one-folder build;
9. unless -SkipInstaller is present, find ISCC.exe first on PATH, then under
   Program Files\Inno Setup 7, Program Files (x86)\Inno Setup 6, and the
   equivalent Inno Setup 7 and 6 directories beneath
   $env:LOCALAPPDATA\Programs;
10. run ISCC.exe with /Qp installer\MikanPet.iss;
11. always verify and hash the portable ZIP; when -SkipInstaller is absent,
    also verify and hash the installer. -SkipInstaller is explicitly a
    portable-only build and must not require an old installer to exist.

Use $ErrorActionPreference = "Stop" and check $LASTEXITCODE after every external
program. Parse e_lfanew and the two-byte COFF Machine field using PowerShell
binary reads or a short inline call to the selected Python; do not infer
architecture from the filename. Never delete a path that does not resolve beneath
$ProjectRoot.

- [ ] **Step 7: Run packaging-contract tests**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest tests.test_packaging -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

Expected: packaging-contract tests and the full suite pass.

- [ ] **Step 8: Reconcile and verify the pinned build tools**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m pip show pywin32 Pillow pyinstaller
~~~

Expected: the venv contains pywin32 312, Pillow 12.2.0, and PyInstaller 6.22.2.

- [ ] **Step 9: Install Inno Setup only if the compiler is absent**

Check:

~~~powershell
$Candidates = @(
  (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
  'C:\Program Files\Inno Setup 7\ISCC.exe',
  'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
  (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
  (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$Candidates
~~~

If no path is returned, install the available signed winget package:

~~~powershell
winget install --id JRSoftware.InnoSetup --exact --accept-source-agreements --accept-package-agreements
~~~

Then rerun the same candidate discovery and require exactly one usable ISCC.exe;
do not assume a machine-wide install path. Do not install unrelated packaging
tools.

- [ ] **Step 10: Build both release artifacts**

Run:

~~~powershell
.\scripts\build.ps1 -Python '.\.venv\Scripts\python.exe'
~~~

Expected:

~~~text
dist\MikanPet\MikanPet.exe
dist\MikanPet-portable-x64.zip
dist\MikanPet-Setup-x64.exe
~~~

The executable smoke test exits 0, and the build script prints SHA-256 hashes for the ZIP and installer.

- [ ] **Step 11: Commit packaging sources**

~~~powershell
git add .gitignore scripts installer packaging/MikanPet.manifest tests/test_packaging.py requirements-build.txt
git commit -m "build: add Windows packages"
~~~

Do not commit .venv, generated icons, PyInstaller work folders, executables, ZIP files, or installer output.

---

### Task 10: User Documentation and End-to-End Release Verification

**Files:**
- Create: README.md
- Create: docs/testing-checklist.md

**Interfaces:**
- Consumes: the complete application and both Task 9 packages.
- Produces: user-facing operating/build instructions and final verification evidence.

- [ ] **Step 1: Write the usage and build documentation**

README.md must contain these concrete sections:

- Install: run MikanPet-Setup-x64.exe, choose the optional Desktop shortcut, and launch from Start Menu.
- Portable: extract every file from MikanPet-portable-x64.zip before running MikanPet.exe.
- Controls: click toggles bubbles; drag moves; right-click opens walk/skin/topmost/reset/exit; list all three media buttons.
- Skins: Mikan, Byte, and Mochi.
- Settings path: %APPDATA%\MikanPet\settings.json.
- Troubleshooting: active media-session requirement, reset off-screen position, single-instance behavior, and how to exit.
- Security note: the local development build is unsigned and Windows SmartScreen may show an Unknown publisher warning; do not claim a signature.
- Development: create .venv, install requirements-build.txt, run unittest, source launch, and scripts\build.ps1.
- Supported systems: Windows 10/11 x64 and Windows 11 ARM via x64 emulation.

docs/testing-checklist.md must list the manual matrix from the approved spec, including 100%, 150%, and 200% scaling; one and multiple monitors; Spotify, YouTube, and one native player; persistence; duplicate launch; installer; portable archive; and uninstall.

- [ ] **Step 2: Verify documentation references exact existing commands and artifacts**

Run:

~~~powershell
rg -n "MikanPet-Setup-x64.exe|MikanPet-portable-x64.zip|scripts\\build.ps1|%APPDATA%\\MikanPet" README.md docs/testing-checklist.md
~~~

Expected: every artifact and command is present with the exact spelling used by the build.

- [ ] **Step 3: Commit documentation**

~~~powershell
git add README.md docs/testing-checklist.md
git commit -m "docs: add Mikan Pet usage and test guide"
~~~

- [ ] **Step 4: Run final automated verification from the clean venv**

Run:

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m mikan_pet --smoke-test
.\scripts\build.ps1 -Python '.\.venv\Scripts\python.exe'
git diff --check
git status --short
~~~

Expected: all tests pass, smoke mode returns 0, both packages are rebuilt, git
diff reports no whitespace errors, and git status has no tracked or untracked
output.

- [ ] **Step 5: Smoke-test fresh portable and installed copies in temporary directories**

First extract the completed portable ZIP to a new temporary directory; do not
launch the copy inside dist directly. Then compile a smoke-only installer from
the same Inno source with a unique AppId and
MySmokeBuild=1 so it creates no Start Menu shortcut, Desktop shortcut, or
post-install Run entry.
Do not install the production artifact for this test because sharing its AppId
could overwrite an existing user's uninstall registration. Use unique,
nonexistent install and compiler-output directories under the resolved user Temp
root:

~~~powershell
$TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\','/')
$TempBoundary = $TempRoot + [System.IO.Path]::DirectorySeparatorChar
$Token = [Guid]::NewGuid().ToString('N')
$PortableDir = [System.IO.Path]::GetFullPath((Join-Path $TempRoot "MikanPet-Portable-$Token"))
$SmokeDir = [System.IO.Path]::GetFullPath((Join-Path $TempRoot "MikanPet-Install-$Token"))
$SmokePackageDir = [System.IO.Path]::GetFullPath((Join-Path $TempRoot "MikanPet-Package-$Token"))
foreach ($Target in @($PortableDir, $SmokeDir, $SmokePackageDir)) {
    if (-not $Target.StartsWith($TempBoundary, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Smoke target escaped Temp: $Target"
    }
    if (Test-Path -LiteralPath $Target) { throw "Smoke target already exists: $Target" }
}
Expand-Archive -LiteralPath '.\dist\MikanPet-portable-x64.zip' -DestinationPath $PortableDir
$PortableExecutables = @(Get-ChildItem -LiteralPath $PortableDir -Filter MikanPet.exe -File -Recurse)
if ($PortableExecutables.Count -ne 1) {
    throw "Expected one fresh portable executable, found $($PortableExecutables.Count)"
}
$PortableExe = $PortableExecutables[0].FullName
foreach ($Argument in @('--smoke-test', '--gui-smoke-test')) {
    $Process = Start-Process -FilePath $PortableExe -ArgumentList $Argument -Wait -PassThru
    if ($Process.ExitCode -ne 0) { throw "Portable $Argument failed: $($Process.ExitCode)" }
}
New-Item -ItemType Directory -Path $SmokePackageDir | Out-Null

$Iscc = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    'C:\Program Files\Inno Setup 7\ISCC.exe',
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $Iscc) { throw "ISCC.exe not found" }
$SmokeBaseName = "MikanPet-Smoke-Setup-$Token"
& $Iscc "/DMyAppId=MikanPet.Smoke.$Token" "/DMyAppMutex=Local\MikanPet.Smoke.$Token" "/DMyOutputBaseFilename=$SmokeBaseName" "/DMySmokeBuild=1" "/O$SmokePackageDir" '.\installer\MikanPet.iss'
if ($LASTEXITCODE -ne 0) { throw "Smoke installer compile failed: $LASTEXITCODE" }
$Installer = Join-Path $SmokePackageDir "$SmokeBaseName.exe"
if (-not (Test-Path -LiteralPath $Installer)) { throw "Smoke installer missing" }

$InstallDirArg = '/DIR="{0}"' -f $SmokeDir
$Process = Start-Process -FilePath $Installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',$InstallDirArg) -Wait -PassThru -WindowStyle Hidden
if ($Process.ExitCode -ne 0) { throw "Installer exit code: $($Process.ExitCode)" }
$InstalledExe = Join-Path $SmokeDir 'MikanPet.exe'
if (-not (Test-Path -LiteralPath $InstalledExe)) { throw "Installed executable missing" }
foreach ($Argument in @('--smoke-test', '--gui-smoke-test')) {
    $Process = Start-Process -FilePath $InstalledExe -ArgumentList $Argument -Wait -PassThru
    if ($Process.ExitCode -ne 0) { throw "Installed $Argument failed: $($Process.ExitCode)" }
}
~~~

Locate exactly one unins*.exe directly inside $SmokeDir. Resolve it and require
that it begins with the resolved $SmokeDir plus a directory separator before
running it with /VERYSILENT /SUPPRESSMSGBOXES /NORESTART. Verify MikanPet.exe
no longer exists. Finally, revalidate all three smoke paths against $TempBoundary
before removing only the fresh portable directory, smoke compiler-output
directory, and any empty install directory. These are GUID-named test data under
Temp; report their deletion in the task result. Both --gui-smoke-test invocations
must visibly render the real packaged Tk window for about 1.5 seconds and exit
without a separately installed Python.

- [ ] **Step 6: Perform final interactive Windows 11 verification**

Launch dist\MikanPet\MikanPet.exe once. Check the items in docs/testing-checklist.md that this host can exercise:

- transparency and topmost;
- movement, reversal, idle, blink, sleep, and stopped mode;
- control hide/show and drag threshold;
- three skin changes without restart;
- multi-monitor transfer if another display is connected;
- mixed-DPI transfer if differently scaled displays are connected: verify the
  pet resizes, remains crisp, stays on-screen, and retains usable control hit
  targets after crossing in both directions;
- at least two display-scaling values available on the host, relaunching when a
  system setting change requires it;
- media control only with a deliberately opened disposable session;
- persistence after exit and relaunch;
- second launch produces no second pet.

Exit from the context menu. Record unavailable hardware combinations as not
locally verified; do not claim they passed.

- [ ] **Step 7: Complete or explicitly qualify the supported-OS matrix**

Record dated results in docs/testing-checklist.md for:

- Windows 11 x64 on the current physical host;
- Windows 10 22H2 x64 in a clean VM, testing installer, launch, controls,
  persistence, duplicate launch, and uninstall;
- 100%, 150%, and 200% DPI, plus a mixed-DPI two-monitor crossing when suitable
  hardware or a VM configuration is available;
- Windows 11 ARM running the x64 package through emulation when an ARM device or
  VM is available.

Windows 10 verification is a release gate for claiming Windows 10 support.
Windows 11 ARM and mixed-monitor rows may be marked unverified when that hardware
is unavailable, but the handoff must then call the package a release candidate
and state those exact gaps. Never turn an unexecuted checklist row into a pass.

- [ ] **Step 8: Confirm release artifacts and handoff**

Run:

~~~powershell
Get-FileHash '.\dist\MikanPet-Setup-x64.exe' -Algorithm SHA256
Get-FileHash '.\dist\MikanPet-portable-x64.zip' -Algorithm SHA256
Get-Item '.\dist\MikanPet-Setup-x64.exe','.\dist\MikanPet-portable-x64.zip' | Select-Object FullName,Length,LastWriteTime
git log --oneline --decorate -12
git status --short --branch
~~~

Expected: both files exist with nonzero length, their SHA-256 values are recorded
for this exact build, all planned commits are visible, and tracked files are
clean. Do not call hashes reproducible or stable unless a separate clean rebuild
produces byte-identical files.

---

## Packaging References Consulted

- PyInstaller stable changelog and package metadata for version 6.22.2 and
  Python 3.14 support:
  https://pyinstaller.org/en/stable/CHANGES.html
  https://pypi.org/project/pyinstaller/
- PyInstaller usage, one-folder/windowed operation, and supported Windows
  platforms:
  https://pyinstaller.org/en/stable/usage.html
  https://pyinstaller.org/en/stable/operating-mode.html
  https://pyinstaller.org/en/stable/requirements.html
- Inno Setup compiler syntax and setup directives:
  https://jrsoftware.org/ishelp/topic_compilercmdline.htm
  https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm
  https://jrsoftware.org/ishelp/topic_64bit.htm
  https://jrsoftware.org/ishelp/topic_archidentifiers.htm
  https://jrsoftware.org/ishelp/topic_setup_minversion.htm
- Microsoft process DPI-awareness and WM_DPICHANGED guidance:
  https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process
  https://learn.microsoft.com/en-us/windows/win32/hidpi/wm-dpichanged
  https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows
