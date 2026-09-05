# Mikan Pet Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four user-requested enhancements: multi-frame procedural "Zzzz Zzzz" sleep animation, floating controls hide bug fix with synchronous window/canvas layout and buffer refresh, real-time Windows GSMTC now-playing song title speech bubble, and GitHub in-place auto-update service with release CI/CD workflow.

**Architecture:** Procedural pixel-art frames render sleep letters within frame boundaries; `PetWindow` layout logic ensures atomic hiding, geometry resize, and idletasks clearing to prevent ghosting; a decoupled `MediaInfoService` reads Windows GSMTC session metadata to drive a speech bubble above the pet; an `UpdaterService` interacts with GitHub Releases API to download and in-place replace portable binaries with an automated GitHub Actions release workflow.

**Tech Stack:** Python 3.11+, Tkinter, pywin32, ctypes (Windows GSMTC / WinRT), standard-library unittest, GitHub Actions.

## Global Constraints

- Retain 100% test pass rate across existing 146 tests.
- Support Windows 10 and Windows 11 x64.
- All Tkinter GUI mutations must occur on the main event thread.
- Procedural pixel rectangles must stay strictly within `FRAME_WIDTH = 36` and `FRAME_HEIGHT = 32`.
- Media title query must be non-blocking and fail safely if no media session is active.
- Updater must update portable files in-place and not require re-running an installer.

---

### Task 1: Procedural Pixel-Art Sleep Animation ("Zzzz Zzzz")

**Files:**
- Modify: `mikan_pet/core/sprites.py:109-125`
- Test: `tests/test_sprites.py`

**Interfaces:**
- Consumes: `ColorRole`, `PixelRect`, `FrameTemplate`, `_with`, `_SLEEP_BASE`, `FRAMES`
- Produces: Expanded `Pose.SLEEP` frame sequence (4 distinct frames) with rising pixel 'Z' letters.

- [ ] **Step 1: Write failing tests for expanded sleep frames**

```python
# In tests/test_sprites.py: add test_sleep_pose_has_four_animated_frames_with_z_indicators
def test_sleep_pose_has_four_animated_frames_with_z_indicators(self) -> None:
    sleep_frames = FRAMES[Pose.SLEEP]
    self.assertEqual(4, len(sleep_frames))
    # Frame 0 is base resting, Frame 1 has small z, Frame 2 has rising Z, Frame 3 has Zzzz
    self.assertGreater(len(sleep_frames[3].rectangles), len(sleep_frames[0].rectangles))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests.test_sprites.SpriteRegistryTests.test_sleep_pose_has_four_animated_frames_with_z_indicators`
Expected: FAIL (AssertionError: 4 != 2)

- [ ] **Step 3: Implement 4-frame sleep sequence in `mikan_pet/core/sprites.py`**

Define procedural pixel rectangles for rising "Z"s:
- Small z: `_r(18, 12, 4, 3, ColorRole.LIGHT)`
- Medium Z: `_r(22, 8, 5, 4, ColorRole.LIGHT)`
- Large Zs: `_r(20, 5, 5, 4, ColorRole.LIGHT), _r(27, 4, 6, 4, ColorRole.SHADE)`
Add to `_SLEEP`:
```python
_SLEEP = (
    _with(_SLEEP_BASE, _r(28, 17, 2, 3, ColorRole.SHADE)),
    _with(_SLEEP_BASE, _r(28, 17, 2, 3, ColorRole.SHADE), _r(18, 13, 3, 3, ColorRole.LIGHT)),
    _with(_SLEEP_BASE, _r(29, 17, 1, 3, ColorRole.SHADE), _r(20, 9, 4, 3, ColorRole.LIGHT), _r(25, 6, 4, 3, ColorRole.LIGHT)),
    _with(_SLEEP_BASE, _r(29, 17, 1, 3, ColorRole.SHADE), _r(22, 5, 5, 4, ColorRole.LIGHT), _r(28, 4, 5, 4, ColorRole.SHADE)),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests/test_sprites.py`
