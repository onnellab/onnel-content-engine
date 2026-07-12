from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_store_versions import STORE_HEADER  # noqa: E402
from prepare_app_release_rows import prepare_app_release_rows  # noqa: E402
from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER  # noqa: E402
from validate_app_releases import RELEASE_HEADER, validate_app_releases  # noqa: E402


def write_store_versions(path: Path, status: str = "updated", version: str = "1.2.3") -> None:
    row = {
        "app_id": "APP-0003",
        "app_slug": "vaultxt",
        "app_name": "VaultXT",
        "platform": "ios",
        "store_url": "https://apps.apple.com/app/id6760122045",
        "store_app_id": "6760122045",
        "store_package": "",
        "version": version,
        "last_updated": "2026-07-12T01:30:00Z",
        "release_notes": "Improved large-file scrolling.",
        "checked_at": "2026-07-12T09:00:00+09:00",
        "status": status,
        "notes": "",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STORE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def write_releases(path: Path, rows: list[dict[str, str]] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows or [])


def write_local_repositories(path: Path, app_path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOCAL_REPOSITORIES_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "app_id": "APP-0003",
                "app_slug": "vaultxt",
                "repository_name": "vaultxt",
                "path": app_path.as_posix(),
                "pubspec_path": "pubspec.yaml",
                "source_priority": "primary",
                "notes": "",
            }
        )


class PrepareAppReleaseRowsTest(unittest.TestCase):
    def test_updated_store_snapshot_creates_planned_release_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store_versions = Path(temp) / "store_versions.csv"
            releases = Path(temp) / "app_releases.csv"
            write_store_versions(store_versions)
            write_releases(releases)

            additions = prepare_app_release_rows(
                store_versions,
                releases,
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertEqual(len(additions), 1)
            row = additions[0]
            self.assertEqual(row["release_id"], "REL-0001")
            self.assertEqual(row["repository"], "onnellab/vaultxt")
            self.assertEqual(row["tag"], "v1.2.3")
            self.assertEqual(row["status"], "planned")
            self.assertEqual(row["artifact_path"], "")
            self.assertEqual(validate_app_releases(releases), 1)

    def test_local_ahead_snapshot_creates_planned_release_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store_versions = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            local_repositories = root / "local_repositories.csv"
            app = root / "vaultxt"
            app.mkdir()
            (app / "pubspec.yaml").write_text("name: vaultxt\nversion: 1.2.4+10\n", encoding="utf-8")
            write_store_versions(store_versions, status="unchanged", version="1.2.3")
            write_releases(releases)
            write_local_repositories(local_repositories, app)

            additions = prepare_app_release_rows(
                store_versions,
                releases,
                local_repositories_path=local_repositories,
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertEqual(len(additions), 1)
            row = additions[0]
            self.assertEqual(row["tag"], "v1.2.4")
            self.assertEqual(row["version"], "1.2.4")
            self.assertIn("local build metadata", row["notes"])
            self.assertIn("Store version: 1.2.3", row["notes"])
            self.assertEqual(validate_app_releases(releases), 1)

    def test_unchanged_snapshot_does_not_create_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store_versions = Path(temp) / "store_versions.csv"
            releases = Path(temp) / "app_releases.csv"
            write_store_versions(store_versions, status="unchanged")
            write_releases(releases)

            additions = prepare_app_release_rows(store_versions, releases)

            self.assertEqual(additions, [])
            self.assertEqual(validate_app_releases(releases), 0)

    def test_duplicate_app_platform_version_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store_versions = Path(temp) / "store_versions.csv"
            releases = Path(temp) / "app_releases.csv"
            write_store_versions(store_versions)
            existing = {field: "" for field in RELEASE_HEADER}
            existing.update(
                {
                    "release_id": "REL-0001",
                    "app_id": "APP-0003",
                    "app_slug": "vaultxt",
                    "app_name": "VaultXT",
                    "repository": "onnellab/vaultxt",
                    "tag": "v1.2.3",
                    "version": "1.2.3",
                    "platform": "ios",
                    "build_type": "release",
                    "status": "planned",
                    "release_date": "2026-07-12",
                    "release_title": "VaultXT v1.2.3",
                    "summary": "VaultXT 1.2.3 public store update detected.",
                    "changes": "Improved large-file scrolling.",
                    "compatibility": "ios public release.",
                }
            )
            write_releases(releases, [existing])

            additions = prepare_app_release_rows(store_versions, releases)

            self.assertEqual(additions, [])
            self.assertEqual(validate_app_releases(releases), 1)

    def test_duplicate_repository_tag_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store_versions = Path(temp) / "store_versions.csv"
            releases = Path(temp) / "app_releases.csv"
            write_store_versions(store_versions)
            existing = {field: "" for field in RELEASE_HEADER}
            existing.update(
                {
                    "release_id": "REL-0001",
                    "app_id": "APP-0003",
                    "app_slug": "vaultxt",
                    "app_name": "VaultXT",
                    "repository": "onnellab/vaultxt",
                    "tag": "v1.2.3",
                    "version": "1.2.3",
                    "platform": "android",
                    "build_type": "release",
                    "status": "planned",
                    "release_date": "2026-07-12",
                    "release_title": "VaultXT v1.2.3",
                    "summary": "VaultXT 1.2.3 public store update detected.",
                    "changes": "Improved large-file scrolling.",
                    "compatibility": "android public release.",
                }
            )
            write_releases(releases, [existing])

            additions = prepare_app_release_rows(store_versions, releases)

            self.assertEqual(additions, [])
            self.assertEqual(validate_app_releases(releases), 1)


if __name__ == "__main__":
    unittest.main()
