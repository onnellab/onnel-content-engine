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

            build_manual_publish_site(social_manifest, syndication_manifest, output)

            html = output.read_text(encoding="utf-8")
            self.assertIn("ONNELLAB Manual Publish", html)
            self.assertIn("https://twitter.com/intent/tweet", html)
            self.assertIn("https://dev.to/new", html)
            self.assertIn("../assets/blog/en/example/social-card.png", html)


if __name__ == "__main__":
    unittest.main()