Expected: PASS and all registry validations pass.

- [ ] **Step 5: Commit**

```bash
rtk git add mikan_pet/core/sprites.py tests/test_sprites.py
rtk git commit -m "feat: add animated Zzzz procedural frames for sleep pose"
```

---

### Task 2: Fix Floating Controls Hide Flicker and Ghosting

**Files:**
- Modify: `mikan_pet/ui/pet_window.py:376-395`
- Test: `tests/test_pet_window.py`

**Interfaces:**
- Consumes: `calculate_window_layout`, `self.canvas`, `self.root`
- Produces: Glitch-free `_apply_window_layout()` with immediate hiding, geometry update, canvas coordinate alignment, and `update_idletasks()`.

- [ ] **Step 1: Write test verifying controls item hiding and update_idletasks invocation on hide**

In `tests/test_pet_window.py`, test that toggling controls from True to False sets canvas item state to hidden before geometry shrinkage and invokes `update_idletasks()`:
```python
def test_hide_controls_clears_canvas_state_and_updates_idletasks(self) -> None:
    window, root, controller, *_ = self.make_window(controls_visible=True)
    root.update_idletasks = Mock()
    window.canvas.itemconfigure = Mock(wraps=window.canvas.itemconfigure)
    controller.set_controls_visible(False)
    window._apply_window_layout()
    window.canvas.itemconfigure.assert_any_call("controls", state="hidden")
    root.update_idletasks.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests.test_pet_window.PetWindowTests.test_hide_controls_clears_canvas_state_and_updates_idletasks`
Expected: FAIL

- [ ] **Step 3: Implement clean atomic hide ordering in `_apply_window_layout()`**

```python
    def _apply_window_layout(self) -> None:
        state = self.controller.state
        layout = calculate_window_layout(state.position, state.controls_visible, self.metrics)
        size = layout.window_size
        origin = layout.root_origin

        # 1. Hide controls immediately so they disappear before any window boundary change
        self.canvas.itemconfigure(
            "controls",
            state="normal" if state.controls_visible else "hidden",
        )
        # 2. Resize and reposition root window
        self.root.geometry(f"{size.width}x{size.height}+{origin.x}+{origin.y}")
        # 3. Reconfigure canvas dimensions and pet sprite position
        self.canvas.configure(width=size.width, height=size.height)
        image_x = layout.pet_offset.x + self.metrics.pet_image_offset.x
        image_y = layout.pet_offset.y + self.metrics.pet_image_offset.y
        self.canvas.coords("pet", image_x, image_y)
        # 4. Clear transparent desktop ghost artifacts
        self.root.update_idletasks()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests/test_pet_window.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add mikan_pet/ui/pet_window.py tests/test_pet_window.py
rtk git commit -m "fix: eliminate ghosting and coordinate jump when hiding floating controls"
```

---

### Task 3: Windows GSMTC Now Playing Media Title Display

**Files:**
- Create: `mikan_pet/services/media_info.py`
- Modify: `mikan_pet/ui/pet_window.py`
- Create: `tests/test_media_info.py`
- Modify: `tests/test_pet_window.py`

**Interfaces:**
- Produces: `MediaTrackInfo(title: str, artist: str, is_playing: bool)`, `MediaInfoService` protocol and Windows backend.
- UI displays a styled bubble at the top of the pet window containing current track information.

- [ ] **Step 1: Write tests for `MediaInfoService`**

Test empty session, active song session, Unicode strings, and string formatting in `tests/test_media_info.py`:
```python
import unittest
from mikan_pet.services.media_info import MediaTrackInfo, format_display_title

class MediaInfoTests(unittest.TestCase):
    def test_format_display_title_combines_title_and_artist(self):
        self.assertEqual("Song Title - Artist", format_display_title(MediaTrackInfo("Song Title", "Artist", True)))

    def test_format_display_title_truncates_long_titles(self):
        long_title = "A" * 50
        formatted = format_display_title(MediaTrackInfo(long_title, "Artist", True), max_length=25)
        self.assertTrue(formatted.endswith("..."))
        self.assertLessEqual(len(formatted), 25)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests/test_media_info.py`
