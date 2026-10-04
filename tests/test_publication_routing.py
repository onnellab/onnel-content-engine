from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from post_core_distribution import post_core_distribution
from post_social_drafts import SocialPostingError, approved_posts, post_social_drafts
from post_syndication_drafts import approved_drafts
from publishing import previous_social_state
from generate_syndication_drafts import previous_syndication_state, _previous_posted_draft_bodies
from publication_history import publication_history, preserve_publication, specific_permalink
from validate_syndication_drafts import SyndicationValidationError, validate_draft


class PublicationRoutingTest(unittest.TestCase):
    def test_medium_remote_posted_history_validates_without_rewriting_legacy_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "medium.md"
            path.write_bytes(b"Legacy already published body.\r\n")
            item = {"topic_id": "T1", "platform": "medium", "language": "en", "draft_path": "medium.md", "canonical_url": "https://onnellab.com/blog/article/", "status": "posted", "posted_url": "https://medium.com/@onnellab/story-abcdef123456"}
            validate_draft(item, root)
            self.assertEqual(path.read_bytes(), b"Legacy already published body.\r\n")
            self.assertEqual(approved_drafts({"drafts": [item]}, "medium"), [])
            for change in ({"posted_url": ""}, {"posted_url": "https://medium.com/@onnellab"}, {"posted_url": "https://evilmedium.com/@onnellab/story-abcdef123456"}, {"status": "approved"}, {"status": "failed"}):
                with self.subTest(change=change), self.assertRaises(SyndicationValidationError):
                    validate_draft(dict(item, **change), root)
            with self.assertRaisesRegex(SyndicationValidationError, "does not exist"):
                validate_draft(dict(item, draft_path="missing.md"), root)

    def test_permalink_validation_rejects_profiles_editors_and_wrong_hosts(self):
        for platform, url in (
            ("x", "https://x.com/onnellab"),
            ("x", "https://x.com/onnellab/status/not-an-id"),
            ("linkedin", "https://evillinkedin.com/posts/example"),
            ("linkedin", "https://www.linkedin.com/in/onnellab/"),
            ("medium", "https://medium.com/@onnellab"),
            ("medium", "https://medium.com/p/abcdef123456/edit"),
            ("medium", "https://medium.com/feed/@onnellab"),
            ("x", "https://user:secret@x.com/onnellab/status/123"),
            ("hashnode", "https://onnellab.hashnode.dev/article"),
        ):
            with self.subTest(url=url):
                self.assertFalse(specific_permalink(platform, url))

    def test_exact_identity_join_and_existing_url_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            key = "T1::x::en::x"
            old = "https://x.com/onnellab/status/123"
            newer = "https://x.com/onnellab/status/456"
            (root / "data/manual_publish_state.json").write_text(json.dumps({"done": {key: {"platform": "x", "posted_url": old}}}))
            (root / "data/remote_browser_publications.json").write_text(json.dumps({"schema_version": 1, "records": [{"manual_key": key, "platform": "x", "posted_url": newer, "status": "processed"}]}))
            history = publication_history(root)
            item = {"topic_id": "T1", "platform": "x", "language": "en", "template_id": "x", "status": "draft"}
            self.assertEqual(preserve_publication(item, history)["posted_url"], old)
            self.assertEqual(preserve_publication(dict(item, posted_url=newer), history)["posted_url"], newer)
            self.assertEqual(preserve_publication(dict(item, language="ko"), history)["status"], "draft")
            self.assertEqual(preserve_publication(dict(item, template_id="variant"), history)["status"], "draft")
            (root / "data/manual_publish_state.json").write_text(json.dumps({"done": {key: {"platform": "linkedin", "posted_url": old}}}))
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                publication_history(root)

    def test_generation_keeps_valid_and_legacy_remote_copy_without_rewriting_receipts(self):
        from test_publishing import PublishingTest
        from publishing import generate_social_posts
        from generate_syndication_drafts import generate_syndication_drafts

        fixture = PublishingTest()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        social_dir = fixture.root / "generated/social"
        synd_dir = fixture.root / "generated/syndication"
        with patch("publishing.write_social_card", return_value=fixture.root / "generated/card.png"):
            generate_social_posts(fixture.topics_path, social_dir, "https://example.com/")
        generate_syndication_drafts(fixture.topics_path, synd_dir, "https://example.com/")
        social = json.loads((social_dir / "manifest.json").read_text())["posts"]
        synd = json.loads((synd_dir / "manifest.json").read_text())["drafts"]
        originals = {}
        done = {}
        for item in [next(p for p in social if p["platform"] == "x" and not p["is_variant"]), next(d for d in synd if d["platform"] == "medium")]:
            path = fixture.root / item["draft_path"]
            original = path.read_bytes()
            originals[item["platform"]] = (path, original)
            template = item.get("template_id", "markdown")
            key = f'{item["topic_id"]}::{item["platform"]}::{item["language"]}::{template}'
            done[key] = {"platform": item["platform"], "posted_url": "https://x.com/onnellab" if item["platform"] == "x" else "https://medium.com/@onnellab/story-abcdef123456"}
        state_path = fixture.root / "data/manual_publish_state.json"
        state_path.write_text(json.dumps({"done": done}))
        state_bytes = state_path.read_bytes()
        with patch("publishing.write_social_card", return_value=fixture.root / "generated/card.png"), patch("publishing.render_social_template_post", return_value="Changed generated text"):
            generate_social_posts(fixture.topics_path, social_dir, "https://example.com/")
        with patch("generate_syndication_drafts.render_template", return_value="Changed generated article"):
            generate_syndication_drafts(fixture.topics_path, synd_dir, "https://example.com/")
        for path, original in originals.values():
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(state_path.read_bytes(), state_bytes)
        regenerated_social = json.loads((social_dir / "manifest.json").read_text())["posts"]
        regenerated_medium = next(d for d in json.loads((synd_dir / "manifest.json").read_text())["drafts"] if d["platform"] == "medium")
        self.assertEqual(next(p for p in regenerated_social if p["platform"] == "x" and not p["is_variant"])["status"], "draft")
        self.assertEqual(regenerated_medium["status"], "posted")

    def test_core_posts_only_api_owned_channels(self):
        with patch("post_core_distribution.post_social_drafts", return_value=[]) as social, patch("post_core_distribution.post_syndication_drafts", return_value=[]) as synd:
            self.assertEqual(post_core_distribution(dry_run=True), [])
        self.assertEqual([call.kwargs["platform"] for call in social.call_args_list], ["bluesky"])
        self.assertEqual([call.kwargs["platform"] for call in synd.call_args_list], ["devto"])

    def test_live_remote_adapter_fails_before_network_or_manifest_access(self):
        for platform in ("x", "linkedin"):
            with self.subTest(platform=platform), patch("post_social_drafts.json_post") as network:
                with self.assertRaisesRegex(SocialPostingError, "remote_browser"):
                    post_social_drafts(Path("missing.json"), platform=platform, adapter=platform)
                network.assert_not_called()

    def test_existing_permalink_is_never_selected_for_reposting(self):
        item = {"status": "approved", "platform": "bluesky", "posted_url": "https://bsky.app/profile/a/post/b"}
        self.assertEqual(approved_posts({"posts": [item]}), [])
        draft = {"status": "approved", "platform": "devto", "posted_url": "https://dev.to/onnellab/existing-article"}
        self.assertEqual(approved_drafts({"drafts": [draft]}), [])

    def test_evidence_without_previous_manifest_or_item_fails_closed(self):
        for platform, kind, template, loader in (("x", "social", "x", previous_social_state), ("medium", "syndication", "markdown", previous_syndication_state)):
            for missing_manifest in (True, False):
                with self.subTest(platform=platform, missing_manifest=missing_manifest), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "data").mkdir()
                    output = root / "generated" / kind
                    output.mkdir(parents=True)
                    (root / "data/manual_publish_state.json").write_text(json.dumps({"done": {f"T1::{platform}::en::{template}": {"platform": platform}}}))
                    if not missing_manifest:
                        (output / "manifest.json").write_text(json.dumps({"posts" if kind == "social" else "drafts": []}))
                    with self.assertRaisesRegex(ValueError, "without previous manifest item"):
                        loader(output)

    def test_remote_receipts_preserve_social_and_medium_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            records = []
            for platform, kind, template, url in (
                ("x", "social", "x", "https://x.com/onnellab/status/123"),
                ("medium", "syndication", "markdown", "https://medium.com/@onnellab/story-abcdef123456"),
            ):
                output = root / "generated" / kind
                output.mkdir(parents=True)
                draft = output / "published.txt"
                draft.write_text("Original public text.\n", encoding="utf-8")
                item = {"topic_id": "T1", "platform": platform, "language": "en", "template_id": template, "status": "draft", "draft_path": draft.relative_to(root).as_posix()}
                (output / "manifest.json").write_text(json.dumps({"posts" if kind == "social" else "drafts": [item]}), encoding="utf-8")
                records.append({"manual_key": f"T1::{platform}::en::{template}", "platform": platform, "posted_url": url, "status": "new", "published_at": "2026-10-01T00:00:00Z"})
            (root / "data" / "remote_browser_publications.json").write_text(json.dumps({"schema_version": 1, "records": records}), encoding="utf-8")
            social = previous_social_state(root / "generated" / "social")[("T1", "x", "en", "x")]
            self.assertEqual(social["status"], "posted")
            self.assertEqual(social["posted_url"], records[0]["posted_url"])
            self.assertEqual(social["_draft_text"], "Original public text.\n")
            synd = previous_syndication_state(root / "generated" / "syndication")
            self.assertEqual(synd[("T1", "medium", "en")]["posted_url"], records[1]["posted_url"])
            self.assertEqual(_previous_posted_draft_bodies(synd, root / "generated" / "syndication", root)[("T1", "medium", "en")], b"Original public text.\n")


if __name__ == "__main__":
    unittest.main()
