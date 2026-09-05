"""Behavioral regressions for final release review findings."""

import sys
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mikan_pet.app import _state_from_settings
from mikan_pet.core.state import PetController
from mikan_pet.core.types import MotionMode, Point, Pose, WorkArea
from mikan_pet.core.window_layout import calculate_window_layout, metrics_for_dpi
from mikan_pet.services.monitors import MonitorInfo, MonitorService
from mikan_pet.services.settings import AppSettings
from mikan_pet.ui.dpi import Win32DpiBackend
from mikan_pet.ui.pet_window import PetWindow
from tests import test_pet_window as window_fixtures
from tests.test_pet_window import event_at


class FinalPlacementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = window_fixtures.PetWindowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def assert_contained(self, window, area):
        layout = calculate_window_layout(window.controller.state.position,
                                         window.controller.state.controls_visible, window.metrics)
        self.assertGreaterEqual(layout.root_origin.x, area.left)
        self.assertGreaterEqual(layout.root_origin.y, area.top)
        self.assertLessEqual(layout.root_origin.x + layout.window_size.width, area.right)
        self.assertLessEqual(layout.root_origin.y + layout.window_size.height, area.bottom)

    def test_stopped_initial_expanded_window_is_safe_at_every_edge_and_final_dpi(self):
        for dpi in (96, 144, 192):
            for position in (Point(0, 0), Point(656, 0), Point(0, 472), Point(656, 472)):
                with self.subTest(dpi=dpi, position=position):
                    window, _, controller, *_ = self.fixture.make_window(
                        dpi=dpi, position=position, motion=MotionMode.STOPPED, pose=Pose.SLEEP)
                    self.assert_contained(window, WorkArea(0, 0, 800, 600))
                    self.assertEqual(Pose.SLEEP, controller.state.pose)

    def test_stopped_default_recovered_and_reset_positions_keep_controls_visible(self):
        for dpi in (96, 144, 192):
            for saved in (None, Point(9000, 9000)):
                with self.subTest(dpi=dpi, saved=saved):
                    window, _, controller, *_ = self.fixture.make_window(dpi=dpi, motion=MotionMode.STOPPED)
                    initial = _state_from_settings(AppSettings(position=saved, walking=False),
                                                   window.monitor_service, metrics_for_dpi(dpi))
                    window2, _, controller2, *_ = self.fixture.make_window(
                        dpi=dpi, position=initial.position, motion=MotionMode.STOPPED)
                    self.assert_contained(window2, WorkArea(0, 0, 800, 600))
                    window._reset_position()
                    self.assert_contained(window, WorkArea(0, 0, 800, 600))
                    self.assertEqual(MotionMode.STOPPED, controller.state.motion)

    def test_runtime_resize_reconciles_stopped_and_walking_without_restarting_pose(self):
        for motion, pose in ((MotionMode.STOPPED, Pose.SLEEP), (MotionMode.AUTOMATIC, Pose.WALK)):
            with self.subTest(motion=motion):
                with patch('time.monotonic', return_value=0) as clock:
                    window, _, controller, *_ = self.fixture.make_window(position=Point(628, 472), motion=motion, pose=pose)
                    window.monitor_service._backend.enumerate = lambda: [MonitorInfo('DISPLAY1', WorkArea(0, 0, 640, 480), True)]
                    clock.return_value = 1.1
                    window._last_tick_ns = 0
                    with patch('mikan_pet.ui.pet_window.time.monotonic_ns', return_value=50_000_000):
                        window._tick()
                    self.assert_contained(window, WorkArea(0, 0, 640, 480))
                    self.assertEqual(motion, controller.state.motion)
                    self.assertEqual(pose, controller.state.pose)
                    self.assertEqual(50, controller.phase_elapsed_ms)

    def test_monitor_removal_recovers_to_primary_and_unchanged_ticks_do_not_jump(self):
        with patch('time.monotonic', return_value=0) as clock:
            window, _, controller, *_ = self.fixture.make_window(motion=MotionMode.STOPPED)
            controller.drag_to(Point(-1200, 300))
            clock.return_value = 1.1
            window._tick()
            self.assert_contained(window, WorkArea(0, 0, 800, 600))
            position = controller.state.position
            for _ in range(10):
                window._tick()
            self.assertEqual(position, controller.state.position)

    def test_runtime_refresh_preserves_unbounded_drag_then_clamps_on_release(self):
        with patch('time.monotonic', return_value=0) as clock:
            window, _, controller, *_ = self.fixture.make_window(motion=MotionMode.STOPPED)
            window._on_pet_press(event_at(210, 310))
            window._on_pet_motion(event_at(-50, 310))
            window.monitor_service._backend.enumerate = lambda: [MonitorInfo('DISPLAY1', WorkArea(0, 0, 640, 480), True)]
            clock.return_value = 1.1
            window._tick()
            self.assertEqual(Point(-60, 300), controller.state.position)
            window._on_pet_release(event_at(900, 700))
            self.assert_contained(window, WorkArea(0, 0, 640, 480))

    def test_oversized_expanded_window_keeps_one_top_left_anchor_during_walk(self):
        window, _, controller, *_ = self.fixture.make_window()
        window.monitor_service._backend.enumerate = lambda: [MonitorInfo('tiny', WorkArea(0, 0, 100, 90), True)]
        window.monitor_service.refresh()
        window._reset_position()
        self.assertEqual(Point(28, 80), controller.state.position)
        for _ in range(4):
            window._last_tick_ns = 0
            with patch('mikan_pet.ui.pet_window.time.monotonic_ns', return_value=50_000_000):
                window._tick()
            self.assertEqual(Point(28, 80), controller.state.position)


