from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_manual_publish_site import html_document
from ops_split_pages import build_split_ops_pages
from validate_manual_publish_site import validate_dashboard


class OpsSplitPagesTest(unittest.TestCase):
    def test_split_pages_keep_legacy_payload_and_use_apps_card_design(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            homepage = root / "homepage"
            app_dir = homepage / "src" / "content" / "apps" / "tagweaver"
            app_dir.mkdir(parents=True)
            (app_dir / "app.md").write_text("title: TagWeaver\nicon: assets\\icon\\tagweaver.png\n", encoding="utf-8")
            output = root / "ops"
            app = {
                "app_id": "APP-0002",
                "app_name": "TagWeaver",
                "slug": "tagweaver",
                "status": "released",
                "platforms": "ios|android",
                "one_line_description": "Offline MP3/FLAC Tag Editor",
            }
            store_items = [
                {"app_id": "APP-0002", "app_slug": "tagweaver", "platform": "ios", "version": "2.5.2", "status": "unchanged", "checked_at": "2026-10-07"},
                {"app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android", "version": "2.5.2", "status": "unchanged", "checked_at": "2026-10-07"},
            ]
            dependencies = [
                {"app_id": "APP-0002", "app_slug": "tagweaver", "package_type": "app_version", "package_name": "tagweaver", "declared_version": "2.5.2+96", "resolved_version": "2.5.2"},
                {"app_id": "APP-0002", "app_slug": "tagweaver", "package_type": "dependency", "package_name": "file_picker", "declared_version": "^10.0.0", "resolved_version": "10.0.0"},
            ]
            build_split_ops_pages(
                output,
                legacy_html=html_document([]),
                homepage_repo=homepage,
                apps=[app],
                publication_items=[],
                releases=[],
                store_items=store_items,
                reviews=[],
                dependencies=dependencies,
                pricing=[],
            )

            validate_dashboard(output / "index.html")
            self.assertTrue((output / "publishing" / "index.html").exists())
            self.assertTrue((output / "media" / "index.html").exists())
            self.assertTrue((output / "settings" / "index.html").exists())
            self.assertTrue((output / "legacy" / "index.html").exists())

            apps_html = (output / "apps" / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="app-card"', apps_html)
            self.assertIn('class="title-row"', apps_html)
            self.assertIn('class="status-badge"', apps_html)
            self.assertIn('class="platform-badges"', apps_html)
            self.assertIn('/app-assets/tagweaver/assets/icon/tagweaver.png', apps_html)
            self.assertIn('/ops/apps/tagweaver/', apps_html)

            detail = (output / "apps" / "tagweaver" / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="funnel"', detail)
            self.assertIn("2.5.2", detail)
            self.assertIn("file_picker", detail)


if __name__ == "__main__":
    unittest.main()
