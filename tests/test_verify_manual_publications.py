from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_manual_publications import verify_manual_publications  # noqa: E402


class VerifyManualPublicationsTest(unittest.TestCase):
    def write_json(self, path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_verifies_public_api_rss_and_visual_pages_into_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            social = root / "generated" / "social" / "manifest.json"
            syndication = root / "generated" / "syndication" / "manifest.json"
            state = root / "data" / "manual_publish_state.json"
            canonical_url = "https://onnellab.github.io/blog/en/example/"
            self.write_json(
                social,
                {
                    "posts": [
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "bluesky",
                            "language": "en",
                            "template_id": "bluesky",
                            "status": "draft",
                            "canonical_url": canonical_url,
                            "slug": "example",
                            "draft_path": "missing.txt",
                            "is_variant": False,
                        },
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "x",
                            "language": "en",
                            "template_id": "x",
                            "status": "draft",
                            "canonical_url": canonical_url,
                            "slug": "example",
                            "draft_path": "missing.txt",
                            "is_variant": False,
                        },
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "linkedin",
                            "language": "en",
                            "template_id": "linkedin",
                            "status": "draft",
                            "canonical_url": canonical_url,
                            "slug": "example",
                            "draft_path": "missing.txt",
                            "is_variant": False,
                        },
                    ]
                },
            )
            self.write_json(
                syndication,
                {
                    "drafts": [
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "devto",
                            "language": "en",
                            "status": "draft",
                            "canonical_url": canonical_url,
                            "slug": "example",
                            "draft_path": "missing.md",
                        },
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "medium",
                            "language": "en",
                            "status": "draft",
                            "canonical_url": canonical_url,
                            "slug": "example",
                            "draft_path": "missing.md",
                        },
                    ]
                },
            )
            self.write_json(state, {"version": 1, "updated_at": "", "done": {}})

            def fetch_json(url: str, _headers: dict[str, str] | None = None) -> object:
                if "app.bsky.feed.getAuthorFeed" in url:
                    return {
                        "feed": [
                            {
                                "post": {
                                    "uri": "at://did:plc:test/app.bsky.feed.post/abc123",
                                    "record": {"text": canonical_url},
                                }
                            }
                        ]
                    }
                if "dev.to/api/articles" in url:
                    return [{"url": "https://dev.to/onnellab/example", "canonical_url": canonical_url}]
                raise AssertionError(url)

            def fetch_text(url: str, _headers: dict[str, str] | None = None) -> str:
                self.assertIn("medium", url)
                return f"<rss><item><link>{canonical_url}</link></item></rss>"

            def visual_text(url: str) -> str:
                return f"Public profile shows {canonical_url} from {url}"

            with unittest.mock.patch.dict(
                "os.environ",
                {
                    "BLUESKY_HANDLE": "onnellab.bsky.social",
                    "DEVTO_USERNAME": "onnellab",
                    "MEDIUM_RSS_URL": "https://medium.com/feed/@onnellab",
                    "X_PUBLIC_PROFILE_URL": "https://x.com/onnellab",
                    "LINKEDIN_PUBLIC_PROFILE_URL": "https://www.linkedin.com/in/onnellab/",
                },
            ):
                verified = verify_manual_publications(
                    social,
                    syndication,
                    state,
                    visual_public_pages=True,
                    now=datetime(2026, 7, 13, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
                    fetch_json=fetch_json,
                    fetch_text=fetch_text,
                    visual_text=visual_text,
                )

            self.assertEqual(len(verified), 5)
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertIn("TOPIC-0001::bluesky::en::bluesky", data["done"])
            self.assertEqual(data["done"]["TOPIC-0001::devto::en::markdown"]["posted_url"], "https://dev.to/onnellab/example")
            self.assertEqual(data["done"]["TOPIC-0001::x::en::x"]["verification_method"], "x_public_page_visual")
            self.assertEqual(data["done"]["TOPIC-0001::linkedin::en::linkedin"]["verification_confidence"], "low")

    def test_dry_run_does_not_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            social = root / "social.json"
            syndication = root / "syndication.json"
            state = root / "state.json"
            self.write_json(
                social,
                {
                    "posts": [
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "bluesky",
                            "language": "en",
                            "template_id": "bluesky",
                            "status": "draft",
                            "canonical_url": "https://example.com/a",
                            "is_variant": False,
                        }
                    ]
                },
            )
            self.write_json(syndication, {"drafts": []})
            self.write_json(state, {"version": 1, "updated_at": "", "done": {}})

            verified = verify_manual_publications(
                social,
                syndication,
                state,
                dry_run=True,
                fetch_json=lambda _url, _headers=None: {
                    "feed": [{"post": {"uri": "at://did/app.bsky.feed.post/a", "record": {"text": "https://example.com/a"}}}]
                },
            )

            self.assertEqual(len(verified), 1)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["done"], {})


if __name__ == "__main__":
    unittest.main()
