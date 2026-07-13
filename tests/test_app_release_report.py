from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_store_versions import ANDROID_HEADER, STORE_HEADER  # noqa: E402
from generate_app_release_report import generate_app_release_report  # noqa: E402
from prepare_app_release_rows import CONFIG_HEADER  # noqa: E402
from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER  # noqa: E402
from validate_app_releases import RELEASE_HEADER  # noqa: E402


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class AppReleaseReportTest(unittest.TestCase):
    def test_generates_status_report_with_next_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            app_repo = root / "vaultxt"
            app_repo.mkdir()
            (app_repo / "pubspec.yaml").write_text("name: vaultxt\nversion: 1.2.4+10\n", encoding="utf-8")
            write_csv(
                store,
                STORE_HEADER,
                [
                    {
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "platform": "ios",
                        "store_url": "https://apps.apple.com/app/id6760122045",
                        "store_app_id": "6760122045",
                        "store_package": "",
                        "version": "1.2.3",
                        "last_updated": "2026-07-12T01:30:00Z",
                        "release_notes": "Improved scrolling.",
                        "checked_at": "2026-07-12T09:00:00+09:00",
                        "status": "updated",
                        "notes": "",
                    },
                    {
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "platform": "android",
                        "store_url": "https://play.google.com/store/apps/details?id=com.onnellab.vaultxt",
                        "store_app_id": "",
                        "store_package": "com.onnellab.vaultxt",
                        "version": "",
                        "last_updated": "",
                        "release_notes": "",
                        "checked_at": "2026-07-12T09:00:00+09:00",
                        "status": "manual_check",
                        "notes": "Google Play manual check.",
                    },
                ],
            )
            planned = {field: "" for field in RELEASE_HEADER}
            planned.update(
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
                    "summary": "VaultXT 1.2.3 update.",
                    "changes": "Improved scrolling.",
                    "compatibility": "ios public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            write_csv(releases, RELEASE_HEADER, [planned])
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])
            write_csv(
                config,
                CONFIG_HEADER,
                [
                    {
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "repository": "onnellab/vaultxt",
                        "artifact_pattern": "generated/releases/vaultxt/{version}/{platform}/*-release.*",
                        "notes": "",
                    }
                ],
            )
            write_csv(
                local_repos,
                LOCAL_REPOSITORIES_HEADER,
                [
                    {
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "repository_name": "vaultxt",
                        "path": app_repo.as_posix(),
                        "pubspec_path": "pubspec.yaml",
                        "source_priority": "primary",
                        "notes": "",
                    }
                ],
            )

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repos,
                output,
                publications,
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertIn("# App Release Status", text)
            self.assertIn("Check Google Play update manually", text)
            self.assertIn("Add release artifact and checksum", text)
            self.assertIn("Publication gate", text)
            self.assertIn("Store notes", text)
            self.assertIn("Improved scrolling.", text)
            self.assertIn("Waiting for artifact and public approval", text)
            self.assertIn("local_ahead", text)
            self.assertEqual(output.read_text(encoding="utf-8"), text)

    def test_report_marks_artifact_without_public_approval_as_private_or_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            app_repo = root / "vaultxt"
            app_repo.mkdir()
            (app_repo / "pubspec.yaml").write_text("name: vaultxt\nversion: 1.2.3+10\n", encoding="utf-8")
            write_csv(store, STORE_HEADER, [])
            planned = {field: "" for field in RELEASE_HEADER}
            planned.update(
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
                    "artifact_path": "generated/releases/vaultxt/1.2.3/ios/vaultxt-ios-1.2.3-release.ipa",
                    "checksum_sha256": "0" * 64,
                    "status": "planned",
                    "release_date": "2026-07-12",
                    "release_title": "VaultXT v1.2.3",
                    "summary": "VaultXT 1.2.3 update.",
                    "changes": "Improved scrolling.",
                    "compatibility": "ios public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            write_csv(releases, RELEASE_HEADER, [planned])
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])
            write_csv(
                config,
                CONFIG_HEADER,
                [
                    {
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "repository": "onnellab/vaultxt",
                        "artifact_pattern": "generated/releases/vaultxt/{version}/{platform}/*-release.*",
                        "notes": "",
                    }
                ],
            )
            write_csv(
                local_repos,
                LOCAL_REPOSITORIES_HEADER,
                [
                    {
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "repository_name": "vaultxt",
                        "path": app_repo.as_posix(),
                        "pubspec_path": "pubspec.yaml",
                        "source_priority": "primary",
                        "notes": "",
                    }
                ],
            )

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repos,
                output,
                publications,
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertIn("Private test or approval pending", text)
            self.assertIn("Approve public release or keep as private test", text)

    def test_report_marks_notes_only_release_as_waiting_for_notes_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            write_csv(store, STORE_HEADER, [])
            planned = {field: "" for field in RELEASE_HEADER}
            planned.update(
                {
                    "release_id": "REL-0009",
                    "app_id": "APP-0003",
                    "app_slug": "vaultxt",
                    "app_name": "VaultXT",
                    "repository": "onnellab/vaultxt",
                    "tag": "v1.2.3",
                    "version": "1.2.3",
                    "platform": "android",
                    "build_type": "release",
                    "release_type": "notes_only",
                    "status": "planned",
                    "release_date": "2026-07-12",
                    "release_title": "VaultXT v1.2.3",
                    "summary": "VaultXT 1.2.3 update.",
                    "changes": "Improved scrolling.",
                    "compatibility": "android public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            write_csv(releases, RELEASE_HEADER, [planned])
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])
            write_csv(config, CONFIG_HEADER, [])
            write_csv(local_repos, LOCAL_REPOSITORIES_HEADER, [])

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repos,
                output,
                publications,
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertIn("Waiting for public notes approval", text)
            self.assertIn("Approve public notes-only release", text)

    def test_report_uses_android_local_metadata_when_local_repo_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            android_versions = root / "android_store_versions.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            write_csv(
                store,
                STORE_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "app_name": "TagWeaver",
                        "platform": "android",
                        "store_url": "https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2",
                        "store_app_id": "",
                        "store_package": "com.onnellab.tagweaver2",
                        "version": "2.1.3",
                        "last_updated": "2026-07-12",
                        "release_notes": "Local Flutter build metadata version.",
                        "checked_at": "2026-07-13T09:00:00+09:00",
                        "status": "unchanged",
                        "notes": "",
                    }
                ],
            )
            write_csv(releases, RELEASE_HEADER, [])
            write_csv(
                config,
                CONFIG_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "repository": "onnellab/tagweaver",
                        "artifact_pattern": "generated/releases/tagweaver/{version}/{platform}/*-release.*",
                        "notes": "",
                    }
                ],
            )
            write_csv(local_repos, LOCAL_REPOSITORIES_HEADER, [])
            write_csv(
                android_versions,
                ANDROID_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "package": "com.onnellab.tagweaver2",
                        "version": "2.1.3",
                        "last_updated": "2026-07-12",
                        "release_notes": "Local Flutter build metadata version.",
                        "source": "local_build_metadata",
                        "notes": "Imported from CI snapshot.",
                    }
                ],
            )
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repos,
                output,
                publications,
                now=datetime.fromisoformat("2026-07-13T09:00:00+09:00"),
                android_versions_path=android_versions,
            )

            self.assertIn("| TagWeaver | android | 2.1.3 | 2.1.3 | same | unchanged | - | onnellab/tagweaver | No action |", text)

    def test_unchanged_store_with_local_ahead_is_review_not_store_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            app_repo = root / "segra"
            app_repo.mkdir()
            (app_repo / "pubspec.yaml").write_text("name: segra\nversion: 1.0.2+10\n", encoding="utf-8")
            write_csv(
                store,
                STORE_HEADER,
                [
                    {
                        "app_id": "APP-0004",
                        "app_slug": "segra",
                        "app_name": "Segra",
                        "platform": "ios",
                        "store_url": "https://apps.apple.com/app/id6779433972",
                        "store_app_id": "6779433972",
                        "store_package": "",
                        "version": "1.0.1",
                        "last_updated": "2026-07-10T18:44:50Z",
                        "release_notes": "Bug fixes.",
                        "checked_at": "2026-07-13T09:00:00+09:00",
                        "status": "unchanged",
                        "notes": "",
                    }
                ],
            )
            write_csv(releases, RELEASE_HEADER, [])
            write_csv(
                config,
                CONFIG_HEADER,
                [
                    {
                        "app_id": "APP-0004",
                        "app_slug": "segra",
                        "repository": "onnellab/segra",
                        "artifact_pattern": "generated/releases/segra/{version}/{platform}/*-release.*",
                        "notes": "",
                    }
                ],
            )
            write_csv(
                local_repos,
                LOCAL_REPOSITORIES_HEADER,
                [
                    {
                        "app_id": "APP-0004",
                        "app_slug": "segra",
                        "repository_name": "segra",
                        "path": app_repo.as_posix(),
                        "pubspec_path": "pubspec.yaml",
                        "source_priority": "primary",
                        "notes": "",
                    }
                ],
            )
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repos,
                output,
                publications,
                now=datetime.fromisoformat("2026-07-13T09:00:00+09:00"),
            )

            self.assertIn("local_ahead", text)
            self.assertIn("Review unpublished local build", text)
            self.assertNotIn("Prepare store release", text)


if __name__ == "__main__":
    unittest.main()
