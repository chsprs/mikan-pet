import unittest
from unittest.mock import Mock
from unittest.mock import call

from mikan_pet.core.types import Point, Size, WorkArea
from mikan_pet.services.monitors import (
    MonitorInfo,
    Win32MonitorBackend,
    WindowsDpiAwarenessBackend,
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

    def test_clamp_anchors_pet_at_work_area_origin_when_pet_is_larger_than_area(self) -> None:
        self.assertEqual(
            Point(0, 0),
            clamp_position(Point(50, 50), Size(120, 100), WorkArea(0, 0, 100, 80)),
        )

    def test_default_position_is_lower_right_with_margin(self) -> None:
        self.assertEqual(Point(1720, 856), default_position(MONITOR_1.work_area, Size(176, 160), 24))

    def test_dpi_awareness_falls_back_to_legacy_per_monitor(self) -> None:
        backend = Mock()
        backend.is_per_monitor.side_effect = [False, False, True]
        backend.set_per_monitor_v2.return_value = False
        backend.set_per_monitor_legacy.return_value = True
        result = enable_per_monitor_dpi_awareness(backend)
        self.assertTrue(result)
        backend.set_per_monitor_v2.assert_called_once()
        backend.set_per_monitor_legacy.assert_called_once()

    def test_dpi_awareness_requires_confirmation_after_attempts(self) -> None:
        backend = Mock()
        backend.is_per_monitor.side_effect = [False, False, False]
        backend.set_per_monitor_v2.return_value = True
        backend.set_per_monitor_legacy.return_value = True

        self.assertFalse(enable_per_monitor_dpi_awareness(backend))

    def test_dpi_queries_after_failed_v2_before_using_legacy_fallback(self) -> None:
        backend = Mock()
        backend.is_per_monitor.side_effect = [False, True]
        backend.set_per_monitor_v2.return_value = False

        self.assertTrue(enable_per_monitor_dpi_awareness(backend))
        self.assertEqual(
            [call.is_per_monitor(), call.set_per_monitor_v2(), call.is_per_monitor()],
            backend.mock_calls,
        )

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

    def test_drag_gap_tie_prefers_last_intersected_monitor(self) -> None:
        left = MonitorInfo("LEFT", WorkArea(0, 0, 100, 100), False)
        right = MonitorInfo("RIGHT", WorkArea(200, 0, 300, 100), True)
        selected = select_drag_monitor(Point(145, 20), Size(10, 10), [left, right], "RIGHT")
        self.assertEqual("RIGHT", selected.id)


class MonitorBackendTests(unittest.TestCase):
    def test_enumerate_maps_pywin32_work_area_and_primary_flag(self) -> None:
        api = Mock()
        api.EnumDisplayMonitors.return_value = [("handle", None, None)]
        api.GetMonitorInfo.return_value = {
            "Work": (-1280, 0, 0, 984),
            "Device": "DISPLAY2",
            "Flags": 1,
        }

        monitors = Win32MonitorBackend(api).enumerate()

        self.assertEqual([MonitorInfo("DISPLAY2", WorkArea(-1280, 0, 0, 984), True)], monitors)

    def test_refresh_rejects_empty_windows_enumeration(self) -> None:
        backend = Mock()
        backend.enumerate.return_value = []

        with self.assertRaisesRegex(RuntimeError, "no monitors"):
            MonitorService(backend).refresh()

    def test_empty_refresh_clears_monitors_from_successful_previous_refresh(self) -> None:
        backend = Mock()
        backend.enumerate.side_effect = [[MONITOR_1], []]
        service = MonitorService(backend)
        service.refresh()

        with self.assertRaisesRegex(RuntimeError, "no monitors"):
            service.refresh()
        with self.assertRaisesRegex(ValueError, "at least one monitor"):
            service.primary()


class WindowsDpiAwarenessBackendTests(unittest.TestCase):
    def test_legacy_fallback_remains_available_when_v2_export_is_absent(self) -> None:
        user32 = Mock(spec=[])
        backend = WindowsDpiAwarenessBackend(user32=user32, shcore=Mock(), kernel32=Mock())

        self.assertFalse(backend.set_per_monitor_v2())


if __name__ == "__main__":
    unittest.main()
