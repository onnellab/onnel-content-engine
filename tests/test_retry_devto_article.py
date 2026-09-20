from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import retry_devto_article as retry  # noqa: E402
from post_syndication_drafts import SyndicationPostingError  # noqa: E402


def make_manifest(root: Path, status: str = "failed") -> Path:
    draft_path = root / "generated/syndication/devto/en/example.md"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text("---\ntitle: Example\npublished: true\ntags: test\ncanonical_url: https://example.com/canonical/\n---\n# Example\n\nOriginally published at https://example.com/canonical/\n", encoding="utf-8")
    manifest = root / "generated/syndication/manifest.json"
    manifest.write_text(json.dumps({"drafts": [{
        "topic_id": "TOPIC-0020", "source_status": "published", "publish_after_canonical": False,
        "platform": "devto", "language": "en", "category": "productivity", "slug": "example",
        "draft_path": "generated/syndication/devto/en/example.md", "canonical_url": "https://example.com/canonical/",
        "status": status, "post_id": "", "posted_url": "", "posted_at": "", "last_attempt_at": "",
        "error": "", "error_type": "", "retry_count": 1,
    }]}, indent=2), encoding="utf-8")
    return manifest


class RetryDevtoArticleTest(unittest.TestCase):
    def invoke(self, match: list[dict[str, object]], *, post=None, put=None, public=None) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = make_manifest(root)
            with patch.dict(os.environ, {"DEVTO_API_KEY": "secret"}), patch.object(retry, "validate_syndication_drafts"), patch.object(retry, "_require_current_published_topic"), patch.object(retry, "authenticated_articles", return_value=match), patch.object(retry, "public_article", return_value=public or {"id": 7, "canonical_url": "https://example.com/canonical/", "url": "https://dev.to/onnellab/example", "published_at": "2026-09-20T00:00:00Z"}), patch.object(retry, "post_devto_draft", return_value=post or (7, "https://dev.to/onnellab/example")) as post_call, patch.object(retry, "put_json", return_value=put or {"id": 7}) as put_call:
                result = retry.retry_devto_article(manifest, "TOPIC-0020")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        return {"draft": result, "manifest": payload, "post_called": post_call, "put_called": put_call}

    def test_existing_published_match_reconciles_without_post(self) -> None:
        result = self.invoke([{"id": 7, "canonical_url": "https://example.com/canonical/", "published_at": "old"}])
        self.assertEqual(result["draft"]["status"], "posted")
        result["post_called"].assert_not_called()
        result["put_called"].assert_not_called()

    def test_no_match_posts_only_selected_draft_and_preserves_unrelated_approved(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = make_manifest(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            unrelated = dict(payload["drafts"][0], topic_id="TOPIC-0099", status="approved", post_id="", error="")
            payload["drafts"].append(unrelated)
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"DEVTO_API_KEY": "secret"}), patch.object(retry, "validate_syndication_drafts"), patch.object(retry, "_require_current_published_topic"), patch.object(retry, "authenticated_articles", return_value=[]), patch.object(retry, "post_devto_draft", return_value=(88, "")) as post, patch.object(retry, "public_article", return_value={"id": 88, "canonical_url": "https://example.com/canonical/", "url": "https://dev.to/onnellab/example", "published_at": "2026-09-20T00:00:00Z"}):
                retry.retry_devto_article(manifest, "TOPIC-0020")
            updated = json.loads(manifest.read_text(encoding="utf-8"))["drafts"]
        post.assert_called_once()
        selected = next(item for item in updated if item["topic_id"] == "TOPIC-0020")
        untouched = next(item for item in updated if item["topic_id"] == "TOPIC-0099")
        self.assertEqual(selected["status"], "posted")
        self.assertEqual(untouched["status"], "approved")
        self.assertEqual(untouched["post_id"], "")

    def test_unpublished_match_uses_put_and_no_post(self) -> None:
        result = self.invoke([{"id": 7, "canonical_url": "https://example.com/canonical/", "published_at": ""}])
        self.assertEqual(result["draft"]["status"], "posted")
        result["post_called"].assert_not_called()
        result["put_called"].assert_called_once()

    def test_duplicate_canonical_match_fails_closed_without_post(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = make_manifest(Path(raw))
            with patch.dict(os.environ, {"DEVTO_API_KEY": "secret"}), patch.object(retry, "validate_syndication_drafts"), patch.object(retry, "_require_current_published_topic"), patch.object(retry, "authenticated_articles", return_value=[{"id": 1, "canonical_url": "https://example.com/canonical/"}, {"id": 2, "canonical_url": "https://example.com/canonical"}]), patch.object(retry, "post_devto_draft") as post:
                with self.assertRaises(SyndicationPostingError):
                    retry.retry_devto_article(manifest, "TOPIC-0020")
            post.assert_not_called()

    def test_saved_id_without_canonical_match_does_not_post(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = make_manifest(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["drafts"][0]["post_id"] = "99"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"DEVTO_API_KEY": "secret"}), patch.object(retry, "validate_syndication_drafts"), patch.object(retry, "_require_current_published_topic"), patch.object(retry, "authenticated_articles", return_value=[]), patch.object(retry, "post_devto_draft") as post:
                with self.assertRaises(SyndicationPostingError):
                    retry.retry_devto_article(manifest, "TOPIC-0020")
            post.assert_not_called()

    def test_rate_limit_is_recorded_as_failed_without_secret_or_raw_body(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            manifest = make_manifest(Path(raw))
            with patch.dict(os.environ, {"DEVTO_API_KEY": "secret"}), patch.object(retry, "validate_syndication_drafts"), patch.object(retry, "_require_current_published_topic"), patch.object(retry, "authenticated_articles", side_effect=SyndicationPostingError("HTTP 429 from Dev.to: secret-body")):
                with self.assertRaises(SyndicationPostingError):
                    retry.retry_devto_article(manifest, "TOPIC-0020")
            draft = json.loads(manifest.read_text(encoding="utf-8"))["drafts"][0]
        self.assertEqual(draft["status"], "failed")
        self.assertEqual(draft["error_type"], "rate_limited")
        self.assertNotIn("secret-body", json.dumps(draft))

    def test_post_id_is_saved_before_public_verification_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = make_manifest(root)
            with patch.dict(os.environ, {"DEVTO_API_KEY": "secret"}), patch.object(retry, "validate_syndication_drafts"), patch.object(retry, "_require_current_published_topic"), patch.object(retry, "authenticated_articles", return_value=[]), patch.object(retry, "post_devto_draft", return_value=(88, "")), patch.object(retry, "public_article", return_value={"id": 88, "canonical_url": "https://wrong.example/", "url": "https://dev.to/onnellab/example", "published_at": "now"}):
                with self.assertRaises(SyndicationPostingError):
                    retry.retry_devto_article(manifest, "TOPIC-0020")
            draft = json.loads(manifest.read_text(encoding="utf-8"))["drafts"][0]
        self.assertEqual(draft["post_id"], "88")
        self.assertEqual(draft["status"], "failed")


if __name__ == "__main__":
    unittest.main()
