"""In-place auto-update service using GitHub Releases."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError

DEFAULT_GITHUB_REPO = os.getenv("MIKAN_PET_REPO", "chsprs/mikan-pet")


class ChecksumMismatchError(ValueError):
    """The downloaded installer does not match the digest published by GitHub."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    installer_url: str | None
    installer_sha256: str | None
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


def release_notes_excerpt(notes: str, limit: int = 300) -> str:
    """Trim release notes for a dialog, marking only text that was actually cut."""
    text = notes.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _with_notes(message: str, release: ReleaseInfo) -> str:
    excerpt = release_notes_excerpt(release.release_notes)
    return f"{message}\n\nCatatan rilis:\n{excerpt}" if excerpt else message


def up_to_date_message(current: str, release: ReleaseInfo) -> str:
    """Explain why no update is offered, including a local build newer than GitHub."""
    if parse_version(current) > parse_version(release.version):
        return (
            f"Versi terpasang (v{current}) lebih baru daripada rilis terbaru "
            f"di GitHub (v{release.version}).\n\nTidak ada pembaruan untuk dipasang."
        )
    return (
        "Mikan Pet sudah versi terbaru.\n\n"
        f"Versi terpasang: v{current}\n"
        f"Rilis terbaru di GitHub: v{release.version}"
    )


def update_available_message(current: str, release: ReleaseInfo) -> str:
    """Ask before downloading; describe what happens to the running pet."""
    message = (
        "Versi baru Mikan Pet tersedia.\n\n"
        f"Versi terpasang: v{current}\n"
        f"Versi baru: v{release.version}"
    )
    if release.installer_url:
        question = (
            "Unduh dan pasang sekarang? Installer akan terbuka setelah unduhan "
            "selesai, lalu Mikan Pet ditutup. Pengaturan Anda tetap tersimpan."
        )
    else:
        question = (
            "Installer tidak ditemukan di rilis ini. Buka halaman rilis "
            "di browser untuk memperbarui secara manual?"
        )
    return f"{_with_notes(message, release)}\n\n{question}"


def update_failure_message(error: Exception) -> str:
    """Describe a failed download without leaking English exception text for known cases."""
    if isinstance(error, ChecksumMismatchError):
        return (
            "Installer yang diunduh tidak cocok dengan checksum SHA-256 dari GitHub, "
            "jadi tidak dijalankan.\n\nCoba lagi nanti."
        )
    return f"Installer pembaruan gagal diunduh.\n\nDetail: {error}"


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

    expected_name = "mikanpet-setup-x64.exe"
    installer_url: str | None = None
    installer_sha256: str | None = None
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "").lower()
        if name == expected_name:
            installer_url = asset.get("browser_download_url")
            installer_sha256 = _asset_sha256(asset)
            break

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        installer_url=installer_url,
        installer_sha256=installer_sha256,
        html_url=html_url,
        release_notes=body,
    )


def download_update_installer(
    installer_url: str,
    target_file: Path,
    expected_sha256: str | None = None,
    timeout: float = 60.0,
) -> None:
    """Download and authenticate the update installer executable."""
    if expected_sha256 is not None:
        expected_sha256 = expected_sha256.strip().lower()
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
            raise ValueError("invalid SHA-256 checksum for update")

    req = urllib.request.Request(installer_url, headers={"User-Agent": "MikanPet-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()

    if expected_sha256 is not None:
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ChecksumMismatchError("update checksum verification failed")

    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(data)


def launch_installer_updater(installer_path: Path) -> None:
    """Launch the installer in silent or normal mode and close current application."""
    if sys.platform != "win32":
        return

    # Launch installer with elevated privileges if needed or standard ShellExecute
    try:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "open",
            str(installer_path),
            None,
            None,
            1,  # SW_SHOWNORMAL
        )
    except Exception:
        subprocess.Popen(
            [str(installer_path)],
            close_fds=True,
        )
