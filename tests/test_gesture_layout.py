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

    def test_nonpositive_dpi_is_rejected_by_all_dpi_helpers(self) -> None:
        for dpi in (0, -1):
            with self.subTest(dpi=dpi):
                with self.assertRaises(ValueError):
                    metrics_for_dpi(dpi)
                with self.assertRaises(ValueError):
                    drag_offset_to_logical(Point(1, 1), dpi)
                with self.assertRaises(ValueError):
                    position_from_pointer(Point(1, 1), Point(1, 1), dpi)

    def test_fractional_and_bool_dpi_are_rejected_by_all_dpi_helpers(self) -> None:
        for dpi in (96.5, True):
            with self.subTest(dpi=dpi):
                with self.assertRaises(ValueError):
                    metrics_for_dpi(dpi)
                with self.assertRaises(ValueError):
                    drag_offset_to_logical(Point(1, 1), dpi)
                with self.assertRaises(ValueError):
                    position_from_pointer(Point(1, 1), Point(1, 1), dpi)

    def test_release_only_reports_a_result_once_and_unpressed_moves_are_safe(self) -> None:
        gesture = PointerGesture(threshold=5)
        self.assertFalse(gesture.move(Point(1, 1)))
        self.assertIsNone(gesture.release(Point(1, 1)))
        gesture.press(Point(10, 10))
        self.assertEqual(GestureResult.CLICK, gesture.release(Point(10, 10)))
        self.assertIsNone(gesture.release(Point(10, 10)))

    def test_threshold_update_preserves_dragged_state(self) -> None:
        gesture = PointerGesture(threshold=5)
        gesture.press(Point(0, 0))
        self.assertTrue(gesture.move(Point(5, 0)))
        gesture.set_threshold(100)
        self.assertTrue(gesture.dragged)

    def test_expanded_layout_and_safe_bounds_scale_at_150_percent(self) -> None:
        metrics = metrics_for_dpi(144)
        pet = Point(750, 600)
        layout = calculate_window_layout(pet, True, metrics)
        self.assertEqual(pet, layout.pet_screen_origin)
        self.assertEqual(Point(708, 480), layout.root_origin)
        self.assertEqual(WorkArea(42, 120, 2838, 1560), safe_pet_work_area(WorkArea(0, 0, 2880, 1560), True, metrics))

    def test_tiny_expanded_work_area_falls_back_to_a_valid_clamp_anchor(self) -> None:
        original = WorkArea(0, 0, 40, 60)
        safe = safe_pet_work_area(original, True, metrics_for_dpi(96))
        self.assertEqual(WorkArea(28, 60, 28, 60), safe)
        self.assertLessEqual(safe.left, safe.right)
        self.assertLessEqual(safe.top, safe.bottom)
        self.assertGreaterEqual(safe.left, original.left)
        self.assertGreaterEqual(safe.top, original.top)
        self.assertLessEqual(safe.right, original.right)
        self.assertLessEqual(safe.bottom, original.bottom)


if __name__ == "__main__":
    unittest.main()