class MonitorRefreshTests(unittest.TestCase):
    def test_runtime_queries_refresh_at_most_once_per_second_and_retain_cache_on_failure(self):
        old = MonitorInfo('old', WorkArea(0, 0, 800, 600), True)
        new = MonitorInfo('new', WorkArea(0, 0, 640, 480), True)
        backend = Mock()
        backend.enumerate.side_effect = [[old], [], OSError('display changing'), [new]]
        with patch('time.monotonic', return_value=0) as clock:
            service = MonitorService(backend)
            service.refresh()
            for now, expected in ((0.5, old), (1.0, old), (1.5, old), (2.0, old), (2.5, old), (3.0, new)):
                clock.return_value = now
                for _ in range(5):
                    self.assertEqual(expected, service.current_for(Point(300, 300), metrics_for_dpi(96).pet_size))
                    self.assertEqual(expected, service.primary())
            self.assertEqual(4, backend.enumerate.call_count)

    def test_explicit_empty_refresh_does_not_erase_last_known_monitor(self):
        old = MonitorInfo('old', WorkArea(0, 0, 800, 600), True)
        backend = Mock()
        backend.enumerate.side_effect = [[old], []]
        service = MonitorService(backend)
        service.refresh()
        with self.assertRaises(RuntimeError):
            service.refresh()
        self.assertEqual(old, service.primary())


class ExactWndProcTests(unittest.TestCase):
    def test_bool_never_enters_raw_pointer_restore_path(self):
        gui = Mock()
        gui.SetWindowLong.return_value = True
        native = Mock()
        backend = Win32DpiBackend(gui, SimpleNamespace(GWL_WNDPROC=-4), native)
        backend.install_subclass(123, Mock())
        backend.restore_subclass()
        native.SetWindowLongPtrW.assert_not_called()
        self.assertIs(True, gui.SetWindowLong.call_args.args[2])


@unittest.skipUnless(sys.platform == 'win32', 'Actual Windows Tk geometry interpretation')
class ActualTkGeometryTests(unittest.TestCase):
    def test_layout_places_negative_absolute_origins_on_left_and_above_desktop(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.overrideredirect(True)
        root.withdraw()
        canvas = tk.Canvas(root)
        canvas.pack()
        # Exercise production layout with an actual Tcl/Tk interpreter. No HWND
        # monitor clamp: these intentionally off-primary coordinates prove parsing.
        window = PetWindow.__new__(PetWindow)
        window.root, window.canvas = root, canvas
        window.metrics = metrics_for_dpi(96)
        window.controller = PetController(_state_from_settings(
            AppSettings(controls_visible=False),
            SimpleNamespace(primary=lambda: MonitorInfo('p', WorkArea(0, 0, 1920, 1080), True)),
            window.metrics))
        for origin in (Point(-1280, 0), Point(0, -100), Point(-1280, -100)):
            with self.subTest(origin=origin):
                window.controller.drag_to(origin)
                window._apply_window_layout()
                root.deiconify()
                root.update()
                self.assertEqual((origin.x, origin.y), (root.winfo_x(), root.winfo_y()))
