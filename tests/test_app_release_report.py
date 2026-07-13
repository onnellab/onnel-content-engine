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
            self.assertIn("Release ready; approve public release or keep private", text)

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
            self.assertIn("Release ready; approve public notes-only release", text)

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
            self.assertIn("Store not updated; confirm public rollout", text)

    def test_completed_store_release_does_not_remain_candidate_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            write_csv(
                store,
                STORE_HEADER,
                [
                    {
                        "app_id": "APP-0005",
                        "app_slug": "clipnest",
                        "app_name": "ClipNest",
                        "platform": "ios",
                        "store_url": "https://apps.apple.com/app/id6779928552",
                        "store_app_id": "6779928552",
                        "store_package": "",
                        "version": "1.0.2",
                        "last_updated": "2026-07-13T03:53:22Z",
                        "release_notes": "Bug fixes.",
                        "checked_at": "2026-07-14T00:00:00+09:00",
                        "status": "updated",
                        "notes": "",
                    }
                ],
            )
            released = {field: "" for field in RELEASE_HEADER}
            released.update(
                {
                    "release_id": "REL-0005",
                    "app_id": "APP-0005",
                    "app_slug": "clipnest",
                    "app_name": "ClipNest",
                    "repository": "onnellab/clipnest",
                    "tag": "v1.0.2",
                    "version": "1.0.2",
                    "platform": "ios",
                    "build_type": "release",
                    "release_type": "notes_only",
                    "release_channel": "public",
                    "status": "released",
                    "release_url": "https://github.com/onnellab/clipnest/releases/tag/v1.0.2",
                    "release_date": "2026-07-13",
                    "release_title": "ClipNest v1.0.2",
                    "summary": "ClipNest 1.0.2 public iOS store update detected.",
                    "changes": "Improved keyboard editing handoff.",
                    "compatibility": "ios public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            write_csv(releases, RELEASE_HEADER, [released])
            write_csv(
                config,
                CONFIG_HEADER,
                [
                    {
                        "app_id": "APP-0005",
                        "app_slug": "clipnest",
                        "repository": "onnellab/clipnest",
                        "artifact_pattern": "generated/releases/clipnest/{version}/{platform}/*-release.*",
                        "notes": "",
                    }
                ],
            )
            write_csv(local_repos, LOCAL_REPOSITORIES_HEADER, [])
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repos,
                output,
                publications,
                now=datetime.fromisoformat("2026-07-14T00:00:00+09:00"),
            )

            self.assertIn("| ClipNest | ios | 1.0.2 | - | unknown | updated | released | onnellab/clipnest | No action |", text)
            self.assertNotIn("Create or verify release candidate", text)
            self.assertNotIn("Release ready; prepare store rollout", text)

    def test_completed_store_release_with_local_ahead_keeps_rollout_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            app_repo = root / "clipnest"
            app_repo.mkdir()
            (app_repo / "pubspec.yaml").write_text("name: clipnest\nversion: 1.0.4+12\n", encoding="utf-8")
            write_csv(
                store,
                STORE_HEADER,
                [
                    {
                        "app_id": "APP-0005",
                        "app_slug": "clipnest",
                        "app_name": "ClipNest",
                        "platform": "ios",
                        "store_url": "https://apps.apple.com/app/id6779928552",
                        "store_app_id": "6779928552",
                        "store_package": "",
                        "version": "1.0.2",
                        "last_updated": "2026-07-13T03:53:22Z",
                        "release_notes": "Bug fixes.",
                        "checked_at": "2026-07-14T00:00:00+09:00",
                        "status": "updated",
                        "notes": "",
                    }
                ],
            )
            released = {field: "" for field in RELEASE_HEADER}
            released.update(
                {
                    "release_id": "REL-0005",
                    "app_id": "APP-0005",
                    "app_slug": "clipnest",
                    "app_name": "ClipNest",
                    "repository": "onnellab/clipnest",
                    "tag": "v1.0.2",
                    "version": "1.0.2",
                    "platform": "ios",
                    "build_type": "release",
                    "release_type": "notes_only",
                    "release_channel": "public",
                    "status": "released",
                    "release_url": "https://github.com/onnellab/clipnest/releases/tag/v1.0.2",
                    "release_date": "2026-07-13",
                    "release_title": "ClipNest v1.0.2",
                    "summary": "ClipNest 1.0.2 public iOS store update detected.",
                    "changes": "Improved keyboard editing handoff.",
                    "compatibility": "ios public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            write_csv(releases, RELEASE_HEADER, [released])
            write_csv(
                config,
                CONFIG_HEADER,
                [
                    {
                        "app_id": "APP-0005",
                        "app_slug": "clipnest",
                        "repository": "onnellab/clipnest",
                        "artifact_pattern": "generated/releases/clipnest/{version}/{platform}/*-release.*",
                        "notes": "",
                    }
                ],
            )
            write_csv(
                local_repos,
                LOCAL_REPOSITORIES_HEADER,
                [
                    {
                        "app_id": "APP-0005",
                        "app_slug": "clipnest",
                        "repository_name": "clipnest",
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
                now=datetime.fromisoformat("2026-07-14T00:00:00+09:00"),
            )

            self.assertIn("Store release complete; confirm next public rollout", text)
            self.assertNotIn("Create or verify release candidate", text)

    def test_completed_release_with_other_platform_matching_local_version_is_no_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repos = root / "local_repositories.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            app_repo = root / "tagweaver"
            app_repo.mkdir()
            (app_repo / "pubspec.yaml").write_text("name: tagweaver\nversion: 2.1.3+81\n", encoding="utf-8")
            write_csv(
                store,
                STORE_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "app_name": "TagWeaver",
                        "platform": "ios",
                        "store_url": "https://apps.apple.com/app/id6759609875",
                        "store_app_id": "6759609875",
                        "store_package": "",
                        "version": "2.2",
                        "last_updated": "2026-07-12T18:06:15Z",
                        "release_notes": "Bug fixes.",
                        "checked_at": "2026-07-14T00:00:00+09:00",
                        "status": "updated",
                        "notes": "",
                    },
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
                        "release_notes": "Bug fixes.",
                        "checked_at": "2026-07-14T00:00:00+09:00",
                        "status": "unchanged",
                        "notes": "",
                    },
                ],
            )
            ios_release = {field: "" for field in RELEASE_HEADER}
            ios_release.update(
                {
                    "release_id": "REL-0004",
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "app_name": "TagWeaver",
                    "repository": "onnellab/tagweaver",
                    "tag": "v2.2",
                    "version": "2.2",
                    "platform": "ios",
                    "build_type": "release",
                    "release_type": "notes_only",
                    "release_channel": "public",
                    "status": "released",
                    "release_url": "https://github.com/onnellab/tagweaver/releases/tag/v2.2",
                    "release_date": "2026-07-12",
                    "release_title": "TagWeaver v2.2",
                    "summary": "TagWeaver 2.2 public iOS store update detected.",
                    "changes": "Stability improvements.",
                    "compatibility": "ios public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            android_release = {field: "" for field in RELEASE_HEADER}
            android_release.update(
                {
                    "release_id": "REL-0001",
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "app_name": "TagWeaver",
                    "repository": "onnellab/tagweaver",
                    "tag": "v2.1.3",
                    "version": "2.1.3",
                    "platform": "android",
                    "build_type": "release",
                    "release_type": "notes_only",
                    "release_channel": "public",
                    "status": "released",
                    "release_url": "https://github.com/onnellab/tagweaver/releases/tag/v2.1.3",
                    "release_date": "2026-07-12",
                    "release_title": "TagWeaver v2.1.3",
                    "summary": "TagWeaver 2.1.3 public Android store update detected.",
                    "changes": "Stability improvements.",
                    "compatibility": "android public release.",
                    "upgrade_notes": "No special upgrade steps documented yet.",
                }
            )
            write_csv(releases, RELEASE_HEADER, [ios_release, android_release])
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
            write_csv(
                local_repos,
                LOCAL_REPOSITORIES_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "repository_name": "tagweaver",
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
                now=datetime.fromisoformat("2026-07-14T00:00:00+09:00"),
            )

            self.assertIn("| TagWeaver | ios | 2.2 | 2.1.3 | store_ahead | updated | released | onnellab/tagweaver | No action |", text)
            self.assertNotIn("Platform versions diverged; confirm version policy", text)
            self.assertNotIn("Sync local metadata", text)


if __name__ == "__main__":
    unittest.main()
