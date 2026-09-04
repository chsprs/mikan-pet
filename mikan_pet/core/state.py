from dataclasses import dataclass, replace

from mikan_pet.core.types import Direction, MotionMode, Point, Pose, Size, SkinId, WorkArea


@dataclass(frozen=True)
class BehaviorDurations:
    walk_ms: int = 9000
    idle_ms: int = 3500
    sleep_ms: int = 7000
    react_ms: int = 450
    sleep_every: int = 3


@dataclass(frozen=True)
class PetState:
    position: Point
    direction: Direction
    motion: MotionMode
    pose: Pose
    skin: SkinId
    controls_visible: bool
    always_on_top: bool


class PetController:
    SPEED_LOGICAL_PX_PER_SECOND = 40.0

    def __init__(self, state: PetState, durations: BehaviorDurations | None = None) -> None:
        self.state = state
        self.durations = durations or BehaviorDurations()
        self.phase_elapsed_ms = 0
        self.completed_idle_count = 0
        self._movement_remainder = 0.0
        self._pre_drag_motion = state.motion
        self._pose_before_reaction = state.pose

    def tick(self, elapsed_ms: int, area: WorkArea, pet_size: Size, dpi_scale: float = 1.0) -> PetState:
        if dpi_scale <= 0:
            raise ValueError("dpi_scale must be positive")
        if elapsed_ms <= 0:
            return self.state
        if self.state.motion is MotionMode.DRAGGING:
            return self.state
        if self.state.pose is Pose.REACT:
            self.phase_elapsed_ms += elapsed_ms
            if self.phase_elapsed_ms >= self.durations.react_ms:
                restored = self._pose_before_reaction if self.state.motion is MotionMode.AUTOMATIC else Pose.IDLE
                self.state = replace(self.state, pose=restored)
                self.phase_elapsed_ms = 0
            return self.state
        if self.state.motion is MotionMode.STOPPED:
            self.phase_elapsed_ms += elapsed_ms
            if self.state.pose is Pose.IDLE and self.phase_elapsed_ms >= self.durations.idle_ms * 3:
                self.state = replace(self.state, pose=Pose.SLEEP)
                self.phase_elapsed_ms = 0
            elif self.state.pose is Pose.SLEEP and self.phase_elapsed_ms >= self.durations.sleep_ms:
                self.state = replace(self.state, pose=Pose.IDLE)
                self.phase_elapsed_ms = 0
            return self.state
        self.phase_elapsed_ms += elapsed_ms
        if self.state.pose is Pose.WALK:
            self._move(elapsed_ms, area, pet_size, dpi_scale)
            if self.phase_elapsed_ms >= self.durations.walk_ms:
                self.phase_elapsed_ms = 0
                self.completed_idle_count += 1
                next_pose = Pose.SLEEP if self.completed_idle_count % self.durations.sleep_every == 0 else Pose.IDLE
                self.state = replace(self.state, pose=next_pose)
        elif self.state.pose is Pose.IDLE and self.phase_elapsed_ms >= self.durations.idle_ms:
            self.phase_elapsed_ms = 0
            self.state = replace(self.state, pose=Pose.WALK)
        elif self.state.pose is Pose.SLEEP and self.phase_elapsed_ms >= self.durations.sleep_ms:
            self.phase_elapsed_ms = 0
            self.state = replace(self.state, pose=Pose.WALK)
        return self.state

    def _move(self, elapsed_ms: int, area: WorkArea, pet_size: Size, dpi_scale: float) -> None:
        distance = self.SPEED_LOGICAL_PX_PER_SECOND * dpi_scale * elapsed_ms / 1000 + self._movement_remainder
        pixels = int(distance)
        self._movement_remainder = distance - pixels
        delta = pixels * self.state.direction.value
        minimum = area.left
        maximum = area.right - pet_size.width
        candidate = self.state.position.x + delta
        direction = self.state.direction
        if candidate <= minimum:
            candidate, direction = minimum, Direction.RIGHT
            self._movement_remainder = 0.0
        elif candidate >= maximum:
            candidate, direction = maximum, Direction.LEFT
            self._movement_remainder = 0.0
        maximum_y = area.bottom - pet_size.height
        y = min(max(self.state.position.y, area.top), maximum_y)
        self.state = replace(self.state, position=Point(candidate, y), direction=direction)

    def toggle_walking(self) -> None:
        if self.state.motion is MotionMode.STOPPED:
            self.state = replace(self.state, motion=MotionMode.AUTOMATIC, pose=Pose.WALK)
        else:
            self.state = replace(self.state, motion=MotionMode.STOPPED, pose=Pose.IDLE)
        self.phase_elapsed_ms = 0
        self._movement_remainder = 0.0

    def begin_drag(self) -> None:
        self._pre_drag_motion = self.state.motion
        self.state = replace(self.state, motion=MotionMode.DRAGGING)
        self._movement_remainder = 0.0

    def drag_to(self, position: Point) -> None:
        self.state = replace(self.state, position=position)

    def place_within(self, area: WorkArea, pet_size: Size) -> None:
        x = min(max(self.state.position.x, area.left), area.right - pet_size.width)
        y = min(max(self.state.position.y, area.top), area.bottom - pet_size.height)
        self.state = replace(self.state, position=Point(x, y))

    def end_drag(self) -> None:
        motion = self._pre_drag_motion
        if motion not in (MotionMode.AUTOMATIC, MotionMode.STOPPED):
            motion = MotionMode.AUTOMATIC
        pose = Pose.WALK if motion is MotionMode.AUTOMATIC else Pose.IDLE
        self.state = replace(self.state, motion=motion, pose=pose)
        self.phase_elapsed_ms = 0

    def react(self) -> None:
        if self.state.pose is not Pose.REACT:
            self._pose_before_reaction = self.state.pose
        self.state = replace(self.state, pose=Pose.REACT)
        self.phase_elapsed_ms = 0

    def set_controls_visible(self, visible: bool) -> None:
        self.state = replace(self.state, controls_visible=visible)

    def set_skin(self, skin: SkinId) -> None:
        self.state = replace(self.state, skin=skin)

    def set_always_on_top(self, enabled: bool) -> None:
        self.state = replace(self.state, always_on_top=enabled)

    def stop_and_idle(self) -> None:
        self._pre_drag_motion = MotionMode.STOPPED
        self.state = replace(self.state, motion=MotionMode.STOPPED, pose=Pose.IDLE)
        self.phase_elapsed_ms = 0
        self._movement_remainder = 0.0
