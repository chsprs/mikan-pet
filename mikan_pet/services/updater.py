"""In-place auto-update service using GitHub Releases."""

from __future__ import annotations

import io
import hashlib
import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError

DEFAULT_GITHUB_REPO = os.getenv("MIKAN_PET_REPO", "chsprs/mikan-pet")


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    zip_url: str | None
    zip_sha256: str | None
    html_url: str
    release_notes: str


def parse_version(v: str) -> tuple[int, ...]:
    """Convert version string into comparable integer tuple (e.g. 'v0.2.1' -> (0, 2, 1))."""
    clean = v.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        digits = "".join(c for c in p if c.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def is_newer_version(current: str, candidate: str) -> bool:
    """Return True if candidate version is strictly newer than current version."""
    return parse_version(candidate) > parse_version(current)


def _release_architecture(machine: str) -> str:
    return "arm64" if machine.strip().lower() in {"arm64", "aarch64"} else "x64"


def _asset_sha256(asset: dict) -> str | None:
    digest = str(asset.get("digest", ""))
    prefix = "sha256:"
    value = digest[len(prefix):].lower() if digest.lower().startswith(prefix) else ""
    if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
        return value
    return None


def fetch_latest_release(
    repo: str,
    timeout: float = 5.0,
    *,
    machine: str | None = None,
) -> ReleaseInfo | None:
    """Query GitHub API for latest release info. Returns None on failure."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MikanPet-Updater",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None

    tag_name = data.get("tag_name", "")
    version = tag_name.lstrip("vV")
    html_url = data.get("html_url", "")
    body = data.get("body", "") or ""

    architecture = _release_architecture(machine or platform.machine())
    expected_name = f"mikanpet-portable-{architecture}.zip"
    zip_url: str | None = None
    zip_sha256: str | None = None
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "").lower()
        if name == expected_name:
            zip_url = asset.get("browser_download_url")
            zip_sha256 = _asset_sha256(asset)
            break

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        zip_url=zip_url,
        zip_sha256=zip_sha256,
        html_url=html_url,
        release_notes=body,
    )


def download_and_extract_update(
    zip_url: str,
    target_dir: Path,
    expected_sha256: str,
    timeout: float = 30.0,
) -> None:
    """Download, authenticate, and safely extract a portable release archive."""
    import zipfile

    expected_sha256 = expected_sha256.strip().lower()
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("invalid SHA-256 checksum for update")
    req = urllib.request.Request(zip_url, headers={"User-Agent": "MikanPet-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        zip_bytes = resp.read()
    actual_sha256 = hashlib.sha256(zip_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("update checksum verification failed")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        target_root = target_dir.resolve()
        for member in zf.infolist():
            destination = (target_root / member.filename).resolve()
            if not destination.is_relative_to(target_root):
                raise ValueError(f"update archive contains unsafe path: {member.filename}")
            unix_mode = (member.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(unix_mode):
                raise ValueError(f"update archive contains unsafe symlink: {member.filename}")
        target_dir.mkdir(parents=True, exist_ok=True)
        zf.extractall(target_dir)


def is_directory_writable(directory: Path) -> bool:
    """Check if the directory is writable by the current process without admin elevation."""
    try:
        test_file = directory / f".mikan_write_test_{os.getpid()}"
        test_file.touch(exist_ok=False)
        test_file.unlink(missing_ok=True)
        return True
    except (OSError, PermissionError):
        return False


def launch_in_place_updater(
    staging_dir: Path,
    install_dir: Path,
    target_exe_name: str = "MikanPet.exe",
) -> Path:
    """Write and trigger detached batch updater script to replace binaries and relaunch."""
    temp_dir = Path(tempfile.gettempdir())
    script_path = temp_dir / "_mikan_update.cmd"

    target_exe = install_dir / target_exe_name
    staging_str = str(staging_dir).rstrip("\\/")
    install_str = str(install_dir).rstrip("\\/")
    target_exe_str = str(target_exe).rstrip("\\/")
    script_content = (
        "@echo off\r\n"
        "setlocal enabledelayedexpansion\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        f'taskkill /F /PID {os.getpid()} >nul 2>&1\r\n'
        "timeout /t 1 /nobreak >nul\r\n"
        "set RETRY=0\r\n"
        ":copy_loop\r\n"
        f'xcopy "{staging_str}\\*" "{install_str}" /E /I /Y /Q /H /R >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "    set /a RETRY+=1\r\n"
        "    if !RETRY! leq 10 (\r\n"
        "        timeout /t 1 /nobreak >nul\r\n"
        "        goto copy_loop\r\n"
        "    )\r\n"
        ")\r\n"
        f'rmdir /S /Q "{staging_str}" >nul 2>&1\r\n'
        f'start "" /D "{install_str}" "{target_exe_str}"\r\n'
        "(goto) 2>nul & del \"%~f0\"\r\n"
    )
    script_path.write_text(script_content, encoding="ascii")

    writable = is_directory_writable(install_dir)
    if not writable and sys.platform == "win32":
        # Request UAC elevation to copy into protected directories
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "cmd.exe",
                f'/c "{script_path}"',
                None,
                0,  # SW_HIDE
            )
            return script_path
        except Exception:
            pass

    creation_flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        creationflags=creation_flags,
        close_fds=True,
    )
    return script_path
