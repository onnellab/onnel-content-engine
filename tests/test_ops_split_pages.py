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
            (app_dir / "description-ko.md").write_text(
                "간단한 설명:\nMP3/FLAC 태그를 오프라인으로 편집해요.\n",
                encoding="utf-8",
            )
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
                funnel_summary={
                    "source_status": {
                        "apple": {"status": "ok", "apps": {"tagweaver": {"status": "ok"}}},
                        "google": {"status": "ok"},
                    },
                    "apps": {
                        "tagweaver": {
                            "platforms": {
                                "ios": {
                                    "latest_date": "2026-10-06",
                                    "windows": {
                                        "30": {
                                            "impressions": 1234,
                                            "store_visitors": 234,
                                            "installs": 45,
                                            "purchases": 2,
                                            "days_with_data": 12,
                                        }
                                    },
                                },
                                "android": {
                                    "latest_date": "2026-10-06",
                                    "windows": {
                                        "30": {
                                            "impressions": None,
                                            "store_visitors": 345,
                                            "installs": 23,
                                            "purchases": 1,
                                            "days_with_data": 12,
                                        }
                                    },
                                },
                            },
                            "combined": {
                                "30": {"store_visitors": None, "impressions": None, "installs": 68, "purchases": 3}
                            },
                        }
                    },
                },
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
            self.assertIn('class="ops-topbar"', apps_html)
            self.assertIn('href="/" aria-label="ONNELLAB home"', apps_html)
            self.assertIn('id="ops-lang-toggle"', apps_html)
            self.assertIn('data-ko="앱 관리" data-en="App management"', apps_html)
            self.assertIn("MP3/FLAC 태그를 오프라인으로 편집해요.", apps_html)
            self.assertIn("Offline MP3/FLAC Tag Editor", apps_html)
            self.assertIn('data-ko="출시됨" data-en="Released"', apps_html)

            detail = (output / "apps" / "tagweaver" / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="funnel"', detail)
            self.assertIn("2.5.2", detail)
            self.assertIn("file_picker", detail)
            self.assertIn('data-ko="앱 운영" data-en="App Operations"', detail)
            self.assertIn('data-ko="변경 없음" data-en="unchanged"', detail)
            self.assertIn("onnellab-ops-language", detail)
            self.assertIn('data-funnel-period="7"', detail)
            self.assertIn('data-funnel-period="30" class="is-active"', detail)
            self.assertIn('data-funnel-period="90"', detail)
            self.assertIn('data-funnel-window="30">', detail)
            self.assertIn('data-funnel-window="7" hidden', detail)
            self.assertIn(">1,234</b>", detail)
            self.assertIn(">234</b>", detail)
            self.assertIn(">345</b>", detail)
            self.assertIn(">68</b>", detail)
            self.assertIn(">3</b>", detail)
            self.assertIn('data-ko="양 스토어 설치 합계" data-en="Combined installs"', detail)
            self.assertIn('data-ko="양 스토어 구매 합계" data-en="Combined purchases"', detail)
            self.assertNotIn("Combined visitors", detail)
            self.assertNotIn("양 스토어 방문 합계", detail)
            self.assertIn("선택한 기간에 수집된 데이터가 아직 없어요.", detail)


if __name__ == "__main__":
    unittest.main()
