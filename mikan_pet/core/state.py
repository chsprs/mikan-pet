from dataclasses import dataclass, replace

from mikan_pet.core.geometry import clamp_position
from mikan_pet.core.types import Direction, MotionMode, Point, Pose, Size, SkinId, WorkArea


@dataclass(frozen=True)
class BehaviorDurations:
    walk_ms: int = 9000
    idle_ms: int = 3500
    sleep_ms: int = 7000
    react_ms: int = 450
    activity_ms: int = 1440
    stretch_ms: int = 1080
    jump_ms: int = 1080
    land_ms: int = 720
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
    REST_ACTIVITIES = (Pose.GROOM, Pose.SCRATCH, Pose.TAIL, Pose.LOOK, Pose.PLAY)
    TRANSIENT_POSES = (Pose.REACT, Pose.JUMP)

    def __init__(self, state: PetState, durations: BehaviorDurations | None = None) -> None:
        self.state = state
        self.durations = durations or BehaviorDurations()
        self.phase_elapsed_ms = 0
        self.completed_idle_count = 0
        self._movement_remainder = 0.0
        self._pre_drag_motion = state.motion
        self._pose_before_reaction = state.pose
        self._phase_before_reaction = 0
        self._pre_drag_pose = state.pose
        self._pre_drag_elapsed = 0
        self._activity_index = 0
        self._rest_completed = False
        self._music_playing = False
        self._pointer_cooldown_ms = 0
        self._pointer_look = False
        self._look_direction = state.direction
        self._drag_sway_ms = 0
        self._drag_delta = 0
        self.carried_frame = 0

    def _enter(self, pose: Pose) -> None:
        self.state = replace(self.state, pose=pose)
        self.phase_elapsed_ms = 0

    def set_music_playing(self, playing: bool) -> None:
        self._music_playing = playing
        if not playing:
            if self._pre_drag_pose is Pose.MUSIC:
                self._pre_drag_pose, self._pre_drag_elapsed = Pose.IDLE, 0
            if self._pose_before_reaction is Pose.MUSIC:
                self._pose_before_reaction, self._phase_before_reaction = Pose.IDLE, 0
            if self.state.pose is Pose.MUSIC:
                self._rest_completed = True
                self._enter(Pose.IDLE)

    def look_at(self, direction: Direction) -> None:
        if self._pointer_look and self.state.pose is Pose.LOOK:
            self._look_direction = direction
            return
        if self._pointer_cooldown_ms or self.state.pose not in (Pose.IDLE, Pose.SIT, Pose.TAIL):
            return
        self._pointer_look = True
        self._look_direction = direction
        self._pose_before_look = self.state.pose
        self._phase_before_look = self.phase_elapsed_ms
        self._pointer_cooldown_ms = 5000
        self._enter(Pose.LOOK)

    @property
    def look_frame(self) -> int | None:
        if not self._pointer_look or self.state.pose is not Pose.LOOK:
            return None
        # Eyes follow screen direction even when the sprite is mirrored.
        return 4 if self._look_direction is self.state.direction else 1

    def tick(self, elapsed_ms: int, area: WorkArea, pet_size: Size, dpi_scale: float = 1.0) -> PetState:
        if dpi_scale <= 0:
            raise ValueError("dpi_scale must be positive")
        if elapsed_ms <= 0:
            return self.state
        self._pointer_cooldown_ms = max(0, self._pointer_cooldown_ms - elapsed_ms)
        if self.state.motion is MotionMode.DRAGGING:
            self._drag_sway_ms = max(0, self._drag_sway_ms - elapsed_ms)
            if not self._drag_sway_ms:
                self.carried_frame = 0
            return self.state
        self.phase_elapsed_ms += elapsed_ms
        pose = self.state.pose
        if pose in self.TRANSIENT_POSES:
            duration = self.durations.jump_ms if pose is Pose.JUMP else self.durations.react_ms
            if self.phase_elapsed_ms >= duration:
                self._enter(self._pose_before_reaction)
                self.phase_elapsed_ms = self._phase_before_reaction
            return self.state
        if pose is Pose.LAND:
            if self.phase_elapsed_ms >= self.durations.land_ms:
                self._enter(self._pre_drag_pose)
                self.phase_elapsed_ms = self._pre_drag_elapsed
            return self.state
        if self._pointer_look and pose is Pose.LOOK:
            if self.phase_elapsed_ms >= self.durations.activity_ms:
                self._pointer_look = False
                self._enter(self._pose_before_look)
                self.phase_elapsed_ms = self._phase_before_look
            return self.state
        if pose is Pose.WALK:
            if self.state.motion is MotionMode.AUTOMATIC:
                self._move(elapsed_ms, area, pet_size, dpi_scale)
            if self.phase_elapsed_ms >= self.durations.walk_ms:
                self.completed_idle_count += 1
                self._rest_completed = False
                self._enter(Pose.SIT)
        elif pose is Pose.SIT and self.phase_elapsed_ms >= self.durations.activity_ms:
            # Every other break may respond to music; all care/play poses remain reachable.
            activity = self.REST_ACTIVITIES[self._activity_index % len(self.REST_ACTIVITIES)]
            if self._music_playing and self._activity_index % 2 == 0:
                activity = Pose.MUSIC
            self._activity_index += 1
            self._enter(activity)
        elif pose in (*self.REST_ACTIVITIES, Pose.MUSIC):
            if self.phase_elapsed_ms >= self.durations.activity_ms:
                self._rest_completed = True
                self._enter(Pose.IDLE)
        elif pose is Pose.IDLE:
            duration = self.durations.idle_ms
            if self.state.motion is MotionMode.STOPPED:
                duration *= 3
            if self.phase_elapsed_ms >= duration:
                if not self._rest_completed:
                    self.completed_idle_count += 1
                    self._enter(Pose.SIT)
                elif self.completed_idle_count % self.durations.sleep_every == 0:
                    self._enter(Pose.YAWN)
                elif self.state.motion is MotionMode.AUTOMATIC:
                    self._enter(Pose.WALK)
                else:
                    self.completed_idle_count += 1
                    self._rest_completed = False
                    self._enter(Pose.SIT)
        elif pose is Pose.YAWN and self.phase_elapsed_ms >= self.durations.activity_ms:
            self._enter(Pose.SLEEP)
        elif pose is Pose.SLEEP and self.phase_elapsed_ms >= self.durations.sleep_ms:
            self._enter(Pose.STRETCH)
        elif pose is Pose.STRETCH and self.phase_elapsed_ms >= self.durations.stretch_ms:
            self._rest_completed = False
            self._enter(Pose.WALK if self.state.motion is MotionMode.AUTOMATIC else Pose.IDLE)
        return self.state

    def _move(self, elapsed_ms: int, area: WorkArea, pet_size: Size, dpi_scale: float) -> None:
        distance = self.SPEED_LOGICAL_PX_PER_SECOND * dpi_scale * elapsed_ms / 1000 + self._movement_remainder
        pixels = int(distance)
        self._movement_remainder = distance - pixels
        delta = pixels * self.state.direction.value
        minimum = area.left
        maximum = max(minimum, area.right - pet_size.width)
        candidate = self.state.position.x + delta
        direction = self.state.direction
        if candidate <= minimum:
            candidate, direction = minimum, Direction.RIGHT
            self._movement_remainder = 0.0
        elif candidate >= maximum:
            candidate, direction = maximum, Direction.LEFT
            self._movement_remainder = 0.0
        position = clamp_position(Point(candidate, self.state.position.y), pet_size, area)
        self.state = replace(self.state, position=position, direction=direction)

    def toggle_walking(self) -> None:
        if self.state.motion is MotionMode.STOPPED:
            self.state = replace(self.state, motion=MotionMode.AUTOMATIC, pose=Pose.WALK)
        else:
            self.state = replace(self.state, motion=MotionMode.STOPPED, pose=Pose.IDLE)
        self.phase_elapsed_ms = 0
        self._movement_remainder = 0.0
        self._rest_completed = False
        self._pointer_look = False

    def _uninterrupted_pose(self) -> tuple[Pose, int]:
        pose, elapsed = self.state.pose, self.phase_elapsed_ms
        if pose in self.TRANSIENT_POSES:
            pose, elapsed = self._pose_before_reaction, self._phase_before_reaction
        if pose is Pose.LAND:
            pose, elapsed = self._pre_drag_pose, self._pre_drag_elapsed
        if pose is Pose.LOOK and self._pointer_look:
            pose, elapsed = self._pose_before_look, self._phase_before_look
            self._pointer_look = False
        if pose is Pose.MUSIC and not self._music_playing:
            pose, elapsed = Pose.IDLE, 0
        return pose, elapsed

    def begin_drag(self) -> None:
        if self.state.motion is MotionMode.DRAGGING:
            return
        self._pre_drag_motion = self.state.motion
        self._pre_drag_pose, self._pre_drag_elapsed = self._uninterrupted_pose()
        self.state = replace(self.state, motion=MotionMode.DRAGGING)
        self._enter(Pose.CARRIED)
        self.carried_frame = 0
        self._drag_sway_ms = 0
        self._drag_delta = 0
        self._movement_remainder = 0.0

    def drag_to(self, position: Point) -> None:
        delta = position.x - self.state.position.x
        if self.state.motion is MotionMode.DRAGGING and delta:
            # Ignore single-pixel hand jitter, but accumulate deliberate slow movement.
            if delta * self._drag_delta < 0:
                self._drag_delta = 0
            self._drag_delta += delta
            if abs(self._drag_delta) >= 3:
                self.carried_frame = 1 if self._drag_delta * self.state.direction.value > 0 else 2
                self._drag_sway_ms = 180
                self._drag_delta = 0
        self.state = replace(self.state, position=position)

    def place_within(self, area: WorkArea, pet_size: Size) -> None:
        self.state = replace(self.state, position=clamp_position(self.state.position, pet_size, area))

    def end_drag(self) -> None:
        if self.state.motion is not MotionMode.DRAGGING:
            return
        motion = self._pre_drag_motion
        if motion not in (MotionMode.AUTOMATIC, MotionMode.STOPPED):
            motion = MotionMode.AUTOMATIC
        self.state = replace(self.state, motion=motion)
        self._enter(Pose.LAND)

    def react(self, *, jump: bool = False) -> None:
        if self.state.motion is MotionMode.DRAGGING:
            return
        self._pose_before_reaction, self._phase_before_reaction = self._uninterrupted_pose()
        self._enter(Pose.JUMP if jump else Pose.REACT)

    def set_controls_visible(self, visible: bool) -> None:
        self.state = replace(self.state, controls_visible=visible)

    def set_skin(self, skin: SkinId) -> None:
        self.state = replace(self.state, skin=skin)

    def set_always_on_top(self, enabled: bool) -> None:
        self.state = replace(self.state, always_on_top=enabled)

    def stop_and_idle(self) -> None:
        self._pre_drag_motion = MotionMode.STOPPED
        self._pointer_look = False
        self._rest_completed = False
        self.state = replace(self.state, motion=MotionMode.STOPPED, pose=Pose.IDLE)
        self.phase_elapsed_ms = 0
        self._movement_remainder = 0.0
