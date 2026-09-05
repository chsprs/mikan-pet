from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows-only installer verifier")
class VerifyInstallScriptTests(unittest.TestCase):
    def test_reports_outdated_version_from_installed_package_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install_dir = Path(directory)
            executable = install_dir / "MikanPet.exe"
            shutil.copy2(sys.executable, executable)
            (install_dir / "_internal").mkdir()
            (install_dir / "version.txt").write_text("0.0.1\n", encoding="ascii")

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts" / "verify_install.ps1"),
                    "-ExecutablePath",
                    str(executable),
                    "-LatestVersion",
                    "0.0.2",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Versi Terpasang : v0.0.1", result.stdout)
        self.assertIn("STATUS : BELUM SESUAI", result.stdout)


if __name__ == "__main__":
    unittest.main()
