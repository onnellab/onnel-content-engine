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

from verify_manual_publications import public_activity_url, public_profile_url, verify_manual_publications  # noqa: E402


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
            report = root / "data" / "manual_publication_verification_report.json"
            canonical_url = "https://onnellab.github.io/blog/en/example/"
            draft_path = root / "missing.txt"
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
                            "draft_path": str(draft_path),
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
                            "draft_path": str(draft_path),
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
                            "draft_path": str(draft_path),
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
            draft_text = "How to Read Large TXT Files Without Lag\n\nExample text\n"
            draft_path.write_text(draft_text, encoding="utf-8")

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
                return f"Public profile shows How to Read Large TXT Files Without Lag {canonical_url} from {url}"

            with unittest.mock.patch.dict(
                "os.environ",
                {
                    "BLUESKY_HANDLE": "onnellab.bsky.social",
                    "DEVTO_USERNAME": "onnellab",
                    "MEDIUM_RSS_URL": "https://medium.com/feed/@onnellab",
                    "X_PUBLIC_PROFILE_URL": "https://x.com/onnellab",
                    "LINKEDIN_PUBLIC_PROFILE_URL": "https://www.linkedin.com/in/onnel-lab-b5b9b0421/",
                },
            ):
                verified = verify_manual_publications(
                    social,
                    syndication,
                    state,
                    report,
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
            report_data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_data["counts"]["checked"], 5)
            self.assertEqual(report_data["counts"]["verified"], 5)
            self.assertEqual(report_data["counts"]["pending"], 0)

    def test_dry_run_does_not_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            social = root / "social.json"
            syndication = root / "syndication.json"
            state = root / "state.json"
            report = root / "report.json"
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
                report,
                dry_run=True,
                fetch_json=lambda _url, _headers=None: {
                    "feed": [{"post": {"uri": "at://did/app.bsky.feed.post/a", "record": {"text": "https://example.com/a"}}}]
                },
            )

            self.assertEqual(len(verified), 1)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["done"], {})
            self.assertFalse(report.exists())

    def test_report_records_pending_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            social = root / "social.json"
            syndication = root / "syndication.json"
            state = root / "state.json"
            report = root / "report.json"
            self.write_json(social, {"posts": []})
            self.write_json(
                syndication,
                {
                    "drafts": [
                        {
                            "topic_id": "TOPIC-0001",
                            "platform": "hashnode",
                            "language": "en",
                            "status": "draft",
                            "canonical_url": "https://example.com/a",
                            "slug": "a",
                            "draft_path": "missing.md",
                        }
                    ]
                },
            )
            self.write_json(state, {"version": 1, "updated_at": "", "done": {}})

            verified = verify_manual_publications(
                social,
                syndication,
                state,
                report,
                now=datetime(2026, 7, 13, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
            )

            self.assertEqual(verified, [])
            report_data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_data["counts"]["pending"], 1)
            self.assertEqual(report_data["items"][0]["reason"], "RSS URL not configured")

    def test_x_public_profile_defaults_to_onnellab(self) -> None:
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(public_profile_url("x"), "https://x.com/onnellab")

    def test_linkedin_public_profile_defaults_to_onnellab_profile(self) -> None:
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(public_profile_url("linkedin"), "https://www.linkedin.com/in/onnel-lab-b5b9b0421/")

    def test_linkedin_activity_url_uses_recent_activity_page(self) -> None:
        self.assertEqual(
            public_activity_url("linkedin", "https://www.linkedin.com/in/onnel-lab-b5b9b0421/"),
            "https://www.linkedin.com/in/onnel-lab-b5b9b0421/recent-activity/all/",
        )


if __name__ == "__main__":
    unittest.main()
