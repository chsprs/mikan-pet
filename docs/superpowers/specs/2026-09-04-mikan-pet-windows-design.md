# Mikan Pet for Windows — Design Specification

Date: 2026-09-04
Status: Approved in conversation

## 1. Purpose

Mikan Pet is a lightweight desktop companion for Windows. It displays an
animated, pixel-art cat above normal application windows and provides universal
previous, play/pause, and next media controls.

The first release must feel like a pet rather than a floating toolbar. It walks
left and right, pauses for idle and sleep animations, reacts to interaction,
can be dragged, and can be stopped or restarted by the user.

## 2. Supported Environment

- Windows 10 and Windows 11, 64-bit.
- Windows 11 on ARM may run the x64 package through Windows emulation; native
  ARM64 packaging is not part of the first release.
- The installed application does not require a separate Python installation.
- Multi-monitor desktops are supported through Windows work-area coordinates.

Windows 7, Windows 8, 32-bit Windows, macOS, and Linux are outside the scope of
this release.

## 3. Product Scope

### Included

- Transparent, borderless, always-on-top desktop pet window.
- Pixel-art animation states: walking, idle breathing, blinking, sleeping, and
  short interaction reactions.
- Automatic horizontal roaming with safe reversal at monitor edges.
- Drag-to-position behavior across monitors.
- Click the pet to show or hide floating media-control bubbles.
- Previous, play/pause, and next commands for the active Windows media session.
- Right-click menu for walking state, skins, always-on-top, position reset, and
  exit.
- Three selectable skins: Mikan, Byte, and Mochi.
- Persistent preferences and position.
- Single-instance protection.
- A Windows installer and a portable package.

### Not included

- Track title, artist, album artwork, progress, or media-application selection.
- Volume control.
- Autostart at Windows login.
- System-tray controls.
- Online accounts, telemetry, networking, or automatic updates.

## 4. Technical Architecture

The application uses Python, Tkinter, and pywin32. Tkinter provides a small GUI
surface with no web runtime. pywin32 supplies the Windows media-key, monitor,
and process primitives needed by the application. PyInstaller bundles the
runtime and dependencies for distribution.

The main units are:

1. **Application coordinator** — starts the singleton guard, loads settings,
   creates the window, connects services, and owns graceful shutdown.
2. **Pet state machine** — owns motion, pose, direction, timing, control
   visibility, and skin selection without depending on Tkinter.
3. **Sprite renderer** — converts small pixel maps and skin palettes into cached
   Tkinter `PhotoImage` frames and displays the active frame.
4. **Pet window** — owns transparency, input bindings, context menus, geometry,
   and the animation timer.
5. **Media-key service** — maps the three actions to Windows virtual-key events.
6. **Monitor service** — resolves work areas, clamps positions, and handles
   transfers between monitors.
7. **Settings store** — validates and atomically persists user preferences.
8. **Packaging scripts** — build the application folder, portable archive, and
   installer reproducibly.

The source layout will keep these responsibilities separate:

```text
mikan_pet/
  __main__.py
  app.py
  core/
    state.py
    sprites.py
  ui/
    pet_window.py
  services/
    media_keys.py
    monitors.py
    settings.py
    singleton.py
tests/
installer/
scripts/
```

## 5. Window and Rendering Model

Mikan Pet uses a compact window that surrounds only the pet and its expanded
controls. It does not create a transparent full-screen overlay, which would
intercept clicks intended for other applications.

The window is configured as borderless, transparent-color, and topmost. The
transparent key color is never used by a skin. Pixel frames are rendered at an
integer scale with no interpolation, so edges remain crisp at normal Windows
display scales.

The renderer builds frames from internal pixel maps and palette definitions.
This avoids external sprite-decoding dependencies and lets all skins share
animation geometry while applying distinct colors and markings. Frames are
created once, cached, and reused.

The animation timer uses Tkinter's event loop. It never updates widgets from a
background thread. Pet movement changes the small window's screen coordinates;
animation changes only the image inside the window.

## 6. Pet State and Behavior

The state machine tracks:

- motion mode: automatic, stopped, or dragging;
- pose: walk, idle, sleep, or react;
- direction: left or right;
- current monitor work area;
- whether controls are visible;
- selected skin;
- pose and behavior timers.

In automatic mode, the pet alternates between walking and short idle periods.
Longer idle periods may enter sleep. Reaching a work-area edge reverses the
direction without crossing the edge. In stopped mode, automatic movement and
walk transitions stop, while idle, blink, tail, and sleep animation remain
active.

Dragging temporarily suspends automatic movement. Releasing the pointer saves
the new position and adopts the monitor containing most of the pet window as
the new roaming boundary.

## 7. Interaction Rules

- A primary click without meaningful pointer movement toggles the floating
  control bubbles.
- Pointer movement of at least five logical pixels after press is treated as a
  drag, not a click.
