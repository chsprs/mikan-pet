# Mikan Pet Enhancements — Design Specification

Date: 2026-09-05
Status: Approved

## 1. Purpose & Scope

This specification defines four key improvements to Mikan Pet:
1. **Sleep Animation ("Zzzz Zzzz")**: Procedural pixel-art sleep indicators rising above the cat when in `Pose.SLEEP`.
2. **Floating Controls Hide Bug Fix**: Elimination of visual flicker, coordinate jumping, and transparent buffer ghosting when collapsing floating media controls.
3. **Now Playing Track Title Bubble**: Reading active media metadata from Windows Global System Media Transport Controls (GSMTC) and presenting track title and artist in a pixel-style speech bubble above the pet.
4. **GitHub In-Place Auto-Update & CI/CD**: Self-update mechanism via GitHub Releases that updates portable binary files in-place without running the installer, plus a GitHub Actions workflow that automatically tests, builds, and publishes release assets upon pushing version tags.

---

## 2. Technical Design

### 2.1 Sleep Animation ("Zzzz Zzzz")

- **Location**: `mikan_pet/core/sprites.py`, `mikan_pet/core/state.py`
- **Mechanism**:
  - `_SLEEP` frame templates expanded into a 4-frame breathing cycle:
    - Frame 0: Cat asleep, breathing at rest (no letters).
    - Frame 1: Small pixel 'z' floats near the head (using `ColorRole.LIGHT`).
    - Frame 2: The small 'z' drifts higher, followed by a larger 'Z' below it.
    - Frame 3: Larger 'Z' and 'zz' drift up forming "Zzzz", slowly fading.
  - Pixel coordinates remain strictly within the standard frame bounds (`FRAME_WIDTH = 36`, `FRAME_HEIGHT = 32`).
  - Automatically scales with DPI via `SpriteCache` and adheres to each skin palette.

### 2.2 Floating Controls Hide Bug Fix

- **Location**: `mikan_pet/ui/pet_window.py`
- **Root Cause**:
  - `_apply_window_layout()` changed canvas size and sprite coords before calling `root.geometry()`, causing a temporary 1-frame visual offset/snap.
  - Windows transparent color window (`-transparentcolor`) does not automatically trigger an immediate desktop redraw when the window bounds shrink, leaving ghost remnants of controls.
- **Solution**:
  1. Hide the `"controls"` canvas tag items immediately (`state="hidden"`).
  2. Execute `root.geometry()` to shrink the window boundary first.
  3. Reposition the canvas sprite coordinates to match the collapsed origin.
  4. Invoke `root.update_idletasks()` immediately to force Windows desktop manager to clear the transparent bounding region cleanly without delay.

### 2.3 Now Playing Track Title Display

- **Location**: `mikan_pet/services/media_info.py`, `mikan_pet/ui/pet_window.py`
- **Data Source**:
  - Windows Runtime `Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager` (GSMTC).
  - Queried non-blockingly (via lightweight thread or throttled async/PowerShell query with zero UI hangs).
  - Returns `TrackInfo(title: str, artist: str, is_playing: bool)`.
- **UI Presentation**:
  - Speech bubble rendered on the Canvas above the pet:
    - Cream background (`#FFF8F0`) with dark border (`#2B1E16`).
    - Displays `"Title - Artist"` truncated to fit smoothly without blocking the screen.
    - Shown automatically for 4 seconds when track changes, and persistently displayed whenever floating media controls are toggled open.
    - Cleanly fades/hides when controls close or track notification expires.

### 2.4 GitHub In-Place Update & CI/CD Workflow

- **Location**:
  - `mikan_pet/services/updater.py`: GitHub Releases API query, download, and detached extraction.
  - `mikan_pet/ui/pet_window.py`: Context menu entry `"Periksa Pembaruan"` (Check for Updates).
  - `.github/workflows/release.yml`: GitHub Actions automated pipeline.
- **Update Flow**:
  1. User selects "Periksa Pembaruan" or background check runs.
  2. Service queries `https://api.github.com/repos/{owner}/{repo}/releases/latest`.
  3. If tag version > local version:
     - Prompts user or downloads `MikanPet-portable-x64.zip`.
     - Spawns a detached replacement helper script (`scripts/apply_update.cmd`).
     - Closes current process, extracts zip over application directory, and launches new `MikanPet.exe`.
  4. If already up to date: Displays brief notification balloon "Mikan Pet sudah versi terbaru (vX.Y.Z)".
- **CI/CD Workflow (`.github/workflows/release.yml`)**:
  - Triggers on push of tags `v*`.
  - Runs on `windows-latest`.
  - Installs Python 3.14 + Inno Setup.
  - Runs tests via `unittest`.
  - Executes `scripts/build.ps1` to produce `MikanPet-Setup-x64.exe` and `MikanPet-portable-x64.zip`.
  - Uploads both artifacts to the GitHub Release automatically.

---

## 3. Testing Strategy

1. **Sprites & Animation**: Unit tests in `tests/test_sprites.py` verifying all 4 sleep frames validate against `validate_registry()` with valid dimensions.
2. **Layout & Hide Fix**: Unit tests in `tests/test_pet_window.py` verifying correct hide order, absence of stale items, and bounds containment.
3. **Media Info Service**: Mocked unit tests in `tests/test_media_info.py` verifying parser handling of empty, playing, paused, and Unicode song titles.
4. **Updater Service**: Mocked unit tests in `tests/test_updater.py` testing semver comparisons, release asset parsing, and failure gracefully handled when offline.
5. **GUI Smoke & Packaging**: Run `verify_gui_smoke.py` and `scripts/build.ps1` to confirm complete build artifact generation.
