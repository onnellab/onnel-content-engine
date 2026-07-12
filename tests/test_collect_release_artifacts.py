from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_release_artifacts import CollectReleaseArtifactError, collect_release_artifacts  # noqa: E402
from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER  # noqa: E402
from validate_app_releases import RELEASE_HEADER  # noqa: E402


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def planned_release(platform: str = "android") -> dict[str, str]:
    row = {field: "" for field in RELEASE_HEADER}
    row.update(
        {
            "release_id": "REL-0001",
            "app_id": "APP-0003",
            "app_slug": "vaultxt",
            "app_name": "VaultXT",
            "repository": "onnellab/vaultxt",
            "tag": "v1.2.3",
            "version": "1.2.3",
            "platform": platform,
            "build_type": "release",
            "status": "planned",
            "release_date": "2026-07-12",
            "release_title": "VaultXT v1.2.3",
            "summary": "VaultXT 1.2.3 local build metadata is ahead.",
            "changes": "Local build metadata version 1.2.3 is ahead.",
            "compatibility": f"{platform} public release.",
            "upgrade_notes": "No special upgrade steps documented yet.",
        }
    )
    return row


class CollectReleaseArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(lambda: shutil.rmtree(ROOT / "generated" / "releases" / "vaultxt", ignore_errors=True))

    def write_repo_config(self, path: Path, repo: Path) -> None:
        write_csv(
            path,
            LOCAL_REPOSITORIES_HEADER,
            [
                {
                    "app_id": "APP-0003",
                    "app_slug": "vaultxt",
                    "repository_name": "vaultxt",
                    "path": repo.as_posix(),
                    "pubspec_path": "pubspec.yaml",
                    "source_priority": "primary",
                    "notes": "",
                }
            ],
        )

    def test_collects_single_android_release_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "vaultxt"
            artifact = repo / "build" / "app" / "outputs" / "bundle" / "release" / "app-release.aab"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"release")
            releases = root / "app_releases.csv"
            repositories = root / "local_repositories.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            self.write_repo_config(repositories, repo)

            copied = collect_release_artifacts(releases, repositories)

            self.assertEqual(len(copied), 1)
            self.assertTrue(copied[0][1].exists())
            self.assertEqual(copied[0][1].read_bytes(), b"release")

    def test_ios_without_local_artifact_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "vaultxt"
            repo.mkdir()
            releases = root / "app_releases.csv"
            repositories = root / "local_repositories.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release("ios")])
            self.write_repo_config(repositories, repo)

            self.assertEqual(collect_release_artifacts(releases, repositories), [])

    def test_multiple_artifacts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "vaultxt"
            base = repo / "build" / "app" / "outputs" / "bundle" / "release"
            base.mkdir(parents=True)
            (base / "app-release.aab").write_bytes(b"one")
            (base / "other-release.aab").write_bytes(b"two")
            releases = root / "app_releases.csv"
            repositories = root / "local_repositories.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            self.write_repo_config(repositories, repo)

            with self.assertRaises(CollectReleaseArtifactError):
                collect_release_artifacts(releases, repositories)


if __name__ == "__main__":
    unittest.main()
