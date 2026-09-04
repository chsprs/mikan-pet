import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NS = {
    "asm": "urn:schemas-microsoft-com:asm.v1",
    "asmv3": "urn:schemas-microsoft-com:asm.v3",
    "win2005": "http://schemas.microsoft.com/SMI/2005/WindowsSettings",
    "win2016": "http://schemas.microsoft.com/SMI/2016/WindowsSettings",
}


def _find_iscc() -> Path | None:
    candidates = [
        shutil.which("ISCC.exe"),
        Path(os.environ.get("ProgramFiles", r"C:\\Program Files")) / "Inno Setup 7" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 7" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


class PackagingContractTests(unittest.TestCase):
    def test_manifest_declares_as_invoker_per_monitor_dpi(self) -> None:
        root = ElementTree.parse(ROOT / "packaging" / "MikanPet.manifest").getroot()
        execution = root.find(".//asmv3:requestedExecutionLevel", MANIFEST_NS)
        self.assertIsNotNone(execution)
        self.assertEqual({"level": "asInvoker", "uiAccess": "false"}, execution.attrib)
        self.assertEqual(
            "true/pm",
            root.findtext(".//win2005:dpiAware", namespaces=MANIFEST_NS),
        )
        self.assertEqual(
            "PerMonitorV2,PerMonitor",
            root.findtext(".//win2016:dpiAwareness", namespaces=MANIFEST_NS),
        )

    def test_icon_generator_creates_transparent_multiresolution_ico(self) -> None:
        from scripts.generate_icon import generate_icon

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "MikanPet.ico"
            generate_icon(output)
            self.assertTrue(output.is_file())
            with Image.open(output) as icon:
                self.assertEqual({(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}, set(icon.ico.sizes()))
                icon.size = (32, 32)
                rgba = icon.convert("RGBA")
                self.assertEqual((0, 0, 0, 0), rgba.getpixel((0, 0)))
                self.assertGreater(sum(pixel[3] > 0 for pixel in rgba.get_flattened_data()), 0)

    def test_inno_script_compiles_to_a_temp_isolated_smoke_installer(self) -> None:
        iscc = _find_iscc()
        if iscc is None:
            self.skipTest("ISCC.exe is not installed")
        if not (ROOT / "dist" / "MikanPet" / "MikanPet.exe").is_file():
            self.skipTest("MikanPet package input is not built yet")
        with tempfile.TemporaryDirectory(prefix="mikan-pet-inno-") as directory:
            output_dir = Path(directory) / str(uuid.uuid4())
            output_dir.mkdir()
            app_id = "{{" + str(uuid.uuid4()).upper() + "}"
            mutex = "Local\\MikanPetSmoke" + uuid.uuid4().hex
            output_name = "MikanPet-smoke-" + uuid.uuid4().hex
            result = subprocess.run(
                [
                    str(iscc), "/Qp", f"/DMyAppId={app_id}",
                    f"/DMyAppMutex={mutex}", f"/DMyOutputBaseFilename={output_name}",
                    "/DMySmokeBuild=1", f"/O{output_dir}",
                    str(ROOT / "installer" / "MikanPet.iss"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            installer = output_dir / f"{output_name}.exe"
            self.assertTrue(installer.is_file())
            self.assertGreater(installer.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
