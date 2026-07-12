from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_store_versions import ANDROID_HEADER  # noqa: E402
from import_android_store_versions import AndroidStoreImportError, import_android_store_versions  # noqa: E402
from validate_android_store_versions import validate_android_store_versions  # noqa: E402


def write_export(path: Path, rows: list[dict[str, str]]) -> None:
    header = ["Package name", "Version name", "Last updated", "Release notes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class ImportAndroidStoreVersionsTest(unittest.TestCase):
    def test_imports_play_console_style_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "play-console.csv"
            output = Path(temp) / "android_store_versions.csv"
            write_export(
                source,
                [
                    {
                        "Package name": "com.onnellab.vaultxt",
                        "Version name": "1.2.3",
                        "Last updated": "2026-07-12",
                        "Release notes": "Android release.",
                    }
                ],
            )

            rows = import_android_store_versions(source, output)

            self.assertEqual(rows[0]["app_id"], "APP-0003")
            self.assertEqual(rows[0]["app_slug"], "vaultxt")
            self.assertEqual(rows[0]["source"], "play_console_export")
            self.assertEqual(validate_android_store_versions(output), 1)

            with output.open("r", encoding="utf-8", newline="") as handle:
                self.assertEqual(csv.DictReader(handle).fieldnames, ANDROID_HEADER)

    def test_dry_run_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "play-console.csv"
            output = Path(temp) / "android_store_versions.csv"
            write_export(source, [{"Package name": "com.onnellab.vaultxt", "Version name": "1.2.3", "Last updated": "", "Release notes": ""}])

            rows = import_android_store_versions(source, output, dry_run=True)

            self.assertEqual(len(rows), 1)
            self.assertFalse(output.exists())

    def test_local_build_metadata_source_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "build-metadata.csv"
            output = Path(temp) / "android_store_versions.csv"
            write_export(source, [{"Package name": "com.onnellab.vaultxt", "Version name": "1.2.3", "Last updated": "", "Release notes": ""}])

            rows = import_android_store_versions(source, output, source="local_build_metadata")

            self.assertEqual(rows[0]["source"], "local_build_metadata")
            self.assertEqual(validate_android_store_versions(output), 1)

    def test_unknown_package_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "play-console.csv"
            output = Path(temp) / "android_store_versions.csv"
            write_export(source, [{"Package name": "com.example.unknown", "Version name": "1.2.3", "Last updated": "", "Release notes": ""}])

            with self.assertRaises(AndroidStoreImportError):
                import_android_store_versions(source, output)


if __name__ == "__main__":
    unittest.main()
