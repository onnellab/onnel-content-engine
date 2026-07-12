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

from check_store_versions import (  # noqa: E402
    ANDROID_HEADER,
    STORE_HEADER,
    StoreVersionError,
    app_store_id,
    check_store_versions,
    google_play_homepage_lookup,
    play_package,
)
from validate_apps_registry import APP_HEADER  # noqa: E402


def write_apps(path: Path) -> None:
    row = {
        "app_id": "APP-0001",
        "app_name": "Quivra",
        "slug": "quivra",
        "status": "released",
        "product_group": "apps",
        "primary_category": "reading",
        "platforms": "ios|android",
        "pricing_model": "freemium",
        "content_eligible": "true",
        "official_site_path": "/apps/quivra/",
        "app_store_url": "https://apps.apple.com/app/id6759565093",
        "play_store_url": "https://play.google.com/store/apps/details?id=com.onnellab.quivra2",
        "docs_path": "",
        "one_line_description": "Read long text without lag.",
        "primary_language": "en",
        "notes": "",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APP_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def write_existing(path: Path, version: str) -> None:
    row = {field: "" for field in STORE_HEADER}
    row.update(
        {
            "app_id": "APP-0001",
            "app_slug": "quivra",
            "app_name": "Quivra",
            "platform": "ios",
            "store_url": "https://apps.apple.com/app/id6759565093",
            "store_app_id": "6759565093",
            "version": version,
            "checked_at": "2026-07-11T09:00:00+09:00",
            "status": "unchanged",
        }
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STORE_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


class StoreVersionsTest(unittest.TestCase):
    def test_extracts_store_identifiers(self) -> None:
        self.assertEqual(app_store_id("https://apps.apple.com/app/id6759565093"), "6759565093")
        self.assertEqual(
            play_package("https://play.google.com/store/apps/details?id=com.onnellab.quivra2"),
            "com.onnellab.quivra2",
        )

    def test_records_new_ios_snapshot_and_android_manual_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp) / "apps.csv"
            output = Path(temp) / "store_versions.csv"
            write_apps(apps)

            with patch(
                "check_store_versions.json_get",
                return_value={
                    "results": [
                        {
                            "version": "1.2.3",
                            "currentVersionReleaseDate": "2026-07-12T01:00:00Z",
                            "releaseNotes": "Improved launch speed.\nFixed layout.",
                        }
                    ]
                },
            ), patch("check_store_versions.html_get", side_effect=StoreVersionError("blocked")):
                rows = check_store_versions(
                    apps,
                    output,
                    Path(temp) / "missing_android_store_versions.csv",
                    now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
                )

            self.assertEqual([row["platform"] for row in rows], ["ios", "android"])
            self.assertEqual(rows[0]["status"], "new")
            self.assertEqual(rows[0]["version"], "1.2.3")
            self.assertEqual(rows[0]["release_notes"], "Improved launch speed. Fixed layout.")
            self.assertEqual(rows[1]["status"], "manual_check")
            self.assertEqual(rows[1]["store_package"], "com.onnellab.quivra2")

    def test_marks_ios_snapshot_updated_when_version_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp) / "apps.csv"
            output = Path(temp) / "store_versions.csv"
            write_apps(apps)
            write_existing(output, "1.2.2")

            with patch(
                "check_store_versions.json_get",
                return_value={"results": [{"version": "1.2.3", "currentVersionReleaseDate": "", "releaseNotes": ""}]},
            ), patch("check_store_versions.html_get", side_effect=StoreVersionError("blocked")):
                rows = check_store_versions(
                    apps,
                    output,
                    Path(temp) / "missing_android_store_versions.csv",
                    dry_run=True,
                    now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
                )

            self.assertEqual(rows[0]["status"], "updated")

    def test_android_source_marks_snapshot_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            apps = Path(temp) / "apps.csv"
            output = Path(temp) / "store_versions.csv"
            android = Path(temp) / "android_store_versions.csv"
            write_apps(apps)
            with android.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=ANDROID_HEADER, lineterminator="\n")
                writer.writeheader()
                writer.writerow(
                    {
                        "app_id": "APP-0001",
                        "app_slug": "quivra",
                        "package": "com.onnellab.quivra2",
                        "version": "1.2.3",
                        "last_updated": "2026-07-12",
                        "release_notes": "Android release.",
                        "source": "manual_entry",
                        "notes": "Manual Play Console entry.",
                    }
                )

            with patch(
                "check_store_versions.json_get",
                return_value={"results": [{"version": "1.2.3", "currentVersionReleaseDate": "", "releaseNotes": ""}]},
            ), patch(
                "check_store_versions.html_get",
                return_value='"141":[[["1.2.3"]]],"146":[["2026. 7. 12."]] com.onnellab.quivra2',
            ):
                rows = check_store_versions(
                    apps,
                    output,
                    android,
                    dry_run=True,
                    now=datetime.fromisoformat("2026-07-12T09:00:00+09:00"),
                )

            self.assertEqual(rows[1]["status"], "new")
            self.assertEqual(rows[1]["version"], "1.2.3")
            self.assertEqual(rows[1]["release_notes"], "Android release.")
            self.assertIn("Google Play public page", rows[1]["notes"])

    def test_google_play_homepage_lookup_reads_public_page_version(self) -> None:
        html = '"141":[[["2.0.1"]]],"146":[["2026. 7. 13."]] com.onnellab.quivra2'
        with patch("check_store_versions.html_get", return_value=html):
            row = google_play_homepage_lookup("https://play.google.com/store/apps/details?id=com.onnellab.quivra2")

        self.assertEqual(row["store_package"], "com.onnellab.quivra2")
        self.assertEqual(row["version"], "2.0.1")
        self.assertEqual(row["last_updated"], "2026. 7. 13.")


if __name__ == "__main__":
    unittest.main()
