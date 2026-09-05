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
from mikan_pet.services.media_info import MediaInfoService, format_display_title
from mikan_pet.services.media_keys import MediaAction, MediaKeyService
from mikan_pet.services.monitors import MonitorService, default_position
from mikan_pet.services.settings import AppSettings
from mikan_pet.ui.dpi import DpiWatcher, Rect
from mikan_pet.ui.sprite_cache import SpriteCache


TRANSPARENT_COLOR = "#FF00FF"
CREAM = "#FFF2D8"
DARK = "#5A3626"
BROWN = "#9B5A37"
MIKAN_ORANGE = "#E78145"
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

    def _draw_control(self, x: int, action: MediaAction, glyph: str, fill: str) -> None:
        sx = self._scale(x)
        sy = self._scale(12)
        face_size = self._scale(44)
        offset = self._scale(4)
        tags = self._tags(action)
        self.canvas.create_rectangle(
            sx + offset,
            sy + offset,
            sx + face_size + offset,
            sy + face_size + offset,
            fill=BROWN,
            outline=DARK,
            width=max(1, self._scale(2)),
            tags=tags,
        )
        self.canvas.create_rectangle(
            sx,
            sy,
            sx + face_size,
            sy + face_size,
            fill=fill,
            outline=DARK,
            width=max(1, self._scale(2)),
            tags=tags,
        )
        self.canvas.create_text(
            sx + self._scale(22),
            sy + self._scale(22),
            text=glyph,
            fill=DARK,
            font="TkFixedFont",
            tags=tags,
        )

    def _build_canvas_items(self) -> None:
        self.canvas.delete("all")
        self._draw_control(16, MediaAction.PREVIOUS, "|<", CREAM)
        self._draw_control(76, MediaAction.PLAY_PAUSE, ">", MIKAN_ORANGE)
        self._draw_control(136, MediaAction.NEXT, ">|", CREAM)
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

    def _bind_canvas_events(self) -> None:
        self.canvas.tag_bind("pet", "<ButtonPress-1>", self._on_pet_press)
        self.canvas.tag_bind("pet", "<B1-Motion>", self._on_pet_motion)
        self.canvas.tag_bind("pet", "<ButtonRelease-1>", self._on_pet_release)
        self.canvas.tag_bind("pet", "<Button-3>", self._show_context_menu)
        for action in MediaAction:
            tag = f"media_{action.value}"
            self.canvas.tag_bind(
                tag,
                "<ButtonRelease-1>",
                lambda _event, selected=action: self._on_media(selected),
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
        self.menu.add_separator()
        self.menu.add_command(label=labels[4], command=self.close)

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
        self.canvas.coords("track_bubble_text", bx, by)
        bbox = self.canvas.bbox("track_bubble_text")
        if bbox:
            pad_x = self._scale(4)
            pad_y = self._scale(2)
            self.canvas.coords(
                "track_bubble_bg",
                bbox[0] - pad_x,
                bbox[1] - pad_y,
                bbox[2] + pad_x,
                bbox[3] + pad_y,
            )
            self.canvas.itemconfigure("track_bubble_bg", state="normal")

    def _schedule_tick(self) -> None:
        if not self._closing:
            self._after_id = self.root.after(TICK_MS, self._tick)

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
        try:
            self.dpi_watcher.close()
        except Exception:
            self._closing = False
            raise
        self.root.destroy()
