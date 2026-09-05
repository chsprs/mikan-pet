"""Transparent animated Tk window and interaction loop for Mikan Pet."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

from mikan_pet.core.gesture import (
    BASE_DPI,
    GestureResult,
    PointerGesture,
    drag_offset_to_logical,
    position_from_pointer,
)
from mikan_pet.core.sprites import SKINS, frame_count
from mikan_pet.core.state import PetController
from mikan_pet.core.types import MotionMode, Point, Pose, SkinId
from mikan_pet.core.window_layout import (
    DpiMetrics,
    calculate_window_layout,
    metrics_for_dpi,
    safe_pet_work_area,
)
from mikan_pet.services.media_info import MediaInfoService, format_display_title, format_time_seconds
from mikan_pet.services.media_keys import MediaAction, MediaKeyService
from mikan_pet.services.monitors import MonitorService, default_position
from mikan_pet.services.settings import AppSettings
from mikan_pet.ui.dpi import DpiWatcher, Rect
from mikan_pet.ui.sprite_cache import SpriteCache


TRANSPARENT_COLOR = "#FF00FF"
CREAM = "#FFF2D8"
CREAM_PRESSED = "#E8D8B8"
DARK = "#5A3626"
BROWN = "#9B5A37"
MIKAN_ORANGE = "#E78145"
ORANGE_PRESSED = "#D06B30"
TICK_MS = 50
MAX_TICK_MS = 200


class AnimationClock:
    def __init__(self, frame_ms: int = 180) -> None:
        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        self.frame_ms = frame_ms
        self.last_pose: Pose | None = None
        self.elapsed_ms = 0

    def advance(self, pose: Pose, elapsed_ms: int, frame_count: int) -> int:
        if frame_count <= 0:
            raise ValueError("frame_count must be positive")
        if pose is not self.last_pose:
            self.last_pose = pose
            self.elapsed_ms = 0
            return 0
        period = self.frame_ms * frame_count
        self.elapsed_ms = (self.elapsed_ms + max(0, elapsed_ms)) % period
        return self.elapsed_ms // self.frame_ms


def configure_pet_root(root: object, transparent_color: str, always_on_top: bool) -> None:
    root.overrideredirect(True)
    root.configure(bg=transparent_color)
    root.wm_attributes("-transparentcolor", transparent_color)
    root.wm_attributes("-topmost", always_on_top)
    root.title("Mikan Pet")


def context_menu_labels(walking: bool) -> tuple[str, ...]:
    return (
        "Berhenti berjalan" if walking else "Mulai berjalan",
        "Pilih skin",
        "Always on top",
        "Reset posisi",
        "Periksa Pembaruan",
        "Keluar",
    )



class PetWindow:
    def __init__(
        self,
        root,
        controller: PetController,
        sprite_cache: SpriteCache,
        monitor_service: MonitorService,
        media_service: MediaKeyService,
        on_settings_changed: Callable[[AppSettings], None],
        dpi_watcher_factory=DpiWatcher,
        media_info_service: MediaInfoService | None = None,
    ) -> None:
        self.root = root
        self.controller = controller
        self.sprite_cache = sprite_cache
        self.monitor_service = monitor_service
        self.media_service = media_service
        self.media_info_service = media_info_service
        self.on_settings_changed = on_settings_changed
        self._closing = False
        self._error_reported = False
        self._after_id: str | None = None
        self.last_intersected_id: str | None = None
        self.logical_drag_offset = Point(0, 0)
        self._walking_before_drag = controller.state.motion is MotionMode.AUTOMATIC
        self.frame_index = 0
        self._image_ref: object | None = None
        self._last_track_title = ""
        self._track_visible_until_ns = 0
        self._button_base_coords: dict[MediaAction, tuple[int, int, int, int, str, str]] = {}

        configure_pet_root(root, TRANSPARENT_COLOR, controller.state.always_on_top)
        self.dpi_watcher = dpi_watcher_factory(root, self._on_dpi_changed)
        initial_dpi = self.dpi_watcher.install()
        self.metrics = metrics_for_dpi(initial_dpi)
        self.root.tk.call("tk", "scaling", initial_dpi / 72.0)
        self.sprite_cache.clear(scale=self.metrics.pixel_scale)
        self.gesture = PointerGesture(self.metrics.drag_threshold_px)
        self.animation_clock = AnimationClock()

        self.canvas = tk.Canvas(
            root,
            highlightthickness=0,
            bg=TRANSPARENT_COLOR,
        )
        self.canvas.pack()
        self.skin_var = tk.StringVar(master=root, value=controller.state.skin.value)
        self.topmost_var = tk.BooleanVar(master=root, value=controller.state.always_on_top)
        self._build_menu()
        self._build_canvas_items()
        self._bind_canvas_events()
        self._reconcile_position()
        self._apply_window_layout()
        self.root.report_callback_exception = self._report_callback_exception
        self._last_tick_ns = time.monotonic_ns()
        self._schedule_tick()

    def _scale(self, value: int) -> int:
        return (value * self.metrics.dpi + BASE_DPI // 2) // BASE_DPI

    def _tags(self, action: MediaAction) -> tuple[str, str]:
        return "controls", f"media_{action.value}"

    def _draw_control(
        self, x: int, action: MediaAction, glyph: str, fill: str, pressed_fill: str
    ) -> None:
        sx = self._scale(x)
        sy = self._scale(12)
        face_size = self._scale(44)
        offset = self._scale(4)
        self._button_base_coords[action] = (sx, sy, face_size, offset, fill, pressed_fill)
        self.canvas.create_rectangle(
            sx + offset,
            sy + offset,
            sx + face_size + offset,
            sy + face_size + offset,
            fill=BROWN,
            outline=DARK,
            width=max(1, self._scale(2)),
            tags=("controls", f"media_{action.value}", f"btn_shadow_{action.value}"),
        )
        self.canvas.create_rectangle(
            sx,
            sy,
            sx + face_size,
            sy + face_size,
            fill=fill,
            outline=DARK,
            width=max(1, self._scale(2)),
            tags=("controls", f"media_{action.value}", f"btn_face_{action.value}"),
        )
        self.canvas.create_text(
            sx + self._scale(22),
            sy + self._scale(22),
            text=glyph,
            fill=DARK,
            font="TkFixedFont",
            tags=("controls", f"media_{action.value}", f"btn_text_{action.value}"),
        )

    def _build_canvas_items(self) -> None:
        self.canvas.delete("all")
        self._button_base_coords.clear()
        self._draw_control(16, MediaAction.PREVIOUS, "|<", CREAM, CREAM_PRESSED)
        self._draw_control(76, MediaAction.PLAY_PAUSE, ">", MIKAN_ORANGE, ORANGE_PRESSED)
        self._draw_control(136, MediaAction.NEXT, ">|", CREAM, CREAM_PRESSED)
        connector_tags = ("controls", "connector")
        self.canvas.create_rectangle(
            self._scale(96),
            self._scale(64),
            self._scale(100),
            self._scale(68),
            fill=CREAM,
            outline=CREAM,
            width=max(1, self._scale(1)),
            tags=connector_tags,
        )
        self.canvas.create_rectangle(
            self._scale(100),
            self._scale(72),
            self._scale(104),
            self._scale(76),
            fill=CREAM,
            outline=CREAM,
            width=max(1, self._scale(1)),
            tags=connector_tags,
        )
        self._image_ref = self.sprite_cache.get(
            self.controller.state.skin,
            self.controller.state.pose,
            self.frame_index,
            self.controller.state.direction,
        )
        self.canvas.create_image(
            0,
            0,
            image=self._image_ref,
            anchor="nw",
            tags=("pet",),
        )
        self.canvas.create_rectangle(
            0,
            0,
            0,
            0,
            fill=CREAM,
            outline=DARK,
            width=max(1, self._scale(1)),
            tags=("track_bubble", "track_bubble_bg"),
            state="hidden",
        )
        self.canvas.create_text(
            0,
            0,
            text="",
            fill=DARK,
            font="TkSmallCaptionFont",
            tags=("track_bubble", "track_bubble_text"),
            state="hidden",
        )
        self.canvas.create_rectangle(
            0,
            0,
            0,
            0,
            fill="#D4C8B8",
            outline="",
            tags=("track_bubble", "track_bubble_bar_bg"),
            state="hidden",
        )
        self.canvas.create_rectangle(
            0,
            0,
            0,
            0,
            fill=MIKAN_ORANGE,
            outline="",
            tags=("track_bubble", "track_bubble_bar_fill"),
            state="hidden",
        )
        self.canvas.create_oval(
            0,
            0,
            0,
            0,
            fill=MIKAN_ORANGE,
            outline=DARK,
            width=max(1, self._scale(1)),
            tags=("track_bubble", "track_bubble_pin"),
            state="hidden",
        )
        self.canvas.create_text(
            0,
            0,
            text="",
            fill=DARK,
            font="TkSmallCaptionFont",
            tags=("track_bubble", "track_bubble_time"),
            state="hidden",
        )

    def _bind_canvas_events(self) -> None:
        self.canvas.tag_bind("pet", "<ButtonPress-1>", self._on_pet_press)
        self.canvas.tag_bind("pet", "<B1-Motion>", self._on_pet_motion)
        self.canvas.tag_bind("pet", "<ButtonRelease-1>", self._on_pet_release)
        self.canvas.tag_bind("pet", "<Button-3>", self._show_context_menu)
        for action in MediaAction:
            tag = f"media_{action.value}"
            self.canvas.tag_bind(
                tag,
                "<ButtonPress-1>",
                lambda _event, selected=action: self._on_button_press(selected),
            )
            self.canvas.tag_bind(
                tag,
                "<ButtonRelease-1>",
                lambda _event, selected=action: self._on_button_release(selected),
            )

    def _is_walking(self) -> bool:
        if self.controller.state.motion is MotionMode.DRAGGING:
            return self._walking_before_drag
        return self.controller.state.motion is MotionMode.AUTOMATIC

    def _build_menu(self) -> None:
        labels = context_menu_labels(self._is_walking())
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label=labels[0], command=self._toggle_walking)
        skin_menu = tk.Menu(self.menu, tearoff=False)
        for skin_id, definition in SKINS.items():
            skin_menu.add_radiobutton(
                label=definition.display_name,
                value=skin_id.value,
                variable=self.skin_var,
                command=lambda value=skin_id.value: self._select_skin(value),
            )
        self.menu.add_cascade(label=labels[1], menu=skin_menu)
        self.menu.add_checkbutton(
            label=labels[2],
            variable=self.topmost_var,
            command=self._toggle_topmost,
        )
        self.menu.add_command(label=labels[3], command=self._reset_position)
        self.menu.add_command(label=labels[4], command=self._check_for_updates)
        self.menu.add_separator()
        self.menu.add_command(label=labels[5], command=self.close)

    def _check_for_updates(self) -> None:
        import threading
        from pathlib import Path
        import sys
        from mikan_pet import __version__
        from mikan_pet.services.updater import (
            DEFAULT_GITHUB_REPO,
            download_and_extract_update,
            fetch_latest_release,
            is_newer_version,
            launch_in_place_updater,
        )

        def worker() -> None:
            release = fetch_latest_release(DEFAULT_GITHUB_REPO)
            if release is None:
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Mikan Pet",
                        "Tidak dapat memeriksa pembaruan.\nPeriksa koneksi internet Anda.",
                        parent=self.root,
                    ),
                )
                return

            if not is_newer_version(__version__, release.version):
                notes = release.release_notes.strip()
                summary = f"\n\nCatatan rilis:\n{notes[:300]}..." if notes else ""
                msg = (
                    f"Status: SESUAI DENGAN GITHUB\n\n"
                    f"• Versi terpasang: v{__version__}\n"
                    f"• Versi GitHub terbaru: v{release.version}\n"
                    f"• Hasil verifikasi: Bebas bug versi (versi terbaru){summary}\n\n"
                    f"Aplikasi Mikan Pet yang terpasang sudah 100% sinkron dengan rilis resmi di GitHub."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Mikan Pet - Verifikasi Versi GitHub",
                        msg,
                        parent=self.root,
                    ),
                )
                return

            def on_confirm_update() -> None:
                notes = release.release_notes.strip()
                summary = f"\n\nCatatan rilis:\n{notes[:300]}..." if notes else ""
                msg = (
                    f"Status: BELUM SESUAI DENGAN GITHUB\n\n"
                    f"• Versi terpasang: v{__version__}\n"
                    f"• Versi GitHub terbaru: v{release.version} (lebih baru)\n"
                    f"{summary}\n\n"
                    f"Apakah Anda ingin memperbarui sekarang tanpa perlu install ulang?"
                )
                should_update = messagebox.askyesno(
                    "Mikan Pet - Pembaruan Tersedia",
                    msg,
                    parent=self.root,
                )
                if not should_update:
                    return

                if not release.zip_url:
                    import webbrowser
                    webbrowser.open(release.html_url)
                    return

                def download_worker() -> None:
                    try:
                        import tempfile
                        staging_dir = Path(tempfile.gettempdir()) / f"mikan_update_{release.version}"
                        download_and_extract_update(release.zip_url, staging_dir)
                        app_dir = Path(sys.executable).resolve().parent
                        exe_path = app_dir / "MikanPet.exe"
                        if not exe_path.exists():
                            self.root.after(
                                0,
                                lambda: messagebox.showinfo(
                                    "Mikan Pet",
                                    f"Pembaruan v{release.version} berhasil diunduh ke:\n{staging_dir}\n\n(Mode development: silakan build atau salin manual)",
                                    parent=self.root,
                                ),
                            )
                            return
                        launch_in_place_updater(staging_dir, app_dir, "MikanPet.exe")
                        self.root.after(0, self.close)
                    except Exception as err:
                        self.root.after(
                            0,
                            lambda: messagebox.showerror(
                                "Mikan Pet - Gagal Memperbarui",
                                f"Gagal mengunduh pembaruan:\n{err}",
                                parent=self.root,
                            ),
                        )

                threading.Thread(target=download_worker, daemon=True).start()
                messagebox.showinfo(
                    "Mikan Pet - Mengunduh Pembaruan",
                    f"Pembaruan v{release.version} sedang diunduh di latar belakang.\n\nSetelah selesai, Mikan Pet akan otomatis dimulai ulang.",
                    parent=self.root,
                )

            self.root.after(0, on_confirm_update)

        threading.Thread(target=worker, daemon=True).start()


    def _show_context_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _on_pet_press(self, event) -> None:
        if self._closing:
            return
        pointer = Point(event.x_root, event.y_root)
        position = self.controller.state.position
        physical_offset = Point(pointer.x - position.x, pointer.y - position.y)
        self.logical_drag_offset = drag_offset_to_logical(physical_offset, self.metrics.dpi)
        self._walking_before_drag = self.controller.state.motion is MotionMode.AUTOMATIC
        self.gesture.press(pointer)
        target = self.monitor_service.current_for(position, self.metrics.pet_size)
        self.last_intersected_id = target.id

    def _on_pet_motion(self, event) -> None:
        if self._closing:
            return
        pointer = Point(event.x_root, event.y_root)
        if not self.gesture.move(pointer):
            return
        if self.controller.state.motion is not MotionMode.DRAGGING:
            self.controller.begin_drag()
        proposed = position_from_pointer(pointer, self.logical_drag_offset, self.metrics.dpi)
        self.controller.drag_to(proposed)
        target = self.monitor_service.drag_target(
            proposed,
            self.metrics.pet_size,
            self.last_intersected_id,
        )
        self.last_intersected_id = target.id
        self._apply_window_layout()

    def _on_pet_release(self, event) -> None:
        if self._closing:
            return
        pointer = Point(event.x_root, event.y_root)
        result = self.gesture.release(pointer)
        if result is None:
            return
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
            proposed = position_from_pointer(pointer, self.logical_drag_offset, self.metrics.dpi)
            self.controller.drag_to(proposed)
            target = self.monitor_service.drag_target(
                self.controller.state.position,
                self.metrics.pet_size,
                self.last_intersected_id,
            )
            self.last_intersected_id = target.id
        self.controller.place_within(
            safe_pet_work_area(
                target.work_area,
                self.controller.state.controls_visible,
                self.metrics,
            ),
            self.metrics.pet_size,
        )
        if result is GestureResult.DRAG:
            self.controller.end_drag()
            self._redraw_current_pose()
        self._apply_window_layout()
        self._settings_changed()

    def _animate_button_press(self, action: MediaAction) -> None:
        base = getattr(self, "_button_base_coords", {}).get(action)
        if not base:
            return
        sx, sy, face_size, offset, _, pressed_fill = base
        dx = max(1, offset // 2)
        dy = max(1, offset // 2)
        self.canvas.coords(
            f"btn_face_{action.value}",
            sx + dx,
            sy + dy,
            sx + face_size + dx,
            sy + face_size + dy,
        )
        self.canvas.coords(
            f"btn_text_{action.value}",
            sx + self._scale(22) + dx,
            sy + self._scale(22) + dy,
        )
        self.canvas.itemconfigure(f"btn_face_{action.value}", fill=pressed_fill)

    def _animate_button_release(self, action: MediaAction) -> None:
        base = getattr(self, "_button_base_coords", {}).get(action)
        if not base:
            return
        sx, sy, face_size, _, normal_fill, _ = base
        self.canvas.coords(
            f"btn_face_{action.value}",
            sx,
            sy,
            sx + face_size,
            sy + face_size,
        )
        self.canvas.coords(
            f"btn_text_{action.value}",
            sx + self._scale(22),
            sy + self._scale(22),
        )
        self.canvas.itemconfigure(f"btn_face_{action.value}", fill=normal_fill)

    def _on_button_press(self, action: MediaAction) -> None:
        self._animate_button_press(action)

    def _on_button_release(self, action: MediaAction) -> None:
        self._on_media(action)
        self.root.after(120, lambda: self._animate_button_release(action))

    def _on_media(self, action: MediaAction) -> None:
        self.media_service.send(action)
        self.controller.react()
        self._redraw_current_pose()

    def _select_skin(self, value: str) -> None:
        skin = SkinId(value)
        self.controller.set_skin(skin)
        self.skin_var.set(skin.value)
        self._redraw_image()
        self._settings_changed()

    def _toggle_topmost(self) -> None:
        enabled = bool(self.topmost_var.get())
        self.controller.set_always_on_top(enabled)
        self.root.wm_attributes("-topmost", enabled)
        self._settings_changed()

    def _reset_position(self) -> None:
        primary = self.monitor_service.primary()
        margin = self._scale(24)
        self.controller.drag_to(default_position(primary.work_area, self.metrics.pet_size, margin))
        self.last_intersected_id = primary.id
        self._reconcile_position()
        self._apply_window_layout()
        self._settings_changed()

    def _toggle_walking(self) -> None:
        self.controller.toggle_walking()
        self.menu.entryconfigure(0, label=context_menu_labels(self._is_walking())[0])
        self._redraw_current_pose()
        self._settings_changed()

    def _redraw_current_pose(self) -> None:
        pose = self.controller.state.pose
        self.frame_index = self.animation_clock.advance(pose, 0, frame_count(pose))
        self._redraw_image()

    def _redraw_image(self) -> None:
        state = self.controller.state
        self._image_ref = self.sprite_cache.get(
            state.skin,
            state.pose,
            self.frame_index,
            state.direction,
        )
        self.canvas.itemconfigure("pet", image=self._image_ref)

    def _apply_window_layout(self) -> None:
        state = self.controller.state
        layout = calculate_window_layout(state.position, state.controls_visible, self.metrics)
        size = layout.window_size
        origin = layout.root_origin
        self.canvas.itemconfigure(
            "controls",
            state="normal" if state.controls_visible else "hidden",
        )
        # Tk's bare '-N' means distance from the far screen edge. '+-N'
        # expresses a negative absolute desktop coordinate (left/above primary).
        self.root.geometry(f"{size.width}x{size.height}+{origin.x}+{origin.y}")
        self.canvas.configure(width=size.width, height=size.height)
        image_x = layout.pet_offset.x + self.metrics.pet_image_offset.x
        image_y = layout.pet_offset.y + self.metrics.pet_image_offset.y
        self.canvas.coords("pet", image_x, image_y)
        self._update_track_info()
        self.root.update_idletasks()

    def _update_track_info(self) -> None:
        service = getattr(self, "media_info_service", None)
        if service is None or not hasattr(self, "_last_track_title"):
            return
        service.poll_if_due()
        track = service.current_track
        now_ns = time.monotonic_ns()
        title_text = format_display_title(track, max_length=22)
        if title_text and title_text != self._last_track_title:
            self._last_track_title = title_text
            self._track_visible_until_ns = now_ns + 4_000_000_000

        should_show = bool(title_text) and (
            self.controller.state.controls_visible or now_ns < self._track_visible_until_ns
        )
        if not should_show:
            self.canvas.itemconfigure("track_bubble", state="hidden")
            return

        display_str = f"♪ {title_text}"
        self.canvas.itemconfigure("track_bubble_text", text=display_str, state="normal")
        if self.controller.state.controls_visible:
            bx = self._scale(100)
            by = self._scale(68)
        else:
            bx = self._scale(72)
            by = self._scale(18)

        pad_x = self._scale(5)
        pad_y = self._scale(2)

        has_timeline = getattr(track, "has_timeline", False) and track.duration_seconds > 0

        layout = calculate_window_layout(
            self.controller.state.position,
            self.controller.state.controls_visible,
            self.metrics,
        )
        max_w = layout.window_size.width

        if has_timeline:
            pos_sec = track.current_position_seconds
            dur_sec = track.duration_seconds
            pos_str = format_time_seconds(pos_sec)
            dur_str = format_time_seconds(dur_sec)
            time_str = f"{pos_str} / {dur_str}"
            progress = max(0.0, min(1.0, pos_sec / dur_sec)) if dur_sec > 0 else 0.0

            # Line 1: Title (centered at bx, by - scale(10))
            self.canvas.coords("track_bubble_text", bx, by - self._scale(10))
            bbox_title = self.canvas.bbox("track_bubble_text")
            title_w = (bbox_title[2] - bbox_title[0]) if bbox_title else self._scale(70)

            # Line 3: Time Text (centered at bx, by + scale(10))
            self.canvas.itemconfigure("track_bubble_time", text=time_str, state="normal")
            self.canvas.coords("track_bubble_time", bx, by + self._scale(10))
            bbox_time = self.canvas.bbox("track_bubble_time")
            time_w = (bbox_time[2] - bbox_time[0]) if bbox_time else self._scale(50)

            min_bubble_w = self._scale(110)
            bubble_w = max(title_w, time_w, min_bubble_w) + pad_x * 2
            bg_x1 = bx - bubble_w // 2
            bg_x2 = bx + bubble_w // 2
            bg_y1 = by - self._scale(18)
            bg_y2 = by + self._scale(18)

            # Line 2: Seekbar with Pin (at by)
            bar_margin = pad_x + self._scale(6)
            bar_x1 = bg_x1 + bar_margin
            bar_x2 = bg_x2 - bar_margin
            bar_y = by
            bar_h = max(1, self._scale(2))
            pin_x = bar_x1 + int((bar_x2 - bar_x1) * progress)
            pin_r = max(3, self._scale(3))

            shift_x = 0
            if bg_x1 < pad_x:
                shift_x = pad_x - bg_x1
            elif bg_x2 > max_w - pad_x:
                shift_x = (max_w - pad_x) - bg_x2

            if shift_x != 0:
                bg_x1 += shift_x
                bg_x2 += shift_x
                bar_x1 += shift_x
                bar_x2 += shift_x
                pin_x += shift_x
                self.canvas.coords("track_bubble_text", bx + shift_x, by - self._scale(10))
                self.canvas.coords("track_bubble_time", bx + shift_x, by + self._scale(10))

            self.canvas.coords("track_bubble_bg", bg_x1, bg_y1, bg_x2, bg_y2)
            self.canvas.coords("track_bubble_bar_bg", bar_x1, bar_y - bar_h, bar_x2, bar_y + bar_h)
            self.canvas.coords("track_bubble_bar_fill", bar_x1, bar_y - bar_h, pin_x, bar_y + bar_h)
            self.canvas.coords("track_bubble_pin", pin_x - pin_r, bar_y - pin_r, pin_x + pin_r, bar_y + pin_r)

            self.canvas.itemconfigure("track_bubble_bg", state="normal")
            self.canvas.itemconfigure("track_bubble_bar_bg", state="normal")
            self.canvas.itemconfigure("track_bubble_bar_fill", state="normal")
            self.canvas.itemconfigure("track_bubble_pin", state="normal")
        else:
            self.canvas.itemconfigure("track_bubble_bar_bg", state="hidden")
            self.canvas.itemconfigure("track_bubble_bar_fill", state="hidden")
            self.canvas.itemconfigure("track_bubble_pin", state="hidden")
            self.canvas.itemconfigure("track_bubble_time", state="hidden")

            self.canvas.coords("track_bubble_text", bx, by)
            bbox = self.canvas.bbox("track_bubble_text")
            if bbox:
                bg_x1 = bbox[0] - pad_x
                bg_y1 = bbox[1] - pad_y
                bg_x2 = bbox[2] + pad_x
                bg_y2 = bbox[3] + pad_y

                shift_x = 0
                if bg_x1 < pad_x:
                    shift_x = pad_x - bg_x1
                elif bg_x2 > max_w - pad_x:
                    shift_x = (max_w - pad_x) - bg_x2

                if shift_x != 0:
                    self.canvas.coords("track_bubble_text", bx + shift_x, by)
                    bg_x1 += shift_x
                    bg_x2 += shift_x

                self.canvas.coords(
                    "track_bubble_bg",
                    bg_x1,
                    bg_y1,
                    bg_x2,
                    bg_y2,
                )
                self.canvas.itemconfigure("track_bubble_bg", state="normal")

    def _current_tick_interval_ms(self) -> int:
        state = self.controller.state
        if state.motion is MotionMode.DRAGGING:
            return 16
        if state.motion is MotionMode.AUTOMATIC and state.pose is Pose.WALK:
            return TICK_MS
        if state.pose is Pose.REACT:
            return TICK_MS
        return 180

    def _schedule_tick(self) -> None:
        if not self._closing:
            interval = self._current_tick_interval_ms()
            self._after_id = self.root.after(interval, self._tick)

    def _reconcile_position(self) -> None:
        """Keep the complete window safe without changing motion or pose timers."""
        state = self.controller.state
        if state.motion is MotionMode.DRAGGING:
            return
        position = self.monitor_service.recover_position(state.position, self.metrics.pet_size)
        target = self.monitor_service.current_for(position, self.metrics.pet_size)
        self.controller.drag_to(position)
        self.controller.place_within(
            safe_pet_work_area(target.work_area, state.controls_visible, self.metrics),
            self.metrics.pet_size,
        )
        self.last_intersected_id = target.id

    def _tick(self) -> None:
        if self._closing:
            return
        now = time.monotonic_ns()
        elapsed_ms = min(MAX_TICK_MS, max(0, (now - self._last_tick_ns) // 1_000_000))
        self._last_tick_ns = now
        self._reconcile_position()
        state = self.controller.state
        active = self.monitor_service.current_for(state.position, self.metrics.pet_size)
        movement_area = safe_pet_work_area(
            active.work_area,
            state.controls_visible,
            self.metrics,
        )
        state = self.controller.tick(
            elapsed_ms,
            movement_area,
            self.metrics.pet_size,
            dpi_scale=self.metrics.dpi / BASE_DPI,
        )
        self.frame_index = self.animation_clock.advance(
            state.pose,
            elapsed_ms,
            frame_count(state.pose),
        )
        self._redraw_image()
        self._apply_window_layout()
        self._schedule_tick()

    def _on_dpi_changed(self, new_dpi: int, suggested_rect: Rect) -> None:
        if self._closing:
            return
        self.root.tk.call("tk", "scaling", new_dpi / 72.0)
        self.metrics = metrics_for_dpi(new_dpi)
        self.sprite_cache.clear(scale=self.metrics.pixel_scale)
        self.gesture.set_threshold(self.metrics.drag_threshold_px)
        self._build_canvas_items()
        state = self.controller.state
        if state.motion is MotionMode.DRAGGING:
            pointer = Point(self.root.winfo_pointerx(), self.root.winfo_pointery())
            proposed = position_from_pointer(pointer, self.logical_drag_offset, self.metrics.dpi)
            self.controller.drag_to(proposed)
            target = self.monitor_service.drag_target(
                proposed,
                self.metrics.pet_size,
                self.last_intersected_id,
            )
            self.last_intersected_id = target.id
        else:
            pet_offset = (
                self.metrics.expanded_pet_offset
                if state.controls_visible
                else Point(0, 0)
            )
            proposed = Point(
                suggested_rect[0] + pet_offset.x,
                suggested_rect[1] + pet_offset.y,
            )
            self.controller.drag_to(proposed)
            target = self.monitor_service.current_for(proposed, self.metrics.pet_size)
            self.controller.place_within(
                safe_pet_work_area(
                    target.work_area,
                    state.controls_visible,
                    self.metrics,
                ),
                self.metrics.pet_size,
            )
            self.last_intersected_id = target.id
        self._apply_window_layout()

    def snapshot_settings(self) -> AppSettings:
        self._reconcile_position()
        state = self.controller.state
        monitor = self.monitor_service.current_for(state.position, self.metrics.pet_size)
        return AppSettings(
            schema_version=1,
            position=state.position,
            monitor_id=monitor.id,
            skin=state.skin,
            walking=self._is_walking(),
            controls_visible=state.controls_visible,
            always_on_top=state.always_on_top,
        )

    def _settings_changed(self) -> None:
        self.on_settings_changed(self.snapshot_settings())

    def _report_callback_exception(self, _exc_type, _exc_value, _traceback) -> None:
        try:
            import os
            import traceback
            from pathlib import Path
            appdata = os.environ.get("APPDATA")
            if appdata:
                log_dir = Path(appdata) / "MikanPet" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "mikan_pet.log"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- Exception at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    traceback.print_exception(_exc_type, _exc_value, _traceback, file=f)
        except Exception:
            pass

        self.controller.stop_and_idle()
        self._walking_before_drag = False
        self.menu.entryconfigure(0, label=context_menu_labels(False)[0])
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        try:
            self._redraw_current_pose()
        except Exception:
            pass
        if not self._error_reported:
            self._error_reported = True
            messagebox.showerror(
                "Mikan Pet",
                "Animasi berhenti karena terjadi kesalahan. Gunakan menu Keluar untuk menutup.",
                parent=self.root,
            )

    def run(self) -> None:
        self.root.mainloop()

    def close_after(self, delay_ms: int) -> None:
        self.root.after(delay_ms, self.close)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        if self.media_info_service is not None:
            try:
                self.media_info_service.close()
            except Exception:
                pass
        try:
            self.dpi_watcher.close()
        except Exception:
            self._closing = False
            raise
        self.root.destroy()