- Media buttons do not toggle or dismiss the bubble row.
- Each media command triggers a short visual reaction on the pet.
- Right-clicking the pet opens a native context menu containing:
  - `Berhenti berjalan` or `Mulai berjalan`, according to current state;
  - a `Pilih skin` submenu with Mikan, Byte, and Mochi;
  - a checked `Always on top` toggle;
  - `Reset posisi`;
  - `Keluar`.
- Skin changes apply immediately without restarting.
- On first launch, the pet starts near the lower-right corner of the primary
  monitor work area without covering the taskbar.

## 8. Universal Media Control

The media service emits a key-down and key-up pair for these Windows virtual
keys:

- previous track: `VK_MEDIA_PREV_TRACK` (`0xB1`);
- play/pause: `VK_MEDIA_PLAY_PAUSE` (`0xB3`);
- next track: `VK_MEDIA_NEXT_TRACK` (`0xB0`).

Windows routes these commands to the active media session, which commonly
includes Spotify, browser-based players such as YouTube, and native media
players. When there is no eligible media session, Windows treats the command as
a no-op. The app remains responsive and reports no false error dialog.

## 9. Skins

All skins use the same dimensions, interaction hit area, and animation state
names so changing a skin cannot change behavior.

- **Mikan** — orange tabby, warm cream highlights, blue collar.
- **Byte** — dark indigo cat with mint and pink neon accents.
- **Mochi** — cream calico with orange and charcoal markings and a teal collar.

Each registry entry must provide every required animation frame. An incomplete
skin is rejected during development tests rather than failing at runtime.

## 10. Settings and Recovery

Settings are stored at `%APPDATA%\MikanPet\settings.json` with a schema version.
The stored values are:

- window position;
- last monitor identity when available;
- selected skin;
- automatic or stopped motion mode;
- control visibility;
- always-on-top preference.

Writes use a temporary file followed by an atomic replacement. Invalid,
truncated, or unsupported settings fall back to safe defaults. A saved position
that does not intersect any current monitor work area is reset to the primary
monitor's lower-right work area.

## 11. Single Instance and Shutdown

A named Windows mutex prevents two copies from running at once. Starting a
second copy exits without creating another pet.

Normal exit cancels scheduled Tkinter callbacks, saves settings, releases the
mutex, and destroys the window. Windows shutdown must not leave a corrupted
settings file because persistence is atomic.

## 12. Packaging and Installation

PyInstaller produces a windowed one-folder build. A one-folder build is chosen
over one-file extraction for faster launch and predictable asset access. The
folder is also archived as the portable package.

Inno Setup wraps the same folder into `MikanPet-Setup-x64.exe` with:

- Windows 10 as the minimum supported version;
- 64-bit compatible architecture;
- per-user installation under Local AppData, without administrator rights;
- a Start Menu shortcut;
- an optional Desktop shortcut;
- an uninstaller.

Build outputs are excluded from version control. The packaging script produces
both the installer and portable archive from a clean build.

## 13. Error Handling

- Corrupt settings: use defaults and continue launching.
- Missing monitor: move to a valid work area.
- Media session absent: safely send the command and remain silent.
- Duplicate process: exit the second process cleanly.
- Missing required skin frame during development: fail a registry validation
  test; packaged builds contain only validated skins.
- Unexpected GUI callback failure: restore the pet to an idle state where
  possible and keep shutdown available from the context menu.

## 14. Testing Strategy

Automated tests use the Python standard `unittest` framework and keep platform
calls behind replaceable service boundaries. Tests cover:

- state transitions and edge reversal;
- walk/stop/drag behavior;
- click-versus-drag threshold;
- required frames for all three skins;
- media-action to virtual-key mapping;
- settings validation, atomic persistence, and corrupt-file recovery;
- off-screen position recovery and monitor clamping;
- singleton behavior through a service-level test double.

Manual Windows verification covers:

- transparency and topmost behavior;
- crisp rendering at 100%, 150%, and 200% display scaling;
- dragging and roaming on one and multiple monitors;
- click, right-click menu, skin switching, and reaction animations;
- control of Spotify, YouTube in a browser, and one native player;
- relaunch persistence and duplicate launch protection;
- installer, optional Desktop shortcut, portable package, and uninstall.

## 15. Acceptance Criteria

The release is complete when:

1. Mikan Pet launches on Windows 10/11 x64 without a Python installation.
2. The pet stays above normal windows without blocking the rest of the desktop.
3. It walks left and right within the active monitor, can be dragged, and can be
   stopped and restarted.
4. Clicking the pet reliably toggles controls while dragging does not.
5. Previous, play/pause, and next control the active Windows media session.
6. Mikan, Byte, and Mochi can be switched at runtime and all animate correctly.
7. Position and preferences survive relaunch and recover safely after monitor
   layout changes or corrupt settings.
8. A second application instance does not create a second pet.
9. Both `MikanPet-Setup-x64.exe` and a portable archive are produced by the
   documented build command.
