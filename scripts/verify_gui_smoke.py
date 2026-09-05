"""Require a visible Mikan Pet HWND and a bounded, successful frozen GUI exit."""

import json
import subprocess
import sys
import time
from pathlib import Path

import win32gui
import win32process


def verify_gui_smoke(executable: Path, timeout_seconds: float = 10.0) -> dict:
    started = time.monotonic()
    process = subprocess.Popen([str(executable.resolve()), "--gui-smoke-test"],
                               creationflags=subprocess.CREATE_NO_WINDOW)
    observed = None
    try:
        while process.poll() is None:
            if time.monotonic() - started > timeout_seconds:
                raise RuntimeError(f"GUI smoke exceeded {timeout_seconds}s; visible window: {observed}")

            def inspect(hwnd, _):
                nonlocal observed
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if (pid == process.pid and win32gui.IsWindowVisible(hwnd)
                        and win32gui.GetWindowText(hwnd) == "Mikan Pet"):
                    rect = win32gui.GetWindowRect(hwnd)
                    if rect[2] > rect[0] and rect[3] > rect[1]:
                        observed = {"hwnd": hwnd, "pid": pid, "title": "Mikan Pet",
                                    "visible": True, "rect": rect,
                                    "class": win32gui.GetClassName(hwnd)}

            win32gui.EnumWindows(inspect, None)
            time.sleep(0.025)
        exit_code = process.wait(timeout=1)
        if exit_code != 0 or observed is None:
            raise RuntimeError(f"GUI smoke failed: exit={exit_code}, visible window={observed}")
        return {"executable": str(executable.resolve()), "window": observed,
                "exit_code": exit_code, "elapsed_seconds": round(time.monotonic() - started, 3)}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    print(json.dumps(verify_gui_smoke(Path(sys.argv[1]))))
