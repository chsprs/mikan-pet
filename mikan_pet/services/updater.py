"""In-place auto-update service using GitHub Releases."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError

DEFAULT_GITHUB_REPO = os.getenv("MIKAN_PET_REPO", "owner/mikan-pet")


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    zip_url: str | None
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


def fetch_latest_release(repo: str, timeout: float = 5.0) -> ReleaseInfo | None:
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

    zip_url: str | None = None
    assets = data.get("assets", [])
    # Find portable zip asset
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith("portable-x64.zip"):
            zip_url = asset.get("browser_download_url")
            break
    if zip_url is None:
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".zip"):
                zip_url = asset.get("browser_download_url")
                break

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        zip_url=zip_url,
        html_url=html_url,
        release_notes=body,
    )


def download_and_extract_update(zip_url: str, target_dir: Path, timeout: float = 30.0) -> None:
    """Download portable release zip and extract into target directory."""
    import zipfile

    target_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(zip_url, headers={"User-Agent": "MikanPet-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        zip_bytes = resp.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(target_dir)


def launch_in_place_updater(
    staging_dir: Path,
    install_dir: Path,
    target_exe_name: str = "MikanPet.exe",
) -> Path:
    """Write and trigger detached batch updater script to replace binaries and relaunch."""
    temp_dir = Path(tempfile.gettempdir())
    script_path = temp_dir / "_mikan_update.cmd"

    script_content = (
        "@echo off\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        f'taskkill /F /PID {os.getpid()} >nul 2>&1\r\n'
        f'xcopy "{staging_dir}\\*" "{install_dir}\\" /E /Y /Q >nul\r\n'
        f'rmdir /S /Q "{staging_dir}"\r\n'
        f'start "" "{install_dir / target_exe_name}"\r\n'
        "(goto) 2>nul & del \"%~f0\"\r\n"
    )
    script_path.write_text(script_content, encoding="ascii")

    creation_flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        creationflags=creation_flags,
        close_fds=True,
    )
    return script_path
