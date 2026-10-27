import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import regenerate_x_draft as subject


class XCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key = "TOPIC-0039::x::en::x"
        self.article_path = "generated/markdown/en/music/example.md"
        self.draft_path = "generated/social/x/en/music/example.txt"
        self.original = "Keep names consistent is easier when the process is clear.\n\nInstall TagWeaver:\nApp Store: https://apps.apple.com/app/id6759609875\n"
        self.item = dict(topic_id="TOPIC-0039", platform="x", language="en", template_id="x",
            category="music", slug="example", is_variant=False, source_status="published",
            publish_after_canonical=False, status="draft", approved_by="", approved_at="",
            post_id="", posted_url="", posted_at="", weighted_length=200,
            draft_path=self.draft_path, canonical_url="https://onnellab.com/blog/en/example/")
        self.other = dict(self.item, platform="linkedin", template_id="linkedin", status="approved",
            approved_by="prior-owner", draft_path="generated/social/linkedin/en/music/example.txt")
        self.put(self.article_path, b"exact article\n")
        self.put(self.draft_path, self.original.encode())
        self.put(self.other["draft_path"], b"Future LinkedIn unchanged\n")
        self.manifest = {"posts": [self.item, self.other], "preserved_extra": 7}
        self.save_manifest()
        self.json("data/manual_publish_state.json", {"version": 1, "done": {}})
        self.json("data/remote_browser_publications.json", {"schema_version": 1, "records": []})
        self.spec = dict(schema_version=1, manual_key=self.key, article_path=self.article_path,
            article_sha256=subject.digest(b"exact article\n"), canonical_url=self.item["canonical_url"],
            original_draft=self.original, original_draft_sha256=subject.digest(self.original.encode()),
            replacement_opening="Choose one verified album title and preserve each track's credited artist.")
        self.correction = self.root / "source.json"
        self.save_spec()

    def put(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def json(self, rel, value):
        self.put(rel, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())

    def save_spec(self):
        self.json("source.json", self.spec)

    def save_manifest(self):
        self.json("generated/social/manifest.json", self.manifest)

    def run_subject(self, write=True):
        return subject.regenerate(self.root, self.correction, write=write)

    def assert_rejected_unchanged(self):
        before = subject.tree_bytes(self.root / "generated/social")
        with self.assertRaises((ValueError, OSError)):
            self.run_subject()
        self.assertEqual(before, subject.tree_bytes(self.root / "generated/social"))

    def test_targeted_write_and_idempotence(self):
        before = subject.tree_bytes(self.root / "generated/social")
        result = self.run_subject()
        after = subject.tree_bytes(self.root / "generated/social")
        self.assertTrue(result["written"])
        changed = {key for key in before if before[key] != after[key]}
        self.assertEqual(changed, {"manifest.json", "x/en/music/example.txt"})
        actual = json.loads(after["manifest.json"])
        self.assertEqual(actual["posts"][1], self.other)
        expected = dict(self.item, weighted_length=result["weighted_length"])
        self.assertEqual(actual["posts"][0], expected)
        body = after["x/en/music/example.txt"]
        self.assertEqual(body.decode().partition("\n\n")[2], self.original.partition("\n\n")[2])
        self.assertEqual(result["draft_sha256"], subject.digest(body))
        self.assertEqual(result["posted_body_sha256"], subject.digest(body.removesuffix(b"\n")))
        self.assertFalse(self.run_subject()["changed"])
        self.assertEqual(after, subject.tree_bytes(self.root / "generated/social"))

    def test_dry_run_no_write(self):
        before = subject.tree_bytes(self.root / "generated/social")
        result = self.run_subject(False)
        self.assertTrue(result["changed"])
        self.assertFalse(result["written"])
        self.assertEqual(before, subject.tree_bytes(self.root / "generated/social"))

    def test_failed_unposted_draft_preserves_error(self):
        self.item.update(status="failed", error="previous failure", retry_count=2)
        self.save_manifest()
        self.run_subject()
        got = subject.load_json(self.root / "generated/social/manifest.json")["posts"][0]
        self.assertEqual((got["status"], got["error"], got["retry_count"]), ("failed", "previous failure", 2))

    def test_manifest_unsafe_fields(self):
        for field, value in [("platform", "linkedin"), ("language", "ko"), ("template_id", "x_question"),
                ("is_variant", True), ("source_status", "scheduled"), ("publish_after_canonical", True),
                ("status", "posted"), ("status", "approved"), ("approved_by", "owner"),
                ("approved_at", "2026"), ("post_id", "123"), ("posted_url", "https://x.com/onnellab/status/123"),
                ("posted_at", "2026"), ("draft_path", "../escape"), ("canonical_url", "https://evil.test/")]:
            with self.subTest(field=field, value=value):
                old = self.item.get(field)
                self.item[field] = value
                self.save_manifest()
                self.assert_rejected_unchanged()
                self.item[field] = old

    def test_source_invalid_fields(self):
        for field, value in [("schema_version", 2), ("manual_key", "TOPIC-0039::linkedin::en::linkedin"),
                ("article_path", "../escape"), ("article_sha256", "0" * 64),
                ("original_draft_sha256", "0" * 64), ("canonical_url", "https://evil.test/"),
                ("replacement_opening", "Too short."), ("replacement_opening", "Bad\n" + "x" * 40 + "."),
                ("replacement_opening", "An incomplete opening with an ellipsis..."),
                ("replacement_opening", "A different link https://evil.test belongs elsewhere."),
                ("replacement_opening", "x" * 200 + ".")]:
            with self.subTest(field=field):
                old = self.spec[field]
                self.spec[field] = value
                self.save_spec()
                self.assert_rejected_unchanged()
                self.spec[field] = old

    def test_unknown_schema_field(self):
        self.spec["approval"] = True
        self.save_spec()
        self.assert_rejected_unchanged()

    def test_original_crlf_rejected(self):
        self.spec["original_draft"] = self.original.replace("\n", "\r\n")
        self.save_spec()
        self.assert_rejected_unchanged()

    def test_changed_draft_rejected(self):
        self.put(self.draft_path, b"Someone else's new copy\n")
        self.assert_rejected_unchanged()

    def test_duplicate_manifest_identity(self):
        self.manifest["posts"].append(dict(self.item))
        self.save_manifest()
        self.assert_rejected_unchanged()

    def test_duplicate_source_json_key(self):
        self.correction.write_text(self.correction.read_text().replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,'))
        self.assert_rejected_unchanged()

    def test_legacy_done_blocks_rewrite(self):
        self.json("data/manual_publish_state.json", {"version": 1, "done": {self.key: {"posted_url": "https://x.com/onnellab"}}})
        self.assert_rejected_unchanged()

    def test_new_and_processed_receipts_block_rewrite(self):
        for status in ("new", "processed"):
            with self.subTest(status=status):
                self.json("data/remote_browser_publications.json", {"schema_version": 1, "records": [
                    {"manual_key": self.key, "platform": "x", "status": status, "posted_url": "https://x.com/onnellab/status/123"}]})
                self.assert_rejected_unchanged()

    def test_missing_history_not_treated_as_empty(self):
        (self.root / "data/manual_publish_state.json").unlink()
        self.assert_rejected_unchanged()

    def test_symlink_draft_rejected(self):
        p = self.root / self.draft_path
        p.unlink()
        p.symlink_to(self.correction)
        with self.assertRaises(subject.CorrectionError):
            self.run_subject()

    def test_noncanonical_manifest_preserved(self):
        self.put("generated/social/manifest.json", json.dumps(self.manifest).encode())
        self.assert_rejected_unchanged()

    def test_stage_write_failure_rolls_back(self):
        original_write = Path.write_bytes
        def fail(path, data):
            if ".x-correction-stage-" in str(path):
                raise OSError("injected stage failure")
            return original_write(path, data)
        with patch.object(Path, "write_bytes", fail):
            self.assert_rejected_unchanged()
        self.assertFalse(list((self.root / "generated").glob(".x-correction-*")))

    def test_swap_failure_rolls_back(self):
        original_rename = Path.rename
        def fail(path, target):
            if path.name.startswith(".x-correction-stage-"):
                raise OSError("injected commit failure")
            return original_rename(path, target)
        with patch.object(Path, "rename", fail):
            self.assert_rejected_unchanged()
        self.assertFalse(list((self.root / "generated").glob(".x-correction-*")))

    def test_swap_and_rollback_failure_preserves_only_original(self):
        before = subject.tree_bytes(self.root / "generated/social")
        original_rename = Path.rename
        def fail(path, target):
            if path.name.startswith((".x-correction-stage-", ".x-correction-backup-")):
                raise OSError("injected commit and rollback failure")
            return original_rename(path, target)
        with patch.object(Path, "rename", fail):
            with self.assertRaisesRegex(subject.CorrectionError, "HOLD:.*original preserved"):
                self.run_subject()
        backups = list((self.root / "generated").glob(".x-correction-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(subject.tree_bytes(backups[0]), before)
        self.assertFalse((self.root / "generated/social").exists())
        self.assertFalse(list((self.root / "generated").glob(".x-correction-stage-*")))


if __name__ == "__main__":
    unittest.main()
