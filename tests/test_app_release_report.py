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
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertIn("# App Release Status", text)
            self.assertIn("Check Google Play update manually", text)
            self.assertIn("Add release artifact and checksum", text)
            self.assertIn("Publication gate", text)
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
                now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
            )

            self.assertIn("Private test or approval pending", text)
            self.assertIn("Approve public release or keep as private test", text)


if __name__ == "__main__":
    unittest.main()
