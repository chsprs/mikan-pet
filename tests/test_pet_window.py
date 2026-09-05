from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from mikan_pet.core.sprites import frame_count
from mikan_pet.core.state import PetController, PetState
from mikan_pet.core.types import Direction, MotionMode, Point, Pose, SkinId, WorkArea
from mikan_pet.services.media_info import MediaTrackInfo
from mikan_pet.services.media_keys import MediaAction
from mikan_pet.services.monitors import MonitorInfo, MonitorService
from mikan_pet.services.settings import AppSettings
from mikan_pet.ui.pet_window import AnimationClock, PetWindow, configure_pet_root, context_menu_labels


class PetWindowHelpersTests(unittest.TestCase):
    def test_configures_borderless_transparent_topmost_root(self) -> None:
        root = Mock()
        configure_pet_root(root, "#FF00FF", True)
        root.overrideredirect.assert_called_once_with(True)
        root.configure.assert_called_once_with(bg="#FF00FF")
        root.wm_attributes.assert_has_calls(
            [call("-transparentcolor", "#FF00FF"), call("-topmost", True)]
        )
        root.title.assert_called_once_with("Mikan Pet")

    def test_menu_label_reflects_walking_state(self) -> None:
        self.assertIn("Berhenti berjalan", context_menu_labels(True))
        self.assertIn("Mulai berjalan", context_menu_labels(False))
        self.assertIn("Pilih skin", context_menu_labels(True))
        self.assertIn("Always on top", context_menu_labels(True))
        self.assertIn("Reset posisi", context_menu_labels(True))
        self.assertIn("Periksa Pembaruan", context_menu_labels(True))
        self.assertIn("Keluar", context_menu_labels(True))

    def test_animation_clock_advances_and_resets_on_pose_change(self) -> None:
        clock = AnimationClock(frame_ms=180)
        self.assertEqual(0, clock.advance(Pose.WALK, 0, frame_count=2))
        self.assertEqual(0, clock.advance(Pose.WALK, 179, frame_count=2))
        self.assertEqual(1, clock.advance(Pose.WALK, 1, frame_count=2))
        self.assertEqual(0, clock.advance(Pose.IDLE, 180, frame_count=10))

    def test_animation_clock_rejects_empty_animation_and_ignores_negative_time(self) -> None:
        clock = AnimationClock(frame_ms=100)
        with self.assertRaises(ValueError):
            clock.advance(Pose.WALK, 10, frame_count=0)
        self.assertEqual(0, clock.advance(Pose.WALK, 0, frame_count=2))
        self.assertEqual(0, clock.advance(Pose.WALK, -500, frame_count=2))


class PetWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeCanvas.instances.clear()
        self.patchers = [
            patch("mikan_pet.ui.pet_window.tk.Canvas", FakeCanvas),
            patch("mikan_pet.ui.pet_window.tk.Menu", FakeMenu),
            patch("mikan_pet.ui.pet_window.tk.BooleanVar", FakeVariable),
            patch("mikan_pet.ui.pet_window.tk.StringVar", FakeVariable),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()

    def make_window(
        self,
        *,
        dpi: int = 96,
        position: Point = Point(200, 300),
        motion: MotionMode = MotionMode.AUTOMATIC,
        pose: Pose = Pose.WALK,
        controls_visible: bool = True,
        media_info_service=None,
    ) -> tuple[PetWindow, FakeRoot, PetController, FakeSpriteCache, FakeMediaService, list[AppSettings], FakeWatcher]:
        root = FakeRoot()
        controller = PetController(
            PetState(
                position=position,
                direction=Direction.RIGHT,
                motion=motion,
                pose=pose,
                skin=SkinId.MIKAN,
                controls_visible=controls_visible,
                always_on_top=True,
            )
        )
        sprite_cache = FakeSpriteCache()
        media_service = FakeMediaService()
        backend = SimpleNamespace(
            enumerate=lambda: [MonitorInfo("DISPLAY1", WorkArea(0, 0, 800, 600), True)]
        )
        monitor_service = MonitorService(backend)
        monitor_service.refresh()
        settings: list[AppSettings] = []
        watcher_factory = FakeWatcherFactory(dpi, root.lifecycle)
        window = PetWindow(
            root,
            controller,
            sprite_cache,
            monitor_service,
            media_service,
            settings.append,
            dpi_watcher_factory=watcher_factory,
            media_info_service=media_info_service,
        )
        return (
            window,
            root,
            controller,
            sprite_cache,
            media_service,
            settings,
            watcher_factory.instance,
        )

    def test_draws_scaled_controls_and_pet_with_semantic_tags(self) -> None:
        window, root, _, _, _, _, _ = self.make_window(dpi=144)
        canvas = window.canvas
        self.assertEqual({"highlightthickness": 0, "bg": "#FF00FF"}, canvas.options)
        self.assertEqual("300x312+158+180", root.geometries[-1])
        pet_image = canvas.items_with_tag("pet", kind="image")
        self.assertEqual((54, 120), pet_image[0][0])
        self.assertEqual(("pet",), pet_image[0][1]["tags"])
        for tag, expected_bounds in {
            "media_previous": (24, 18, 96, 90),
            "media_play_pause": (114, 18, 186, 90),
            "media_next": (204, 18, 276, 90),
        }.items():
            items = canvas.items_with_tag(tag)
            self.assertTrue(items)
            self.assertTrue(all("controls" in options["tags"] for _, options in items))
            self.assertEqual(expected_bounds, canvas.tag_bounds(tag))
        self.assertEqual(2, len(canvas.items_with_tag("connector")))
        self.assertTrue(all("controls" in item[1]["tags"] for item in canvas.items_with_tag("connector")))

    def test_collapsed_window_hides_control_items_and_keeps_pet_origin(self) -> None:
        window, root, _, _, _, _, _ = self.make_window(controls_visible=False)
        self.assertEqual("144x128+200+300", root.geometries[-1])
        controls = window.canvas.items_with_tag("controls")
        self.assertTrue(controls)
        self.assertTrue(all(options["state"] == "hidden" for _, options in controls))
        pet_image = window.canvas.items_with_tag("pet", "image")
        self.assertEqual((8, 0), pet_image[0][0])
        self.assertEqual(("pet",), pet_image[0][1]["tags"])

    def test_context_menu_has_walk_skin_topmost_reset_separator_and_exit(self) -> None:
        window, _, _, _, _, _, _ = self.make_window()
        self.assertEqual(
            ["command", "cascade", "checkbutton", "command", "command", "separator", "command"],
            [kind for kind, _ in window.menu.entries],
        )
        skin_menu = window.menu.entries[1][1]["menu"]
        self.assertEqual(3, len(skin_menu.entries))
        self.assertTrue(all(kind == "radiobutton" for kind, _ in skin_menu.entries))

    def test_pet_click_toggles_controls_without_entering_drag(self) -> None:
        window, _, controller, _, _, settings, _ = self.make_window(
            motion=MotionMode.STOPPED,
            pose=Pose.SLEEP,
            controls_visible=False,
        )
        window._on_pet_press(event_at(220, 320))
        window._on_pet_release(event_at(220, 320))
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual(Pose.SLEEP, controller.state.pose)
        self.assertTrue(controller.state.controls_visible)
        self.assertEqual(1, len(settings))

    def test_showing_controls_immediately_clamps_complete_expanded_window(self) -> None:
        window, root, controller, _, _, _, _ = self.make_window(
            position=Point(656, 472),
            controls_visible=False,
        )
        window._on_pet_press(event_at(666, 482))
        window._on_pet_release(event_at(666, 482))
        self.assertEqual(Point(628, 472), controller.state.position)
        self.assertEqual("200x208+600+392", root.geometries[-1])

    def test_threshold_crossing_starts_drag_and_motion_is_unbounded(self) -> None:
        window, root, controller, _, _, _, _ = self.make_window()
        window._on_pet_press(event_at(210, 310))
        window._on_pet_motion(event_at(214, 310))
        self.assertEqual(MotionMode.AUTOMATIC, controller.state.motion)
        window._on_pet_motion(event_at(-50, 310))
        self.assertEqual(MotionMode.DRAGGING, controller.state.motion)
        self.assertEqual(Point(-60, 300), controller.state.position)
        self.assertEqual("200x208+-88+220", root.geometries[-1])

    def test_drag_release_uses_release_pointer_then_clamps_and_restores_mode(self) -> None:
        window, _, controller, _, _, settings, _ = self.make_window(motion=MotionMode.STOPPED)
        window._on_pet_press(event_at(210, 310))
        window._on_pet_motion(event_at(-50, 310))
        self.assertEqual(Point(-60, 300), controller.state.position)
        window._on_pet_release(event_at(900, 700))
        self.assertEqual(Point(628, 472), controller.state.position)
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual(Pose.IDLE, controller.state.pose)
        self.assertEqual(controller.state.position, settings[-1].position)

    def test_media_tags_do_not_use_pet_bindings_and_media_reacts_immediately(self) -> None:
        window, _, controller, sprite_cache, media_service, _, _ = self.make_window()
        pet_callbacks = {callback for tag, _, callback in window.canvas.bindings if tag == "pet"}
        media_callbacks = {callback for tag, _, callback in window.canvas.bindings if tag.startswith("media_")}
        self.assertTrue(pet_callbacks.isdisjoint(media_callbacks))
        before = len(sprite_cache.get_calls)
        window._on_media(MediaAction.NEXT)
        self.assertEqual([MediaAction.NEXT], media_service.actions)
        self.assertEqual(Pose.REACT, controller.state.pose)
        self.assertGreater(len(sprite_cache.get_calls), before)

    def test_skin_topmost_and_reset_handlers_update_state_and_persist(self) -> None:
        window, root, controller, _, _, settings, _ = self.make_window(position=Point(300, 250))
        window._select_skin("byte")
        self.assertEqual(SkinId.BYTE, controller.state.skin)
        self.assertEqual("byte", window.skin_var.get())
        window.topmost_var.set(False)
        window._toggle_topmost()
        self.assertFalse(controller.state.always_on_top)
        self.assertIn(("-topmost", False), root.attributes)
        window._reset_position()
        self.assertEqual(Point(628, 448), controller.state.position)
        self.assertEqual(3, len(settings))

    def test_skin_change_keeps_current_animation_phase(self) -> None:
        window, _, _, sprite_cache, _, _, _ = self.make_window()
        window.animation_clock.advance(Pose.WALK, 0, frame_count(Pose.WALK))
        window.frame_index = window.animation_clock.advance(
            Pose.WALK, 180, frame_count(Pose.WALK)
        )
        window._select_skin("mochi")
        self.assertEqual(1, window.frame_index)
        self.assertEqual((SkinId.MOCHI, Pose.WALK, 1, Direction.RIGHT), sprite_cache.get_calls[-1])

    def test_walking_toggle_refreshes_visible_menu_label(self) -> None:
        window, _, controller, _, _, settings, _ = self.make_window()
        window._toggle_walking()
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual({"label": "Mulai berjalan"}, window.menu.entry_updates[-1][1])
        self.assertEqual(1, len(settings))

    def test_tick_caps_elapsed_time_updates_image_and_schedules_one_successor(self) -> None:
        with patch("mikan_pet.ui.pet_window.time.monotonic_ns", side_effect=[1_000_000_000, 2_000_000_000]):
            window, root, controller, sprite_cache, _, _, _ = self.make_window()
            with patch.object(controller, "tick", wraps=controller.tick) as tick:
                initial_schedules = len(root.after_calls)
                window._tick()
        tick.assert_called_once()
        self.assertEqual(200, tick.call_args.args[0])
        self.assertEqual(WorkArea(28, 80, 772, 600), tick.call_args.args[1])
        self.assertEqual(1.0, tick.call_args.kwargs["dpi_scale"])
        self.assertGreater(len(sprite_cache.get_calls), 1)
        self.assertEqual(initial_schedules + 1, len(root.after_calls))
        self.assertEqual(50, root.after_calls[-1][0])

    def test_constructs_exactly_one_animation_clock(self) -> None:
        with patch("mikan_pet.ui.pet_window.AnimationClock", wraps=AnimationClock) as clock_factory:
            window, _, _, _, _, _, _ = self.make_window()
        self.assertEqual(1, clock_factory.call_count)
        self.assertIsNotNone(window.animation_clock)

    def test_pose_transition_resets_animation_to_frame_zero(self) -> None:
        clock = AnimationClock(frame_ms=50)
        self.assertEqual(0, clock.advance(Pose.WALK, 0, frame_count(Pose.WALK)))
        self.assertEqual(1, clock.advance(Pose.WALK, 50, frame_count(Pose.WALK)))
        self.assertEqual(0, clock.advance(Pose.REACT, 50, frame_count(Pose.REACT)))

    def test_dpi_change_clears_cache_rebuilds_scaled_canvas_and_updates_threshold(self) -> None:
        window, root, controller, sprite_cache, _, settings, _ = self.make_window()
        window._on_dpi_changed(144, (100, 200, 400, 512))
        self.assertEqual(("tk", "scaling", 2.0), root.tk.calls[-1])
        self.assertEqual(6, sprite_cache.clear_calls[-1])
        self.assertEqual(144, window.metrics.dpi)
        self.assertEqual(Point(142, 320), controller.state.position)
        self.assertEqual("300x312+100+200", root.geometries[-1])
        self.assertEqual([], settings)
        window._on_pet_press(event_at(150, 330))
        window._on_pet_motion(event_at(157, 330))
        self.assertEqual(MotionMode.AUTOMATIC, controller.state.motion)
        window._on_pet_motion(event_at(158, 330))
        self.assertEqual(MotionMode.DRAGGING, controller.state.motion)

    def test_dpi_change_during_drag_recalculates_unbounded_anchor_from_pointer(self) -> None:
        window, root, controller, sprite_cache, _, _, _ = self.make_window()
        window._on_pet_press(event_at(240, 320))
        window._on_pet_motion(event_at(250, 320))
        self.assertEqual(MotionMode.DRAGGING, controller.state.motion)
        root.pointer = Point(-100, 650)
        window._on_dpi_changed(144, (0, 0, 300, 312))
        self.assertEqual(Point(-160, 620), controller.state.position)
        self.assertEqual(6, sprite_cache.clear_calls[-1])

    def test_snapshot_reports_current_monitor_and_controller_preferences(self) -> None:
        window, _, controller, _, _, _, _ = self.make_window()
        controller.set_skin(SkinId.MOCHI)
        snapshot = window.snapshot_settings()
        self.assertEqual(
            AppSettings(
                schema_version=1,
                position=Point(200, 300),
                monitor_id="DISPLAY1",
                skin=SkinId.MOCHI,
                walking=True,
                controls_visible=True,
                always_on_top=True,
            ),
            snapshot,
        )

    def test_snapshot_preserves_automatic_preference_during_temporary_drag(self) -> None:
        window, _, _, _, _, _, _ = self.make_window()
        window._on_pet_press(event_at(210, 310))
        window._on_pet_motion(event_at(220, 310))
        self.assertTrue(window.snapshot_settings().walking)

    def test_close_is_idempotent_and_restores_subclass_before_destroy(self) -> None:
        window, root, _, _, _, _, watcher = self.make_window()
        scheduled = window._after_id
        window.close()
        window.close()
        self.assertEqual([scheduled], root.cancelled)
        self.assertEqual(1, watcher.close_calls)
        self.assertEqual(1, root.destroy_calls)
        self.assertLess(root.lifecycle.index("watcher.close"), root.lifecycle.index("root.destroy"))

    def test_close_after_and_run_delegate_to_tk_loop(self) -> None:
        window, root, _, _, _, _, _ = self.make_window()
        window.close_after(250)
        self.assertEqual((250, window.close), root.after_calls[-1][:2])
        window.run()
        self.assertEqual(1, root.mainloop_calls)

    def test_close_can_retry_after_dpi_restore_failure_before_destroying_root(self) -> None:
        window, root, _, _, _, _, watcher = self.make_window()
        attempts = 0

        def fail_once() -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("restore failed")

        watcher.close = fail_once
        with self.assertRaisesRegex(OSError, "restore failed"):
            window.close()
        self.assertEqual(0, root.destroy_calls)

        window.close()
        self.assertEqual(2, attempts)
        self.assertEqual(1, root.destroy_calls)

    def test_callback_exception_stops_animation_and_shows_only_one_error(self) -> None:
        window, root, controller, sprite_cache, _, _, _ = self.make_window(pose=Pose.REACT)
        with patch("mikan_pet.ui.pet_window.messagebox.showerror") as showerror:
            root.report_callback_exception(RuntimeError, RuntimeError("boom"), None)
            root.report_callback_exception(RuntimeError, RuntimeError("again"), None)
        self.assertEqual(MotionMode.STOPPED, controller.state.motion)
        self.assertEqual(Pose.IDLE, controller.state.pose)
        self.assertEqual(Pose.IDLE, sprite_cache.get_calls[-1][1])
        self.assertEqual(1, showerror.call_count)
        self.assertIn("Mikan Pet", showerror.call_args.args[0])
        self.assertFalse(window._closing)

    def test_hide_controls_clears_canvas_state_and_updates_idletasks(self) -> None:
        window, root, controller, *_ = self.make_window(controls_visible=True)
        controller.set_controls_visible(False)
        window._apply_window_layout()
        controls = window.canvas.items_with_tag("controls")
        self.assertTrue(all(opt.get("state") == "hidden" for _, opt in controls))
        self.assertGreater(root.update_idletasks_calls, 0)

    def test_track_info_bubble_displayed_when_track_is_playing(self) -> None:
        media_info = Mock()
        media_info.current_track = MediaTrackInfo(
            title="Song A", artist="Artist B", is_playing=True
        )
        window, root, controller, *_ = self.make_window(media_info_service=media_info)
        window._tick()
        bubble_bg = window.canvas.items_with_tag("track_bubble", kind="rectangle")
        bubble_txt = window.canvas.items_with_tag("track_bubble", kind="text")
        self.assertTrue(len(bubble_bg) > 0)
        self.assertTrue(len(bubble_txt) > 0)
        self.assertEqual("normal", bubble_bg[0][1].get("state"))
        self.assertEqual("normal", bubble_txt[0][1].get("state"))
        self.assertIn("Song A", bubble_txt[0][1].get("text"))

    def test_check_for_updates_shows_info_when_already_latest(self) -> None:
        window, root, controller, *_ = self.make_window()
        fake_release = SimpleNamespace(
            version="0.1.0",
            tag_name="v0.1.0",
            zip_url=None,
            html_url="",
            release_notes="",
        )
        with patch("mikan_pet.services.updater.fetch_latest_release", return_value=fake_release), \
             patch("mikan_pet.ui.pet_window.messagebox.showinfo") as showinfo, \
             patch("threading.Thread", side_effect=lambda target, daemon: SimpleNamespace(start=target)):
            window._check_for_updates()
            for delay, cb, _ in list(root.after_calls):
                cb()
        showinfo.assert_called_once()
        self.assertIn("terbaru", showinfo.call_args.args[1])




def event_at(x: int, y: int) -> SimpleNamespace:
    return SimpleNamespace(x_root=x, y_root=y)


class FakeVariable:
    def __init__(self, master=None, value=None) -> None:
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class FakeTk:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def call(self, *args):
        self.calls.append(args)


class FakeRoot:
    def __init__(self) -> None:
        self.tk = FakeTk()
        self.attributes: list[tuple[str, object]] = []
        self.geometries: list[str] = []
        self.after_calls: list[tuple[int, object, str]] = []
        self.cancelled: list[str] = []
        self.pointer = Point(0, 0)
        self.lifecycle: list[str] = []
        self.destroy_calls = 0
        self.mainloop_calls = 0
        self.update_idletasks_calls = 0
        self.report_callback_exception = None

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def overrideredirect(self, enabled: bool) -> None:
        self.override = enabled

    def configure(self, **kwargs) -> None:
        self.config = kwargs

    def wm_attributes(self, name: str, value) -> None:
        self.attributes.append((name, value))

    def title(self, value: str) -> None:
        self.title_value = value

    def geometry(self, value: str) -> None:
        self.geometries.append(value)

    def after(self, delay: int, callback):
        identifier = f"after-{len(self.after_calls) + 1}"
        self.after_calls.append((delay, callback, identifier))
        return identifier

    def after_cancel(self, identifier: str) -> None:
        self.cancelled.append(identifier)
        self.lifecycle.append("root.after_cancel")

    def winfo_pointerx(self) -> int:
        return self.pointer.x

    def winfo_pointery(self) -> int:
        return self.pointer.y

    def destroy(self) -> None:
        self.destroy_calls += 1
        self.lifecycle.append("root.destroy")

    def mainloop(self) -> None:
        self.mainloop_calls += 1


class FakeCanvas:
    instances: list["FakeCanvas"] = []

    def __init__(self, master, **options) -> None:
        self.master = master
        self.options = options
        self.items: list[tuple[str, tuple[int, ...], dict]] = []
        self.bindings: list[tuple[str, str, object]] = []
        self.config_updates: list[dict] = []
        FakeCanvas.instances.append(self)

    def pack(self) -> None:
        self.packed = True

    def configure(self, **kwargs) -> None:
        self.config_updates.append(kwargs)

    def delete(self, target) -> None:
        if target == "all":
            self.items.clear()

    def create_rectangle(self, *coords: int, **options) -> int:
        self.items.append(("rectangle", coords, options))
        return len(self.items)

    def create_text(self, *coords: int, **options) -> int:
        self.items.append(("text", coords, options))
        return len(self.items)

    def create_image(self, *coords: int, **options) -> int:
        self.items.append(("image", coords, options))
        return len(self.items)

    def tag_bind(self, tag: str, event: str, callback) -> None:
        self.bindings.append((tag, event, callback))

    def itemconfigure(self, tag: str, **options) -> None:
        for index, (kind, coords, existing) in enumerate(self.items):
            if tag in existing.get("tags", ()):
                self.items[index] = (kind, coords, {**existing, **options})

    def coords(self, tag: str, *coords: int) -> None:
        for index, (kind, _, existing) in enumerate(self.items):
            if tag in existing.get("tags", ()):
                self.items[index] = (kind, coords, existing)

    def items_with_tag(self, tag: str, kind: str | None = None):
        return [
            (coords, options)
            for item_kind, coords, options in self.items
            if tag in options.get("tags", ()) and (kind is None or item_kind == kind)
        ]

    def tag_bounds(self, tag: str) -> tuple[int, int, int, int]:
        coords = [coords for coords, _ in self.items_with_tag(tag) if len(coords) == 4]
        return (
            min(item[0] for item in coords),
            min(item[1] for item in coords),
            max(item[2] for item in coords),
            max(item[3] for item in coords),
        )

    def bbox(self, tag: str) -> tuple[int, int, int, int] | None:
        coords = [coords for coords, _ in self.items_with_tag(tag) if len(coords) == 4]
        if coords:
            return (
                min(item[0] for item in coords),
                min(item[1] for item in coords),
                max(item[2] for item in coords),
                max(item[3] for item in coords),
            )
        text_items = [coords for coords, _ in self.items_with_tag(tag, kind="text") if len(coords) == 2]
        if text_items:
            x, y = text_items[0]
            return (x - 20, y - 8, x + 20, y + 8)
        return None


class FakeMenu:
    def __init__(self, master, tearoff=False) -> None:
        self.master = master
        self.tearoff = tearoff
        self.entries: list[tuple[str, dict]] = []
        self.entry_updates: list[tuple[object, dict]] = []

    def add_command(self, **kwargs) -> None:
        self.entries.append(("command", kwargs))

    def add_cascade(self, **kwargs) -> None:
        self.entries.append(("cascade", kwargs))

    def add_radiobutton(self, **kwargs) -> None:
        self.entries.append(("radiobutton", kwargs))

    def add_checkbutton(self, **kwargs) -> None:
        self.entries.append(("checkbutton", kwargs))

    def add_separator(self) -> None:
        self.entries.append(("separator", {}))

    def entryconfigure(self, index, **kwargs) -> None:
        self.entry_updates.append((index, kwargs))

    def tk_popup(self, x: int, y: int) -> None:
        self.popup = (x, y)

    def grab_release(self) -> None:
        self.released = True


class FakeSpriteCache:
    def __init__(self) -> None:
        self.scale = 4
        self.get_calls: list[tuple] = []
        self.clear_calls: list[int | None] = []

    def get(self, *key):
        self.get_calls.append(key)
        return ("image", *key)

    def clear(self, scale=None) -> None:
        self.scale = scale if scale is not None else self.scale
        self.clear_calls.append(scale)


class FakeMediaService:
    def __init__(self) -> None:
        self.actions: list[MediaAction] = []

    def send(self, action: MediaAction) -> None:
        self.actions.append(action)


class FakeWatcherFactory:
    def __init__(self, dpi: int, lifecycle: list[str]) -> None:
        self.dpi = dpi
        self.lifecycle = lifecycle
        self.instance = None

    def __call__(self, root, callback):
        self.instance = FakeWatcher(self.dpi, callback, self.lifecycle)
        return self.instance


class FakeWatcher:
    def __init__(self, dpi: int, callback, lifecycle: list[str]) -> None:
        self.dpi = dpi
        self.callback = callback
        self.lifecycle = lifecycle
        self.close_calls = 0

    def install(self) -> int:
        return self.dpi

    def close(self) -> None:
        self.close_calls += 1
        self.lifecycle.append("watcher.close")


if __name__ == "__main__":
    unittest.main()
