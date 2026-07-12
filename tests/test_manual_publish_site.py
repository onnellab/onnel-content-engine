from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_manual_publish_site import build_manual_publish_site  # noqa: E402


class ManualPublishSiteTest(unittest.TestCase):
    def test_builds_dashboard_with_social_and_syndication_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            social_draft = root / "x.txt"
            social_draft.write_text("Post text\nhttps://onnellab.github.io/blog/en/example/", encoding="utf-8")
            syndication_draft = root / "devto.md"
            syndication_draft.write_text("# Article\n\nBody", encoding="utf-8")
            social_manifest = root / "social.json"
            syndication_manifest = root / "syndication.json"
            output = root / "manual" / "index.html"
            social_manifest.write_text(
                json.dumps(
                    {
                        "posts": [
                            {
                                "topic_id": "TOPIC-0001",
                                "platform": "x",
                                "language": "en",
                                "category": "reading",
                                "slug": "example",
                                "template_id": "x",
                                "is_variant": False,
                                "status": "draft",
                                "draft_path": social_draft.relative_to(ROOT).as_posix()
                                if social_draft.is_relative_to(ROOT)
                                else social_draft.as_posix(),
                                "canonical_url": "https://onnellab.github.io/blog/en/example/",
                                "card_asset_path": "generated/assets/blog/en/example/social-card.png",
                                "weighted_length": 48,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            syndication_manifest.write_text(
                json.dumps(
                    {
                        "drafts": [
                            {
                                "topic_id": "TOPIC-0001",
                                "platform": "devto",
                                "language": "en",
                                "category": "reading",
                                "slug": "example",
                                "status": "draft",
                                "draft_path": syndication_draft.as_posix(),
                                "canonical_url": "https://onnellab.github.io/blog/en/example/",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            build_manual_publish_site(social_manifest, syndication_manifest, output, ROOT / "data" / "topics.csv")

            html = output.read_text(encoding="utf-8")
            self.assertIn("ONNELLAB Manual Publish", html)
            self.assertIn("ONNELLAB 수동 게시", html)
            self.assertIn("동기화 연결", html)
            self.assertIn('id="lang-toggle"', html)
            self.assertIn("https://twitter.com/intent/tweet", html)
            self.assertIn("https://dev.to/new", html)
            self.assertIn("/blog-assets/en/example/social-card.png", html)
            self.assertIn("statePath = 'data/manual_publish_state.json'", html)
            self.assertIn("setAppBadge", html)
            self.assertIn("Enable badge", html)
            self.assertIn('name="robots" content="noindex,nofollow,noarchive"', html)
            self.assertIn("Twitter", html)
            self.assertIn('"publishing_mode": "manual"', html)
            self.assertIn('"publishing_mode": "automatic"', html)
            self.assertIn('id="mode"', html)
            self.assertIn('id="toggle-variants"', html)
            self.assertIn("수동 게시 필요", html)
            self.assertIn("자동화 대상", html)
            self.assertIn("platform-badge", html)
            self.assertIn("오늘 할 일", html)
            self.assertIn('data-view="due"', html)
            self.assertIn("currentView = 'due'", html)
            self.assertIn("GitHub에 올릴 릴리즈 후보", html)
            self.assertIn('id="release-grid"', html)
            self.assertIn("release-data", html)
            self.assertIn("릴리즈 후보", html)
            self.assertIn("예정일", html)
            self.assertIn("App Store / Play Store 현재 공개 버전", html)
            self.assertIn('id="store-grid"', html)
            self.assertIn("store-data", html)
            self.assertIn('"platform": "android"', html)
            self.assertIn("본문 보기", html)
            self.assertIn("card-detail", html)
            self.assertIn("링크 카드 사용", html)
            self.assertIn("이미지 첨부 없이 링크 카드로 게시", html)
            self.assertIn("usesLinkPreviewCard", html)
            self.assertIn("지금 게시할 수동 항목이 없습니다", html)
            self.assertIn("블로그 상태", html)
            self.assertIn('id="blog-grid"', html)
            self.assertIn("blog-data", html)
            self.assertIn("다음 게시 예정", html)
            self.assertIn("mode-manual", html)
            self.assertIn("syncButtonLarge.disabled = !githubToken()", html)
            self.assertNotIn('id="sync-state"', html)
            self.assertNotIn('id="label-total"', html)
            self.assertIn("/favicon.svg?v=20260712-ol-transparent-v2", html)
            self.assertIn(">English</button>", html)
            manifest = (output.parent / "manifest.webmanifest").read_text(encoding="utf-8")
            self.assertIn("/favicon-32x32.png?v=20260712-ol-transparent-v2", manifest)
            self.assertNotIn("favicon-16x16.png", manifest)
            self.assertTrue((output.parent / "manifest.webmanifest").exists())
            self.assertTrue((output.parent / "sw.js").exists())


if __name__ == "__main__":
    unittest.main()
