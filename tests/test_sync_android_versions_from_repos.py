from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_store_versions import ANDROID_HEADER  # noqa: E402
from sync_android_versions_from_repos import (  # noqa: E402
    LOCAL_REPOSITORIES_HEADER,
    AndroidRepoSyncError,
    sync_android_versions_from_repos,
)
from validate_android_store_versions import validate_android_store_versions  # noqa: E402


def write_repositories(path: Path, app_path: Path) -> None:
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


class SyncAndroidVersionsFromReposTest(unittest.TestCase):
    def test_syncs_pubspec_versions_to_android_store_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "vaultxt"
            app.mkdir()
            (app / "pubspec.yaml").write_text("name: vaultxt\nversion: 1.2.3+45\n", encoding="utf-8")
            repos = root / "local_repositories.csv"
            output = root / "android_store_versions.csv"
            write_repositories(repos, app)

            rows = sync_android_versions_from_repos(repos, output, today="2026-07-12")

            self.assertEqual(rows[0]["version"], "1.2.3")
            self.assertEqual(rows[0]["source"], "local_build_metadata")
            self.assertIn("1.2.3+45", rows[0]["notes"])
            self.assertEqual(validate_android_store_versions(output), 1)
            with output.open("r", encoding="utf-8", newline="") as handle:
                self.assertEqual(csv.DictReader(handle).fieldnames, ANDROID_HEADER)

    def test_dry_run_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "vaultxt"
            app.mkdir()
            (app / "pubspec.yaml").write_text("name: vaultxt\nversion: 1.2.3+45\n", encoding="utf-8")
            repos = root / "local_repositories.csv"
            output = root / "android_store_versions.csv"
            write_repositories(repos, app)

            rows = sync_android_versions_from_repos(repos, output, today="2026-07-12", dry_run=True)

            self.assertEqual(len(rows), 1)
            self.assertFalse(output.exists())

    def test_missing_local_repo_falls_back_to_github_main(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "missing-vaultxt"
            repos = root / "local_repositories.csv"
            output = root / "android_store_versions.csv"
            write_repositories(repos, app)

            with patch(
                "sync_android_versions_from_repos.app_release_repository_index",
                return_value={"APP-0003": "onnellab/onnellab-text"},
            ), patch("sync_android_versions_from_repos.github_token", return_value="token"), patch(
                "sync_android_versions_from_repos.github_file_text",
                return_value="name: vaultxt\nversion: 2.0.0+65\n",
            ):
                rows = sync_android_versions_from_repos(repos, output, today="2026-09-18")

            self.assertEqual(rows[0]["version"], "2.0.0")
            self.assertIn("github:onnellab/onnellab-text/pubspec.yaml", rows[0]["notes"])

    def test_missing_pubspec_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "vaultxt"
            app.mkdir()
            repos = root / "local_repositories.csv"
            output = root / "android_store_versions.csv"
            write_repositories(repos, app)

            with self.assertRaises(AndroidRepoSyncError):
                sync_android_versions_from_repos(repos, output)


if __name__ == "__main__":
    unittest.main()