Expected: FAIL (No module named `mikan_pet.services.media_info`)

- [ ] **Step 3: Implement `mikan_pet/services/media_info.py`**

Implement `MediaTrackInfo`, `format_display_title`, and `WindowsMediaInfoBackend`:
Use a lightweight non-blocking Windows GSMTC query (via PowerShell background or Windows WinRT ctypes if available) with fallback to empty track.
Add song bubble UI in `PetWindow`:
Create canvas text & speech balloon with tag `"track_info"`.
Update track info on periodic tick (e.g., every 2-3 seconds) and show for 4 seconds on change or while `controls_visible` is True.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests/test_media_info.py tests/test_pet_window.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add mikan_pet/services/media_info.py mikan_pet/ui/pet_window.py tests/test_media_info.py tests/test_pet_window.py
rtk git commit -m "feat: add Windows GSMTC media title display bubble"
```

---

### Task 4: GitHub In-Place Auto-Update Service

**Files:**
- Create: `mikan_pet/services/updater.py`
- Modify: `mikan_pet/ui/pet_window.py`
- Create: `tests/test_updater.py`

**Interfaces:**
- Produces: `UpdaterService`, `ReleaseInfo`, `check_for_updates(repo: str, current_version: str)`, `apply_update(zip_path: Path, app_dir: Path)`
- Adds context menu item `"Periksa Pembaruan"` in `PetWindow`.

- [ ] **Step 1: Write tests for updater service**

In `tests/test_updater.py`:
- Test semver comparison (`is_newer_version("0.1.0", "0.2.0") -> True`, `is_newer_version("0.2.0", "0.2.0") -> False`).
- Test parsing GitHub Releases API JSON.
- Test handling network errors gracefully.

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests/test_updater.py`
Expected: FAIL

- [ ] **Step 3: Implement `mikan_pet/services/updater.py` and UI binding**

- `is_newer_version(current: str, candidate: str) -> bool`
- `fetch_latest_release(repo: str) -> ReleaseInfo | None`
- In `PetWindow._build_menu()`, add `"Periksa Pembaruan"` command.
- When clicked, asynchronously checks for updates. If up to date, displays a friendly message; if an update exists, offers to download and replace in-place.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest tests/test_updater.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add mikan_pet/services/updater.py mikan_pet/ui/pet_window.py tests/test_updater.py
rtk git commit -m "feat: add GitHub in-place auto-update service and menu"
```

---

### Task 5: GitHub Actions CI/CD Workflow & Release Verification

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `README.md`
- Test: Build pipeline via `scripts/build.ps1`

**Interfaces:**
- Produces: Automated workflow triggered on tag push `v*` producing release binaries.

- [ ] **Step 1: Create `.github/workflows/release.yml`**

Create automated workflow:
- Target: `windows-latest`
- Trigger: `push: tags: ['v*']`
- Steps: Checkout, setup Python 3.14, install Inno Setup (`choco install innosetup`), run tests, run `scripts/build.ps1`, publish artifacts (`MikanPet-Setup-x64.exe`, `MikanPet-portable-x64.zip`) to GitHub Releases via `softprops/action-gh-release`.

- [ ] **Step 2: Run local test suite and build verification**

Run: `rtk .worktrees/mikan-pet-implementation/.venv/Scripts/python -m unittest discover -s tests`
Run: `rtk powershell -File "scripts/build.ps1" -Python ".\.worktrees\mikan-pet-implementation\.venv\Scripts\python.exe"`
Expected: 100% tests pass, build succeeds, GUI smoke test exits code 0.

- [ ] **Step 3: Commit**

```bash
rtk git add .github/workflows/release.yml README.md
rtk git commit -m "ci: add GitHub Actions release workflow for tag-based automated builds"
```
