import unittest
from dataclasses import replace

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

    def test_walk_wraps_from_left_edge_and_keeps_heading_left(self) -> None:
        controller = self.make_controller()
        controller.state = replace(
            controller.state,
            position=Point(10, 40),
            direction=Direction.LEFT,
        )
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
        controller.tick(250, WorkArea(0, 0, 500, 300), Size(20, 20), dpi_scale=1.5)
        self.assertEqual(Point(85, 40), controller.state.position)

    def test_fractional_physical_motion_is_carried_between_ticks(self) -> None:
        controller = self.make_controller()
        area = WorkArea(0, 0, 500, 300)
        controller.tick(50, area, Size(20, 20), dpi_scale=1.25)
        controller.tick(50, area, Size(20, 20), dpi_scale=1.25)
        self.assertEqual(Point(75, 40), controller.state.position)

    def test_rejects_non_positive_dpi_scale(self) -> None:
        controller = self.make_controller()
        with self.assertRaises(ValueError):
            controller.tick(50, WorkArea(0, 0, 500, 300), Size(20, 20), dpi_scale=0)

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
