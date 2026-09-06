"""Application composition and command-line entry points for Mikan Pet."""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

from mikan_pet.core.sprites import validate_registry
from mikan_pet.core.state import PetController, PetState
from mikan_pet.core.types import Direction, MotionMode, Pose
from mikan_pet.core.window_layout import DpiMetrics, metrics_for_dpi
from mikan_pet.services.media_info import MediaInfoService
from mikan_pet.services.media_keys import MEDIA_VIRTUAL_KEYS, MediaAction, MediaKeyService
from mikan_pet.services.monitors import MonitorService, Win32MonitorBackend, default_position, enable_per_monitor_dpi_awareness
from mikan_pet.services.settings import AppSettings, SettingsStore, default_settings, settings_path
from mikan_pet.services.singleton import SingleInstance
from mikan_pet.ui.dpi import DpiWatcher
from mikan_pet.ui.pet_window import PetWindow
from mikan_pet.ui.sprite_cache import SpriteCache


VERSION = "0.1.13"
_MUTEX_NAME = "Local\\MikanPet"

WindowFactory = Callable[[AppSettings, MonitorService, MediaKeyService, Callable[[AppSettings], None]], PetWindow]


class MikanPetApplication:
    """Own the production resources for a single application run."""

    def __init__(
        self,
        *,
        singleton: SingleInstance,
        settings_store: SettingsStore,
        monitor_service: MonitorService,
        media_service: MediaKeyService,
        window_factory: WindowFactory,
    ) -> None:
        self.singleton = singleton
        self.settings_store = settings_store
        self.monitor_service = monitor_service
        self.media_service = media_service
        self.window_factory = window_factory

    def run(self) -> int:
        if not self.singleton.acquire():
            return 0
        window: PetWindow | None = None
        try:
            settings = self.settings_store.load()
            window = self.window_factory(
                settings=settings,
                monitor_service=self.monitor_service,
                media_service=self.media_service,
                on_settings_changed=self.settings_store.save,
            )
            window.run()
            return 0
        finally:
            try:
                if window is not None:
                    try:
                        self.settings_store.save(window.snapshot_settings())
                    finally:
                        window.close()
            finally:
                self.singleton.release()


def realized_dpi(root: object) -> int:
    """Read the already-realized Tk root DPI as an integer physical value."""
    return int(round(float(root.winfo_fpixels("1i"))))


def _state_from_settings(
    settings: AppSettings,
    monitor_service: MonitorService,
    metrics: DpiMetrics,
) -> PetState:
    if settings.position is None:
        margin = (24 * metrics.dpi + 48) // 96
        position = default_position(monitor_service.primary().work_area, metrics.pet_size, margin)
    else:
        position = monitor_service.recover_position(settings.position, metrics.pet_size)
    walking = settings.walking
    return PetState(
        position=position,
        direction=Direction.LEFT,
        motion=MotionMode.AUTOMATIC if walking else MotionMode.STOPPED,
        pose=Pose.WALK if walking else Pose.IDLE,
        skin=settings.skin,
        controls_visible=settings.controls_visible,
        always_on_top=settings.always_on_top,
    )


def default_window_factory(
    settings: AppSettings,
    monitor_service: MonitorService,
    media_service: MediaKeyService,
    on_settings_changed: Callable[[AppSettings], None],
) -> PetWindow:
    """Create the real Tk window only after DPI awareness is confirmed."""
    if not enable_per_monitor_dpi_awareness():
        raise RuntimeError("Per-monitor DPI awareness could not be confirmed")
    monitor_service.refresh()
    root = tk.Tk()
    try:
        controller = PetController(
            _state_from_settings(
                settings,
                monitor_service,
                metrics_for_dpi(realized_dpi(root)),
            )
        )
        sprite_cache = SpriteCache(tk.PhotoImage)
        return PetWindow(
            root,
            controller,
            sprite_cache,
            monitor_service,
            media_service,
            on_settings_changed,
            DpiWatcher,
            MediaInfoService(),
        )
    except Exception:
        root.destroy()
        raise


def create_application() -> MikanPetApplication:
    """Compose the normal, persistence-enabled production application."""
    return MikanPetApplication(
        singleton=SingleInstance(_MUTEX_NAME),
        settings_store=SettingsStore(settings_path()),
        monitor_service=MonitorService(Win32MonitorBackend()),
        media_service=MediaKeyService(),
        window_factory=default_window_factory,
    )


def validate_smoke_contract() -> list[str]:
    """Check package data without creating a window or Windows side effects."""
    errors = list(validate_registry())
    expected_actions = {MediaAction.PREVIOUS, MediaAction.PLAY_PAUSE, MediaAction.NEXT}
    if set(MEDIA_VIRTUAL_KEYS) != expected_actions:
        errors.append("media virtual-key map must contain previous, play/pause, and next")
    if default_settings().schema_version != 1:
        errors.append("default settings must use schema version 1")
    return errors


def run_gui_smoke_test(*, window_factory: WindowFactory = default_window_factory) -> int:
    """Briefly render the real GUI without user settings or a production mutex."""
    window: PetWindow | None = None
    try:
        window = window_factory(
            default_settings(),
            MonitorService(Win32MonitorBackend()),
            MediaKeyService(),
            lambda _settings: None,
        )
        window.close_after(1500)
        window.run()
        return 0
    finally:
        if window is not None:
            window.close()


def _run_production() -> int:
    try:
        return create_application().run()
    except Exception as error:
        messagebox.showerror("Mikan Pet", f"Mikan Pet tidak dapat dimulai: {error}")
        return 1


def main(argv: list[str] | None = None) -> int:
    """Dispatch explicit diagnostics or launch the production application."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return _run_production()
    if arguments == ["--smoke-test"]:
        return 0 if not validate_smoke_contract() else 1
    if arguments == ["--gui-smoke-test"]:
        return run_gui_smoke_test()
    if arguments == ["--version"]:
        print(VERSION)
        return 0
    return 2
