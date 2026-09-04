import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from mikan_pet.app import (
    MikanPetApplication,
    default_window_factory,
    main,
    run_gui_smoke_test,
    validate_smoke_contract,
)
from mikan_pet.core.state import PetController, PetState
from mikan_pet.core.types import Direction, MotionMode, Point, Pose, SkinId, Size, WorkArea
from mikan_pet.services.media_keys import MediaAction
from mikan_pet.services.monitors import MonitorInfo
from mikan_pet.services.settings import default_settings
from mikan_pet.ui.dpi import Win32DpiBackend


class AppTests(unittest.TestCase):
    def make_app(self, *, singleton=None, store=None, window_factory=None) -> MikanPetApplication:
        if singleton is None:
            singleton = Mock()
            singleton.acquire.return_value = True
        if store is None:
            store = Mock()
            store.load.return_value = default_settings()
        return MikanPetApplication(
            singleton=singleton,
            settings_store=store,
            monitor_service=Mock(),
            media_service=Mock(),
            window_factory=Mock() if window_factory is None else window_factory,
        )

    def test_duplicate_instance_exits_without_window_or_release(self) -> None:
        singleton = Mock()
        singleton.acquire.return_value = False
        window_factory = Mock()
        app = self.make_app(singleton=singleton, window_factory=window_factory)

        self.assertEqual(0, app.run())

        window_factory.assert_not_called()
        singleton.release.assert_not_called()

    def test_normal_run_loads_runs_saves_closes_and_releases_in_order(self) -> None:
        events: list[str] = []
        singleton = Mock()
        singleton.acquire.side_effect = lambda: events.append("acquire") or True
        singleton.release.side_effect = lambda: events.append("release")
        store = Mock()
        store.load.side_effect = lambda: events.append("load") or default_settings()
        store.save.side_effect = lambda settings: events.append("save")
        window = Mock()
        window.run.side_effect = lambda: events.append("run")
        window.snapshot_settings.side_effect = lambda: events.append("snapshot") or default_settings()
        window.close.side_effect = lambda: events.append("close")
        factory = Mock(side_effect=lambda **kwargs: events.append("factory") or window)
        app = self.make_app(singleton=singleton, store=store, window_factory=factory)

        self.assertEqual(0, app.run())

        self.assertEqual(["acquire", "load", "factory", "run", "snapshot", "save", "close", "release"], events)
        self.assertIs(store.save, factory.call_args.kwargs["on_settings_changed"])

    def test_load_failure_releases_singleton_without_constructing_window(self) -> None:
        singleton = Mock()
        singleton.acquire.return_value = True
        store = Mock()
        store.load.side_effect = RuntimeError("load failed")
        factory = Mock()
        app = self.make_app(singleton=singleton, store=store, window_factory=factory)

        with self.assertRaisesRegex(RuntimeError, "load failed"):
            app.run()

        factory.assert_not_called()
        singleton.release.assert_called_once()

    def test_factory_failure_releases_singleton_without_window_cleanup(self) -> None:
        singleton = Mock()
        singleton.acquire.return_value = True
        store = Mock()
        store.load.return_value = default_settings()
        factory = Mock(side_effect=RuntimeError("factory failed"))
        app = self.make_app(singleton=singleton, store=store, window_factory=factory)

        with self.assertRaisesRegex(RuntimeError, "factory failed"):
            app.run()

        store.save.assert_not_called()
        singleton.release.assert_called_once()

    def test_run_failure_still_saves_closes_and_releases(self) -> None:
        events: list[str] = []
        singleton = Mock()
        singleton.acquire.return_value = True
        singleton.release.side_effect = lambda: events.append("release")
        store = Mock()
        store.load.return_value = default_settings()
        store.save.side_effect = lambda settings: events.append("save")
        window = Mock()
        window.run.side_effect = RuntimeError("run failed")
        window.snapshot_settings.side_effect = lambda: events.append("snapshot") or default_settings()
        window.close.side_effect = lambda: events.append("close")
        app = self.make_app(singleton=singleton, store=store, window_factory=Mock(return_value=window))

        with self.assertRaisesRegex(RuntimeError, "run failed"):
            app.run()

        self.assertEqual(["snapshot", "save", "close", "release"], events)

    def test_snapshot_failure_still_closes_window_and_releases_singleton(self) -> None:
        events: list[str] = []
        singleton = Mock()
        singleton.acquire.return_value = True
        singleton.release.side_effect = lambda: events.append("release")
        store = Mock()
        store.load.return_value = default_settings()
        window = Mock()
        window.snapshot_settings.side_effect = RuntimeError("snapshot failed")
        window.close.side_effect = lambda: events.append("close")
        app = self.make_app(singleton=singleton, store=store, window_factory=Mock(return_value=window))

        with self.assertRaisesRegex(RuntimeError, "snapshot failed"):
            app.run()

        self.assertEqual(["close", "release"], events)

    def test_save_failure_still_closes_window_and_releases_singleton(self) -> None:
        events: list[str] = []
        singleton = Mock()
        singleton.acquire.return_value = True
        singleton.release.side_effect = lambda: events.append("release")
        store = Mock()
        store.load.return_value = default_settings()
        store.save.side_effect = RuntimeError("save failed")
        window = Mock()
        window.snapshot_settings.return_value = default_settings()
        window.close.side_effect = lambda: events.append("close")
        app = self.make_app(singleton=singleton, store=store, window_factory=Mock(return_value=window))

        with self.assertRaisesRegex(RuntimeError, "save failed"):
            app.run()

        self.assertEqual(["close", "release"], events)

    def test_close_failure_still_releases_singleton(self) -> None:
        singleton = Mock()
        singleton.acquire.return_value = True
        store = Mock()
        store.load.return_value = default_settings()
        window = Mock()
        window.snapshot_settings.return_value = default_settings()
        window.close.side_effect = RuntimeError("close failed")
        app = self.make_app(singleton=singleton, store=store, window_factory=Mock(return_value=window))

        with self.assertRaisesRegex(RuntimeError, "close failed"):
            app.run()

        singleton.release.assert_called_once()

    def test_smoke_contract_validates_registry_media_map_and_schema(self) -> None:
        self.assertEqual([], validate_smoke_contract())

    def test_gui_smoke_is_bounded_and_closes_after_a_normal_run(self) -> None:
        window = Mock()
        factory = Mock(return_value=window)

        self.assertEqual(0, run_gui_smoke_test(window_factory=factory))

        window.close_after.assert_called_once_with(1500)
        window.run.assert_called_once()
        window.close.assert_called_once()

    def test_gui_smoke_is_bounded_and_always_closes_after_run_failure(self) -> None:
        window = Mock()
        window.run.side_effect = RuntimeError("run failed")
        factory = Mock(return_value=window)

        with self.assertRaisesRegex(RuntimeError, "run failed"):
            run_gui_smoke_test(window_factory=factory)

        window.close_after.assert_called_once_with(1500)
        window.close.assert_called_once()

    def test_window_factory_fails_before_tk_when_dpi_awareness_is_unavailable(self) -> None:
        with patch("mikan_pet.app.enable_per_monitor_dpi_awareness", return_value=False), patch(
            "mikan_pet.app.tk.Tk"
        ) as root_factory:
            with self.assertRaisesRegex(RuntimeError, "DPI"):
                default_window_factory(default_settings(), Mock(), Mock(), Mock())

        root_factory.assert_not_called()

    def test_window_factory_refreshes_recovers_and_constructs_expected_state(self) -> None:
        monitor = MonitorInfo("DISPLAY1", WorkArea(0, 0, 1920, 1040), True)
        monitor_service = Mock()
        monitor_service.primary.return_value = monitor
        construction_events: list[str] = []
        monitor_service.refresh.side_effect = lambda: construction_events.append("refresh")
        monitor_service.recover_position.side_effect = lambda *_args: construction_events.append("recover") or Point(300, 400)
        settings = default_settings().__class__(
            position=Point(9000, 9000), skin=SkinId.BYTE, walking=False,
            controls_visible=False, always_on_top=False,
        )
        root = Mock()
        window = Mock()
        callback = Mock()
        with patch("mikan_pet.app.enable_per_monitor_dpi_awareness", return_value=True), patch(
            "mikan_pet.app.tk.Tk", side_effect=lambda: construction_events.append("root") or root
        ) as root_factory, patch("mikan_pet.app.tk.PhotoImage") as photo_factory, patch(
            "mikan_pet.app.SpriteCache", side_effect=lambda *_args: construction_events.append("cache") or Mock()
        ) as cache_factory, patch(
            "mikan_pet.app.PetWindow", side_effect=lambda *_args: construction_events.append("window") or window
        ) as window_class:
            result = default_window_factory(settings, monitor_service, Mock(), callback)

        self.assertIs(window, result)
        monitor_service.refresh.assert_called_once()
        monitor_service.recover_position.assert_called_once_with(Point(9000, 9000), Size(144, 128))
        self.assertEqual(["refresh", "recover", "root", "cache", "window"], construction_events)
        root_factory.assert_called_once()
        state = window_class.call_args.args[1].state
        self.assertEqual(
            PetState(Point(300, 400), Direction.RIGHT, MotionMode.STOPPED, Pose.IDLE,
                     SkinId.BYTE, False, False),
            state,
        )
        self.assertIsInstance(window_class.call_args.args[1], PetController)
        self.assertIs(callback, window_class.call_args.args[5])
        cache_factory.assert_called_once_with(photo_factory)

    def test_window_factory_destroys_partially_created_root_when_window_construction_fails(self) -> None:
        monitor = MonitorInfo("DISPLAY1", WorkArea(0, 0, 1920, 1040), True)
        monitor_service = Mock()
        monitor_service.primary.return_value = monitor
        root = Mock()
        with patch("mikan_pet.app.enable_per_monitor_dpi_awareness", return_value=True), patch(
            "mikan_pet.app.tk.Tk", return_value=root
        ), patch("mikan_pet.app.PetWindow", side_effect=RuntimeError("window failed")):
            with self.assertRaisesRegex(RuntimeError, "window failed"):
                default_window_factory(default_settings(), monitor_service, Mock(), Mock())

        root.destroy.assert_called_once()

    def test_dpi_close_restores_raw_wndproc_pointer_without_pywin32_callable_conversion(self) -> None:
        win32gui = Mock()
        win32gui.SetWindowLong.return_value = 0x12345678
        win32con = Mock(GWL_WNDPROC=-4)
        user32 = Mock()
        backend = Win32DpiBackend(win32gui_module=win32gui, win32con_module=win32con, user32=user32)
        backend.install_subclass(456, Mock(return_value=0))

        backend.restore_subclass()

        user32.SetWindowLongPtrW.assert_called_once()
        self.assertEqual((456, -4, 0x12345678), (
            user32.SetWindowLongPtrW.call_args.args[0],
            user32.SetWindowLongPtrW.call_args.args[1],
            user32.SetWindowLongPtrW.call_args.args[2].value,
        ))

    def test_main_smoke_mode_has_no_production_side_effects(self) -> None:
        with patch("mikan_pet.app.validate_smoke_contract", return_value=[]), patch(
            "mikan_pet.app.create_application"
        ) as create_application, patch("mikan_pet.app.run_gui_smoke_test") as gui_smoke:
            self.assertEqual(0, main(["--smoke-test"]))

        create_application.assert_not_called()
        gui_smoke.assert_not_called()

    def test_main_smoke_mode_reports_failed_contract_without_launching(self) -> None:
        with patch("mikan_pet.app.validate_smoke_contract", return_value=["bad media map"]), patch(
            "mikan_pet.app.create_application"
        ) as create_application:
            self.assertEqual(1, main(["--smoke-test"]))

        create_application.assert_not_called()

    def test_main_gui_smoke_does_not_create_production_application(self) -> None:
        with patch("mikan_pet.app.run_gui_smoke_test", return_value=0) as gui_smoke, patch(
            "mikan_pet.app.create_application"
        ) as create_application:
            self.assertEqual(0, main(["--gui-smoke-test"]))

        gui_smoke.assert_called_once_with()
        create_application.assert_not_called()

    def test_main_version_prints_version_without_launching(self) -> None:
        output = StringIO()
        with redirect_stdout(output), patch("mikan_pet.app.create_application") as create_application:
            self.assertEqual(0, main(["--version"]))

        self.assertEqual("0.1.0\n", output.getvalue())
        create_application.assert_not_called()

    def test_main_rejects_unknown_or_mixed_arguments(self) -> None:
        for argv in (["--unknown"], ["--version", "--smoke-test"]):
            with self.subTest(argv=argv), patch("mikan_pet.app.create_application") as create_application:
                self.assertEqual(2, main(argv))
                create_application.assert_not_called()

    def test_main_runs_production_application_without_arguments(self) -> None:
        app = Mock()
        app.run.return_value = 0
        with patch("mikan_pet.app.create_application", return_value=app) as create_application:
            self.assertEqual(0, main([]))

        create_application.assert_called_once_with()
        app.run.assert_called_once()

    def test_main_shows_concise_error_only_for_production_failure(self) -> None:
        app = Mock()
        app.run.side_effect = RuntimeError("broken")
        with patch("mikan_pet.app.create_application", return_value=app), patch(
            "mikan_pet.app.messagebox.showerror"
        ) as showerror:
            self.assertEqual(1, main([]))

        showerror.assert_called_once()
        self.assertIn("broken", showerror.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
