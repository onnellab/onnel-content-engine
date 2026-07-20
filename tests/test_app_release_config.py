from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_app_release_rows import CONFIG_HEADER, CONFIG_PATH  # noqa: E402
from validate_app_release_config import AppReleaseConfigError, validate_app_release_config  # noqa: E402


def read_config_rows() -> list[dict[str, str]]:
    with CONFIG_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_config(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONFIG_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class AppReleaseConfigTest(unittest.TestCase):
    def test_current_release_config_is_valid(self) -> None:
        configured_count = len(read_config_rows())
        self.assertGreater(configured_count, 0)
        self.assertEqual(validate_app_release_config(), configured_count)

    def test_repository_must_use_owner_name(self) -> None:
        rows = read_config_rows()
        rows[0]["repository"] = "quivra"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_release_config.csv"
            write_config(path, rows)

            with self.assertRaises(AppReleaseConfigError):
                validate_app_release_config(path)

    def test_pattern_must_include_version_and_platform(self) -> None:
        rows = read_config_rows()
        rows[0]["artifact_pattern"] = "generated/releases/quivra/*-release.*"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_release_config.csv"
            write_config(path, rows)

            with self.assertRaises(AppReleaseConfigError):
                validate_app_release_config(path)

    def test_slug_must_match_app_registry(self) -> None:
        rows = read_config_rows()
        rows[0]["app_slug"] = "wrong"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_release_config.csv"
            write_config(path, rows)

            with self.assertRaises(AppReleaseConfigError):
                validate_app_release_config(path)


if __name__ == "__main__":
    unittest.main()
