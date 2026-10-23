"""Synthetic boundary tests; no live queue, frozen articles, or external execution."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_research_preview as preview
from topic_management import TOPIC_HEADER


class RegisteredResearchPreview(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.stage = self.base / "stage"
        self.output = self.base / "output"
        self.stage.mkdir()
        self.output.mkdir()
        for name in preview.COPY_ROOTS:
            path = self.stage / name
            if name.endswith(".md"):
                path.write_text("synthetic fixture\n", encoding="utf-8")
            else:
                path.mkdir()
        self.rows = []
        for locale, topic_id in preview.REGISTERED_IDS.items():
            row = dict.fromkeys(TOPIC_HEADER, "")
            row.update(id=topic_id, status="review", category=preview.CATEGORY,
                       slug=preview.SLUG, primary_language=locale,
                       review_required="true",
                       canonical_path=f"generated/markdown/{locale}/{preview.CATEGORY}/{preview.SLUG}.md")
            self.rows.append(row)
        self.write_rows()
        source_hashes = {}
        for locale in preview.LOCALES:
            relative = f"preview/research-source-notes/{locale}.json"
            raw = (json.dumps({"synthetic": locale}) + "\n").encode()
            self.put(relative, raw)
            source_hashes[locale] = preview.digest(raw)
        self.put_json("preview/research-source-notes/reviewed-source-sha256.json",
                      source_hashes)
        # Historical state is deliberately irrelevant to the registered branch.
        self.put_json("preview/research-source-notes/manifest.json",
                      {"state": "HISTORICAL_SNAPSHOT_NOT_A_CURRENT_GATE"})
        files = []
        for relative in preview.native_output_paths():
            raw = ("synthetic artifact: " + relative + "\n").encode()
            if relative.endswith("/review.json"):
                locale = relative.split("/")[2]
                raw = (json.dumps({"version": 4,
                                   "topic_id": preview.REGISTERED_IDS[locale]}) + "\n").encode()
            self.put(relative, raw)
            files.append(preview.native_entry(relative, raw))
        self.audit = {
            "schema": 1, "kind": "review_supply_audit_not_publication_receipt",
            "slug": preview.SLUG, "category": preview.CATEGORY, "stage": "review",
            "scheduled_at": None, "published_at": None, "published_url": None,
            "queue_ids": list(preview.REGISTERED_IDS.values()),
            "reviewed_source_digests": source_hashes, "reviewed_files": files,
        }
        self.write_audit()
        gate = patch("check_nine_language_publication.check_reviewed_candidates",
                     return_value=1)
        self.current_gate = gate.start()
        self.addCleanup(gate.stop)

    def put(self, relative, raw):
        path = self.stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def put_json(self, relative, value):
        self.put(relative, (json.dumps(value) + "\n").encode())

    def write_audit(self):
        self.put_json(preview.REGISTERED_AUDIT, self.audit)

    def write_rows(self):
        path = self.stage / "data/topics.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TOPIC_HEADER)
            writer.writeheader()
            writer.writerows(self.rows)
        self.put("topics/topics.csv", path.read_bytes())

    def validate(self):
        return preview.validate_registered_candidates(self.stage)

    def refresh_audit_entry(self, relative):
        for index, entry in enumerate(self.audit["reviewed_files"]):
            if entry["path"] == relative:
                self.audit["reviewed_files"][index] = preview.native_entry(
                    relative, (self.stage / relative).read_bytes())
                self.write_audit()
                return
        self.fail("Fixture entry not found")

    def test_valid_registered_read_is_nonmutating(self):
        before = preview.source_inventory(self.stage)
        candidates, manifest = self.validate()
        self.assertEqual([r["id"] for r in candidates],
                         list(preview.REGISTERED_IDS.values()))
        self.assertEqual(len(manifest["files"]), 72)
        self.assertEqual(preview.source_inventory(self.stage), before)
        self.current_gate.assert_called_once_with(self.stage / "data/topics.csv")

    def test_invalid_audit_identity_fails(self):
        original = copy.deepcopy(self.audit)
        for field, value in (("schema", True), ("kind", "receipt"),
                             ("slug", "other"), ("category", "other"),
                             ("stage", "scheduled"), ("scheduled_at", "tomorrow"),
                             ("published_at", "yesterday"), ("published_url", "https://example.org"),
                             ("queue_ids", list(reversed(original["queue_ids"])))):
            with self.subTest(field=field):
                self.audit = copy.deepcopy(original)
                self.audit[field] = value
                self.write_audit()
                with self.assertRaises(ValueError):
                    self.validate()
        self.current_gate.assert_not_called()

    def test_candidate_identity_and_state_fail_closed(self):
        original = copy.deepcopy(self.rows)
        mutations = [
            lambda r: r.pop(),
            lambda r: r.append(dict(r[0])),
            lambda r: r[0].update(id="TOPIC-9999"),
            lambda r: r[0].update(primary_language="ko"),
            lambda r: r[0].update(category="other"),
            lambda r: r[0].update(slug="other"),
            lambda r: r[0].update(canonical_path="../escape"),
            lambda r: r[0].update(review_required="false"),
            *[lambda r, status=status: r[0].update(status=status)
              for status in ("idea", "draft", "scheduled", "published")],
            *[lambda r, key=key: r[0].update({key: "unexpected"})
              for key in ("related_apps", "scheduled_at", "published_at", "published_url")],
            lambda r: r.append(dict(r[0], id="TOPIC-9999", category="other")),
            lambda r: r.append(dict(r[0], slug="another-slug")),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                self.rows = copy.deepcopy(original)
                mutate(self.rows)
                self.write_rows()
                with self.assertRaises(ValueError):
                    self.validate()
        self.current_gate.assert_not_called()

    def test_queue_mirror_mismatch_fails(self):
        self.put("topics/topics.csv", b"different")
        with self.assertRaisesRegex(ValueError, "mirror"):
            self.validate()

    def test_reviewed_source_changes_fail(self):
        for locale in preview.LOCALES:
            relative = f"preview/research-source-notes/{locale}.json"
            original = (self.stage / relative).read_bytes()
            self.put(relative, original + b" ")
            with self.subTest(locale=locale), self.assertRaisesRegex(ValueError, "source digest"):
                self.validate()
            self.put(relative, original)
        self.current_gate.assert_not_called()

    def test_every_native_file_is_hash_bound_before_gate(self):
        for relative in preview.native_output_paths():
            path = self.stage / relative
            raw = path.read_bytes()
            path.write_bytes(raw + b" ")
            with self.subTest(path=relative), self.assertRaisesRegex(ValueError, "fingerprint"):
                self.validate()
            path.write_bytes(raw)
        self.current_gate.assert_not_called()

    def test_bad_manifest_entries_fail(self):
        original = copy.deepcopy(self.audit)
        mutations = [
            lambda files: files.pop(),
            lambda files: files.append(dict(files[0])),
            lambda files: files.__setitem__(1, dict(files[0])),
            lambda files: files[0].update(path="../escape"),
            lambda files: files[0].update(byte_length=True),
            lambda files: files[0].update(byte_length=1),
            lambda files: files[0].update(sha256="0" * 64),
            lambda files: files[0].update(git_blob_sha1="0" * 40),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                self.audit = copy.deepcopy(original)
                mutate(self.audit["reviewed_files"])
                self.write_audit()
                with self.assertRaises(ValueError):
                    self.validate()

    def test_duplicate_json_keys_and_symlinks_fail(self):
        self.put(preview.REGISTERED_AUDIT, b'{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.validate()
        self.write_audit()
        relative = preview.native_output_paths()[0]
        path = self.stage / relative
        path.unlink()
        path.symlink_to(self.stage / "README.md")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.validate()

    def test_old_review_fails_even_with_matching_audit(self):
        relative = next(p for p in preview.native_output_paths() if p.endswith("/review.json"))
        self.put_json(relative, {"version": 3, "topic_id": "TOPIC-0037"})
        self.refresh_audit_entry(relative)
        with self.assertRaisesRegex(ValueError, "version 4"):
            self.validate()
        self.current_gate.assert_not_called()

    def test_current_fingerprint_gate_cannot_be_replaced_by_audit(self):
        relative = preview.native_output_paths()[0]
        self.put(relative, b"tampered article with matching audit\n")
        self.refresh_audit_entry(relative)
        # Native verifier owns score, mandatory-check and fingerprint semantics.
        for reason in ("stale fingerprint", "score 9.0", "mandatory check failed"):
            with self.subTest(reason=reason):
                self.current_gate.side_effect = ValueError(reason)
                with self.assertRaisesRegex(ValueError, reason):
                    self.validate()

    def test_gate_writes_are_isolated_and_failure_propagates(self):
        before = preview.source_inventory(self.stage)
        def native_gates(gate_stage, output):
            self.assertNotEqual(gate_stage, self.stage)
            self.assertEqual(output, self.output)
            path = next(p for p in preview.native_output_paths() if p.endswith("/review.json"))
            (gate_stage / path).write_bytes(b"regenerated review")
        with patch.object(preview, "run_gates", side_effect=native_gates) as gates:
            preview.run_registered_gates(self.stage, self.output)
            gates.assert_called_once()
        self.assertEqual(preview.source_inventory(self.stage), before)
        with patch.object(preview, "run_gates", side_effect=ValueError("native failure")):
            with self.assertRaisesRegex(ValueError, "native failure"):
                preview.run_registered_gates(self.stage, self.output)
        self.assertEqual(preview.source_inventory(self.stage), before)

    def test_registered_collection_copies_original_72_without_alias_writes(self):
        candidates, manifest = self.validate()
        before = preview.source_inventory(self.stage)
        with patch.object(preview.shutil, "copyfile", side_effect=AssertionError("alias write")), \
                patch("topic_management.TopicStore.write", side_effect=AssertionError("queue write")), \
                patch("prepare_blog_preview.validate_bundle"):
            preview.collect(self.stage, self.output, candidates, [],
                            registered_manifest=manifest)
        self.assertEqual(preview.verified_native_manifest(self.output), manifest)
        for entry in manifest["files"]:
            relative = entry["path"]
            self.assertEqual((self.output / "artifacts" / relative).read_bytes(),
                             (self.stage / relative).read_bytes())
        # Ignore interpreter import caches, not any queue or registered artifact.
        after = preview.source_inventory(self.stage)
        for relative, expected in before.items():
            self.assertEqual(after[relative], expected)
        evidence = json.loads((self.output / "candidate-topic-rows.json").read_text())
        self.assertIs(evidence["ids_reserved"], True)
        self.assertIs(evidence["live_queue_modified"], False)
        self.assertEqual(evidence["idea_seeds"], [])

    def test_missing_social_alias_fails_without_regeneration(self):
        relative = next(p for p in preview.native_output_paths() if p.endswith("/social-card.svg"))
        (self.stage / relative).unlink()
        with patch.object(preview.shutil, "copyfile", side_effect=AssertionError("alias write")):
            with self.assertRaisesRegex(ValueError, "Missing"):
                self.validate()

    def worker_marker(self):
        original = self.base / "original"
        original.mkdir()
        output = original / "preview-evidence/research-source-notes"
        output.mkdir(parents=True)
        self.put_json(preview.MARKER, {"source": str(original), "output": str(output)})
        return output

    def test_registered_worker_never_enters_draft_or_mutation_path(self):
        output = self.worker_marker()
        with patch.object(preview, "ROOT", self.stage), \
                patch.object(preview, "validate_drafts", side_effect=AssertionError("draft")), \
                patch.object(preview, "stage_topics", side_effect=AssertionError("queue write")), \
                patch("topic_management.TopicStore.write", side_effect=AssertionError("queue write")), \
                patch.object(preview, "materialize_candidates", side_effect=AssertionError("generate")), \
                patch.object(preview, "run_registered_gates") as gates, \
                patch.object(preview, "collect") as collect:
            preview.stage_worker()
        gates.assert_called_once_with(self.stage, output)
        self.assertEqual(collect.call_args.kwargs["registered_manifest"]["files"],
                         self.audit["reviewed_files"])

    def test_invalid_registered_audit_never_falls_back(self):
        self.worker_marker()
        self.audit["stage"] = "scheduled"
        self.write_audit()
        with patch.object(preview, "ROOT", self.stage), \
                patch.object(preview, "validate_drafts", side_effect=AssertionError("fallback")):
            with self.assertRaises(ValueError):
                preview.stage_worker()

    def test_missing_audit_keeps_strict_draft_branch(self):
        self.worker_marker()
        (self.stage / preview.REGISTERED_AUDIT).unlink()
        with patch.object(preview, "ROOT", self.stage), \
                patch.object(preview, "validate_drafts", return_value={}), \
                patch.object(preview, "run_registered_gates", side_effect=AssertionError("registered")):
            with self.assertRaisesRegex(ValueError, "no longer an idea"):
                preview.stage_worker()


    def test_unsafe_or_malformed_present_audit_never_falls_back(self):
        self.worker_marker()
        path = self.stage / preview.REGISTERED_AUDIT
        original = path.read_bytes()
        cases = (
            lambda: path.mkdir(),
            lambda: path.symlink_to(self.base / "missing-audit"),
            lambda: path.write_bytes(b"{"),
            lambda: path.write_bytes(b'{"schema":1,"schema":1}'),
        )
        for index, create in enumerate(cases):
            with self.subTest(index=index):
                path.unlink()
                create()
                try:
                    with patch.object(preview, "ROOT", self.stage), \
                            patch.object(preview, "validate_drafts", side_effect=AssertionError("fallback")):
                        with self.assertRaises(ValueError):
                            preview.stage_worker()
                finally:
                    if path.is_dir() and not path.is_symlink():
                        path.rmdir()
                    else:
                        path.unlink()
                    path.write_bytes(original)

    def test_registered_worker_rejects_unsafe_output_and_output_symlink(self):
        output = self.worker_marker()
        marker = preview.read_json(self.stage / preview.MARKER)
        original_marker = dict(marker)
        marker["output"] = str(self.stage / "unsafe-output")
        self.put_json(preview.MARKER, marker)
        with patch.object(preview, "ROOT", self.stage):
            with self.assertRaisesRegex(ValueError, "evidence destination"):
                preview.stage_worker()
        self.put_json(preview.MARKER, original_marker)
        output.rmdir()
        output.symlink_to(self.stage, target_is_directory=True)
        with patch.object(preview, "ROOT", self.stage):
            with self.assertRaisesRegex(ValueError, "evidence destination"):
                preview.stage_worker()

    def test_post_gate_registered_artifact_mutation_fails(self):
        relative = preview.native_output_paths()[0]
        def mutate_original(gate_stage, output):
            (self.stage / relative).write_bytes(b"changed after initial validation")
        with patch.object(preview, "run_gates", side_effect=mutate_original):
            with self.assertRaisesRegex(ValueError, "Registered stage changed"):
                preview.run_registered_gates(self.stage, self.output)

    def test_registered_collection_forbids_seeds_before_output(self):
        candidates, manifest = self.validate()
        with patch("topic_management.TopicStore.write", side_effect=AssertionError("queue write")):
            with self.assertRaisesRegex(ValueError, "collection evidence mismatch"):
                preview.collect(self.stage, self.output, candidates,
                                [{"status": "idea"}], registered_manifest=manifest)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
