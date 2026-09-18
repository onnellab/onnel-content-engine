from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_manual_publish_site import latest_app_release_rows
from check_store_versions import ANDROID_HEADER, STORE_HEADER, check_store_versions
from generate_app_release_report import generate_app_release_report
from prepare_app_release_rows import CONFIG_HEADER
from sync_android_versions_from_repos import LOCAL_REPOSITORIES_HEADER
from sync_flutter_plugin_versions import OUTPUT_HEADER, app_version_from_pubspec, sync_flutter_plugin_versions
from validate_app_releases import RELEASE_HEADER
from validate_apps_registry import APP_HEADER


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def app_row(status: str = "released") -> dict[str, str]:
    row = {field: "" for field in APP_HEADER}
    row.update(
        {
            "app_id": "APP-0002",
            "app_name": "TagWeaver",
            "slug": "tagweaver",
            "status": status,
            "product_group": "apps",
            "primary_category": "music",
            "platforms": "ios|android",
            "pricing_model": "one_time_purchase",
            "content_eligible": "true",
            "official_site_path": "/apps/tagweaver/",
            "app_store_url": "https://apps.apple.com/app/id6759609875",
            "play_store_url": "https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2",
            "primary_language": "ko",
        }
    )
    return row


class AppOperationalStatusTest(unittest.TestCase):
    def test_dashboard_uses_latest_repository_release_state_per_app(self) -> None:
        rows = [
            {"release_id": "REL-0012", "app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android", "version": "2.3.0", "status": "planned"},
            {"release_id": "REL-0013", "app_id": "APP-0002", "app_slug": "tagweaver", "platform": "ios", "version": "2.5.0", "status": "planned"},
            {"release_id": "REL-0015", "app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android", "version": "2.6.0", "status": "archived"},
        ]

        latest = latest_app_release_rows(rows)

        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["release_id"], "REL-0013")
        self.assertEqual(latest[0]["version"], "2.5.0")

    def test_pubspec_app_version_keeps_build_and_public_version(self) -> None:
        self.assertEqual(app_version_from_pubspec("name: tagweaver\nversion: 2.5.0+90\n"), ("2.5.0", "2.5.0+90"))

    def test_flutter_snapshot_includes_repository_app_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "tagweaver"
            repo.mkdir()
            (repo / "pubspec.yaml").write_text(
                "name: tagweaver\nversion: 2.5.0+90\nenvironment:\n  flutter: '>=3.38.0'\ndependencies:\n  flutter:\n    sdk: flutter\n",
                encoding="utf-8",
            )
            repositories = root / "local_repositories.csv"
            write_csv(
                repositories,
                LOCAL_REPOSITORIES_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "repository_name": "tagweaver",
                        "path": repo.as_posix(),
                        "pubspec_path": "pubspec.yaml",
                        "source_priority": "primary",
                        "notes": "",
                    }
                ],
            )
            output = root / "versions.csv"
            report = root / "versions.md"
            rows = sync_flutter_plugin_versions(repositories, output, report)

            version = next(row for row in rows if row["package_type"] == "app_version")
            self.assertEqual(version["resolved_version"], "2.5.0")
            self.assertEqual(version["declared_version"], "2.5.0+90")
            self.assertEqual(version["status"], "ok")

    def test_development_app_is_not_reported_as_store_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apps = root / "apps.csv"
            output = root / "store_versions.csv"
            write_csv(apps, APP_HEADER, [app_row("development")])
            with patch("check_store_versions.json_get", side_effect=AssertionError("store lookup must be skipped")), patch(
                "check_store_versions.html_get", side_effect=AssertionError("store lookup must be skipped")
            ):
                rows = check_store_versions(
                    apps,
                    output,
                    root / "missing-android.csv",
                    dry_run=True,
                    now=datetime.fromisoformat("2026-09-18T16:00:00+09:00"),
                )

            self.assertEqual([row["status"] for row in rows], ["not_released", "not_released"])
            self.assertEqual(rows[0]["store_app_id"], "6759609875")
            self.assertEqual(rows[1]["store_package"], "com.onnellab.tagweaver2")

    def test_stale_android_snapshot_is_not_merged_into_newer_public_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apps = root / "apps.csv"
            output = root / "store_versions.csv"
            android = root / "android_store_versions.csv"
            write_csv(apps, APP_HEADER, [app_row("released")])
            write_csv(
                android,
                ANDROID_HEADER,
                [
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "package": "com.onnellab.tagweaver2",
                        "version": "2.1.3",
                        "last_updated": "2026-07-12",
                        "release_notes": "Old Android notes.",
                        "source": "local_build_metadata",
                        "notes": "Imported from stale pubspec 2.1.3+81.",
                    }
                ],
            )
            with patch(
                "check_store_versions.json_get",
                return_value={"results": [{"version": "2.5.0", "currentVersionReleaseDate": "2026-09-18T01:00:00Z", "releaseNotes": "Current iOS notes."}]},
            ), patch(
                "check_store_versions.html_get",
                return_value='"141":[[["2.5.0"]]],"146":[["2026. 9. 18."]] com.onnellab.tagweaver2',
            ):
                rows = check_store_versions(
                    apps,
                    output,
                    android,
                    dry_run=True,
                    now=datetime.fromisoformat("2026-09-18T16:00:00+09:00"),
                )

            android_row = next(row for row in rows if row["platform"] == "android")
            self.assertEqual(android_row["version"], "2.5.0")
            self.assertEqual(android_row["release_notes"], "")
            self.assertIn("snapshot version 2.1.3 is stale", android_row["notes"])
            self.assertNotIn("Imported from stale pubspec", android_row["notes"])

    def test_release_report_prefers_repository_main_version_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store_versions.csv"
            releases = root / "app_releases.csv"
            config = root / "app_release_config.csv"
            local_repositories = root / "local_repositories.csv"
            flutter_versions = root / "app_flutter_dependency_versions.csv"
            android_versions = root / "android_store_versions.csv"
            publications = root / "app_release_publications.csv"
            output = root / "app_releases.md"
            stale_repo = root / "stale-tagweaver"
            stale_repo.mkdir()
            (stale_repo / "pubspec.yaml").write_text("name: tagweaver\nversion: 2.1.3+81\n", encoding="utf-8")
            store_row = {field: "" for field in STORE_HEADER}
            store_row.update(
                {
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "app_name": "TagWeaver",
                    "platform": "ios",
                    "store_url": "https://apps.apple.com/app/id6759609875",
                    "store_app_id": "6759609875",
                    "version": "2.5.0",
                    "checked_at": "2026-09-18T16:00:00+09:00",
                    "status": "unchanged",
                }
            )
            write_csv(store, STORE_HEADER, [store_row])
            write_csv(releases, RELEASE_HEADER, [])
            write_csv(
                config,
                CONFIG_HEADER,
                [{"app_id": "APP-0002", "app_slug": "tagweaver", "repository": "onnellab/tagweaver", "artifact_pattern": "", "notes": ""}],
            )
            write_csv(
                local_repositories,
                LOCAL_REPOSITORIES_HEADER,
                [{"app_id": "APP-0002", "app_slug": "tagweaver", "repository_name": "tagweaver", "path": stale_repo.as_posix(), "pubspec_path": "pubspec.yaml", "source_priority": "primary", "notes": ""}],
            )
            app_version_row = {field: "" for field in OUTPUT_HEADER}
            app_version_row.update(
                {
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "package_type": "app_version",
                    "package_name": "tagweaver",
                    "declared_version": "2.5.0+90",
                    "resolved_version": "2.5.0",
                    "status": "ok",
                    "source": "github:onnellab/tagweaver/pubspec.yaml",
                }
            )
            write_csv(flutter_versions, OUTPUT_HEADER, [app_version_row])
            write_csv(android_versions, ["app_id", "app_slug", "package", "version", "last_updated", "release_notes", "source", "notes"], [])
            write_csv(publications, ["release_id", "public_release", "approved_at", "notes"], [])

            text = generate_app_release_report(
                store,
                releases,
                config,
                local_repositories,
                output,
                publications,
                now=datetime.fromisoformat("2026-09-18T16:00:00+09:00"),
                android_versions_path=android_versions,
                flutter_versions_path=flutter_versions,
            )

            self.assertIn("Repository version", text)
            self.assertIn("| TagWeaver | ios | 2.5.0 | 2.5.0 | same |", text)
            self.assertNotIn("| TagWeaver | ios | 2.5.0 | 2.1.3 |", text)


if __name__ == "__main__":
    unittest.main()
