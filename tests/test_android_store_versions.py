from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_store_versions import ANDROID_HEADER, ANDROID_VERSIONS_PATH  # noqa: E402
from validate_android_store_versions import AndroidStoreVersionError, validate_android_store_versions  # noqa: E402


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANDROID_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def valid_row() -> dict[str, str]:
    return {
        "app_id": "APP-0003",
        "app_slug": "vaultxt",
        "package": "com.onnellab.vaultxt",
        "version": "1.2.3",
        "last_updated": "2026-07-12",
        "release_notes": "Android release.",
        "source": "manual_entry",
        "notes": "",
    }


class AndroidStoreVersionsTest(unittest.TestCase):
    def test_current_android_store_versions_file_is_valid(self) -> None:
        self.assertEqual(validate_android_store_versions(ANDROID_VERSIONS_PATH), 5)

    def test_valid_android_row_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "android_store_versions.csv"
            write_rows(path, [valid_row()])

            self.assertEqual(validate_android_store_versions(path), 1)

    def test_package_must_match_registry(self) -> None:
        row = valid_row()
        row["package"] = "com.example.wrong"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "android_store_versions.csv"
            write_rows(path, [row])

            with self.assertRaises(AndroidStoreVersionError):
                validate_android_store_versions(path)

    def test_source_must_be_supported(self) -> None:
        row = valid_row()
        row["source"] = "scraped"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "android_store_versions.csv"
            write_rows(path, [row])

            with self.assertRaises(AndroidStoreVersionError):
                validate_android_store_versions(path)


if __name__ == "__main__":
    unittest.main()
