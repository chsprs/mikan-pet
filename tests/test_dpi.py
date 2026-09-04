import ctypes
import gc
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import Mock, call

from mikan_pet.ui.dpi import WM_DPICHANGED, DpiWatcher, Win32DpiBackend, dpi_from_wparam


class DpiWatcherTests(unittest.TestCase):
    def test_extracts_new_dpi_from_wparam(self) -> None:
        self.assertEqual(144, dpi_from_wparam(144 | (144 << 16)))

    def test_schedules_callback_and_applies_suggested_rectangle(self) -> None:
        root = Mock()
        backend = Mock()
        backend.read_suggested_rect.return_value = (100, 200, 400, 520)
        callback = Mock()
        watcher = DpiWatcher(root, callback, backend)
        watcher.handle_message(WM_DPICHANGED, 144 | (144 << 16), 1234)
        backend.apply_suggested_rect.assert_called_once_with((100, 200, 400, 520))
        root.after_idle.assert_called_once()
        root.after_idle.call_args.args[0]()
        callback.assert_called_once_with(144, (100, 200, 400, 520))

    def test_install_resolves_top_level_hwnd_and_reports_initial_dpi(self) -> None:
        root = Mock()
        root.winfo_id.return_value = 123
        backend = Mock()
        backend.resolve_top_level.return_value = 456
        backend.get_window_dpi.return_value = 144
        watcher = DpiWatcher(root, Mock(), backend)
        self.assertEqual(144, watcher.install())
        root.update_idletasks.assert_called_once()
        backend.resolve_top_level.assert_called_once_with(123)
        backend.install_subclass.assert_called_once_with(456, watcher.handle_message)

    def test_close_restores_subclass_exactly_once(self) -> None:
        root = Mock()
        root.winfo_id.return_value = 123
        backend = Mock()
        backend.resolve_top_level.return_value = 456
        backend.get_window_dpi.return_value = 96
        watcher = DpiWatcher(root, Mock(), backend)
        watcher.install()

        watcher.close()
        watcher.close()

        backend.restore_subclass.assert_called_once()

    def test_late_idle_callback_is_ignored_after_close(self) -> None:
        root = Mock()
        backend = Mock()
        backend.read_suggested_rect.return_value = (1, 2, 11, 22)
        callback = Mock()
        watcher = DpiWatcher(root, callback, backend)
        watcher.handle_message(WM_DPICHANGED, 120, 99)
        scheduled = root.after_idle.call_args.args[0]

        watcher.close()
        scheduled()

        callback.assert_not_called()

    def test_non_dpi_message_delegates_to_previous_window_proc(self) -> None:
        backend = Mock()
        backend.call_previous.return_value = 73
        watcher = DpiWatcher(Mock(), Mock(), backend)
        self.assertEqual(73, watcher.handle_message(0x0010, 4, 5))
        backend.call_previous.assert_called_once_with(0x0010, 4, 5)


class Win32DpiBackendTests(unittest.TestCase):
    def test_resolve_top_level_prefers_parent_wrapper_when_present(self) -> None:
        win32gui = Mock()
        win32gui.GetParent.return_value = 456
        backend = Win32DpiBackend(win32gui_module=win32gui, win32con_module=Mock(), user32=Mock())
        self.assertEqual(456, backend.resolve_top_level(123))

    def test_missing_get_dpi_for_window_falls_back_to_96(self) -> None:
        backend = Win32DpiBackend(
            win32gui_module=Mock(), win32con_module=Mock(), user32=Mock(spec=[])
        )
        self.assertEqual(96, backend.get_window_dpi(123))

    def test_reads_native_rect_and_applies_xy_size_with_required_flags(self) -> None:
        class NativeRect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        win32gui = Mock()
        win32gui.SetWindowLong.return_value = object()
        win32con = SimpleNamespace(GWL_WNDPROC=-4, SWP_NOZORDER=4, SWP_NOACTIVATE=16)
        backend = Win32DpiBackend(win32gui_module=win32gui, win32con_module=win32con, user32=Mock())
        backend.install_subclass(456, Mock(return_value=0))
        native = NativeRect(100, 200, 400, 520)

        rect = backend.read_suggested_rect(ctypes.addressof(native))
        backend.apply_suggested_rect(rect)

        self.assertEqual((100, 200, 400, 520), rect)
        win32gui.SetWindowPos.assert_called_once_with(456, 0, 100, 200, 300, 320, 20)

    def test_calls_saved_window_proc_for_delegated_message(self) -> None:
        win32gui = Mock()
        previous = object()
        win32gui.SetWindowLong.return_value = previous
        win32gui.CallWindowProc.return_value = 27
        win32con = SimpleNamespace(GWL_WNDPROC=-4)
        backend = Win32DpiBackend(win32gui_module=win32gui, win32con_module=win32con, user32=Mock())
        backend.install_subclass(456, Mock(return_value=0))

        self.assertEqual(27, backend.call_previous(0x0010, 4, 5))
        win32gui.CallWindowProc.assert_called_once_with(previous, 456, 0x0010, 4, 5)

    def test_native_subclass_retains_callback_and_restores_previous_proc(self) -> None:
        win32gui = Mock()
        previous = object()
        win32gui.SetWindowLong.return_value = previous
        win32con = Mock(GWL_WNDPROC=-4)
        backend = Win32DpiBackend(win32gui_module=win32gui, win32con_module=win32con, user32=Mock())
        handler = Mock(return_value=19)

        backend.install_subclass(456, handler)
        callback_ref = weakref.ref(win32gui.SetWindowLong.call_args.args[2])
        gc.collect()
        self.assertIsNotNone(callback_ref())
        self.assertEqual(19, callback_ref()(456, WM_DPICHANGED, 144, 900))

        backend.restore_subclass()
        backend.restore_subclass()
        self.assertEqual(
            [call(456, -4, win32gui.SetWindowLong.call_args_list[0].args[2]), call(456, -4, previous)],
            win32gui.SetWindowLong.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
