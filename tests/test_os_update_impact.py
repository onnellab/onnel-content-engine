from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_os_update_impact  # noqa: E402
from validate_apps_registry import APP_HEADER  # noqa: E402


def write_apps(path: Path) -> None:
    rows = [
        {"app_id": "APP-0001", "app_name": "Papira", "slug": "papira", "status": "in_review", "product_group": "apps", "primary_category": "productivity", "platforms": "ios|android", "pricing_model": "freemium", "content_eligible": "false", "official_site_path": "", "app_store_url": "", "play_store_url": "", "docs_path": "", "one_line_description": "Organize notes and documents.", "primary_language": "en", "notes": ""},
        {"app_id": "APP-0002", "app_name": "Clipnest", "slug": "clipnest", "status": "released", "product_group": "apps", "primary_category": "media", "platforms": "ios", "pricing_model": "free", "content_eligible": "true", "official_site_path": "/apps/clipnest/", "app_store_url": "https://apps.apple.com/app/id1", "play_store_url": "", "docs_path": "", "one_line_description": "Capture and organize clips.", "primary_language": "en", "notes": ""},
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APP_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class OsUpdateImpactTest(unittest.TestCase):
    def test_changed_source_creates_review_for_matching_platform_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            write_apps(data / "apps_registry.csv")
            (data / "os_update_watchlist.json").write_text(json.dumps({"sources": [
                {"platform": "android", "status": "changed", "url": "https://example.com/android", "content_hash": "h1", "checked_at": "2026-09-20"},
            ]}), encoding="utf-8")
            with patch.object(analyze_os_update_impact, "ROOT", root):
                self.assertEqual(analyze_os_update_impact.main(), 0)
            payload = json.loads((data / "os_update_impact_tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["tasks"]), 1)
        self.assertEqual(payload["tasks"][0]["app_slug"], "papira")
        self.assertEqual(payload["tasks"][0]["task_id"], "os-android-papira")
        self.assertEqual(payload["tasks"][0]["status"], "review_required")

    def test_no_changed_sources_produces_no_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            write_apps(data / "apps_registry.csv")
            (data / "os_update_watchlist.json").write_text(json.dumps({"sources": [
                {"platform": "android", "status": "unchanged"},
            ]}), encoding="utf-8")
            with patch.object(analyze_os_update_impact, "ROOT", root):
                self.assertEqual(analyze_os_update_impact.main(), 0)
            payload = json.loads((data / "os_update_impact_tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["tasks"], [])


if __name__ == "__main__":
    unittest.main()
