"""Synthetic review fixtures only: no actual image approval, API or upload."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_existing_cover as cover
import aether_single
from short_video_pipeline import file_hash
from test_aether_existing_cover import ExistingCoverTests


class DelegatedReviewTests(ExistingCoverTests):
    def setUp(self):
        super().setUp()
        self.review_path = self.assets / "review.json"
        self.review = {
            "schema_version": 1, "kind": "aether_cover_quality_review", "profile": "aether_inn",
            "title": self.title, "source_sha256": self.spec["sha256"],
            "reviewer_kind": "dot_delegated", "verdict": "accepted",
            "authority_reference": "synthetic_test_only_authority",
            "reviewed_at": "2026-01-01T00:00:00+00:00",
            "checks": dict.fromkeys(("full_resolution", "thumbnail_scale", "song_scene_fit",
                "geometry_materials", "full_bleed", "exact_title", "legibility",
                "no_watermark_or_duplicate_brand"), True),
            "notes": "Synthetic test fixture; no real image was reviewed."
        }

    def enable_review(self):
        self.review_path.write_text(json.dumps(self.review))
        self.spec.update(quality_basis="dot_delegated_visual_v1",
                         quality_review={"path": "review.json", "sha256": file_hash(self.review_path)})
        self.save()

    def test_delegated_result_has_truthful_provenance(self):
        self.enable_review()
        old_ledger = (self.assets / cover.APPROVAL_FILE).read_bytes()
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background"), \
             patch.object(cover, "run_process", side_effect=self.render):
            result = self.imported()
        self.assertEqual(result["model"], "dot_reviewed_existing_cover")
        self.assertEqual(result["layout"], "dot_reviewed_finished_cover")
        self.assertEqual(result["quality_reviewer"], "dot_delegated")
        self.assertEqual(result["quality_review_sha256"], file_hash(self.review_path))
        self.assertEqual(old_ledger, (self.assets / cover.APPROVAL_FILE).read_bytes())
        self.assertEqual(aether_single.policy_for({"cover": result})["cover_provider"], "dot_reviewed_existing_cover")

    def test_legacy_policy_and_result_ignore_injected_internal_key(self):
        baseline = aether_single.policy_for({"cover": {"source_kind": "existing_approved_cover"}})
        self.spec["_validated_quality_provenance"] = {"quality_basis": "dot_delegated_visual_v1"}
        self.save()
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background"), \
             patch.object(cover, "run_process", side_effect=self.render):
            result = self.imported()
        self.assertNotIn("quality_basis", result)
        self.assertEqual(result["model"], "owner_approved_existing_cover")
        self.assertEqual(baseline, aether_single.policy_for({"cover": result}))

    def test_bad_evidence_fields_fail_closed(self):
        mutations = [("schema_version", True), ("kind", "other"), ("profile", "onnellab"),
            ("title", "Other"), ("source_sha256", "0"*64), ("reviewer_kind", "owner"),
            ("verdict", "rejected"), ("verdict", "inconclusive"), ("authority_reference", ""),
            ("reviewed_at", "2026-01-01"), ("reviewed_at", "2999-01-01T00:00:00Z"),
            ("notes", " "), ("notes", "x"*4001)]
        original = copy.deepcopy(self.review)
        for key, value in mutations:
            with self.subTest(key=key, value=str(value)[:40]):
                self.review = {**original, key: value}
                self.enable_review()
                with self.assertRaises(Exception):
                    cover.approved_cover(self.title, self.assets)

    def test_every_visual_check_is_required_exact_boolean(self):
        original = copy.deepcopy(self.review)
        for key in original["checks"]:
            for value in (False, None, 1, "true"):
                self.review = copy.deepcopy(original)
                self.review["checks"][key] = value
                self.enable_review()
                with self.subTest(key=key, value=value), self.assertRaises(Exception):
                    cover.approved_cover(self.title, self.assets)

    def test_delegation_never_overrides_rights_or_quality_rejection(self):
        self.enable_review()
        for key in ("commercial_use_confirmed", "quality_accepted"):
            self.spec[key] = False
            self.save()
            with self.subTest(key=key), self.assertRaises(Exception):
                cover.approved_cover(self.title, self.assets)
            self.spec[key] = True

    def test_no_evidence_or_unknown_basis_or_unbranded_is_rejected(self):
        self.enable_review()
        for field, value in (("quality_review", None), ("quality_basis", "unknown"),
                             ("quality_basis", "owner_attested"), ("kind", "unbranded_background")):
            original = self.spec[field]
            self.spec[field] = value
            self.save()
            with self.subTest(field=field), self.assertRaises(Exception):
                cover.approved_cover(self.title, self.assets)
            self.spec[field] = original

    def test_missing_changed_or_duplicate_review_rejected(self):
        self.enable_review()
        self.review_path.unlink()
        with self.assertRaises(Exception):
            cover.approved_cover(self.title, self.assets)
        self.enable_review()
        self.review_path.write_text("{}")
        with self.assertRaisesRegex(Exception, "hash_mismatch"):
            cover.approved_cover(self.title, self.assets)
        self.review_path.write_text('{"schema_version":1,"schema_version":1}')
        self.spec["quality_review"]["sha256"] = file_hash(self.review_path)
        self.save()
        with self.assertRaisesRegex(Exception, "review_invalid"):
            cover.approved_cover(self.title, self.assets)

    def test_review_path_boundaries_and_size(self):
        self.enable_review()
        for path in ("../review.json", "/tmp/review.json", "review.txt"):
            self.spec["quality_review"]["path"] = path
            self.save()
            with self.subTest(path=path), self.assertRaises(Exception):
                cover.approved_cover(self.title, self.assets)
        self.enable_review()
        other = self.assets / "real.json"
        self.review_path.rename(other)
        self.review_path.symlink_to(other)
        with self.assertRaisesRegex(Exception, "unsafe"):
            cover.approved_cover(self.title, self.assets)
        self.review_path.unlink()
        self.review_path.write_bytes(b"x"*(cover.MAX_REVIEW_BYTES+1))
        self.spec["quality_review"]["sha256"] = file_hash(self.review_path)
        self.save()
        with self.assertRaisesRegex(Exception, "invalid"):
            cover.approved_cover(self.title, self.assets)

    def test_fifo_and_swapped_parent_are_rejected(self):
        self.enable_review()
        self.review_path.unlink()
        os.mkfifo(self.review_path)
        with self.assertRaisesRegex(Exception, "review_invalid"):
            cover.approved_cover(self.title, self.assets)
        self.review_path.unlink()
        self.enable_review()
        folder = self.assets / "reviews"
        folder.mkdir()
        (folder / "proof.json").write_bytes(self.review_path.read_bytes())
        self.spec["quality_review"]["path"] = "reviews/proof.json"
        self.save()
        real_read = cover._read_review
        reads = 0
        def swapping_read(root, relative):
            nonlocal reads
            reads += 1
            if reads == 2:
                folder.rename(self.assets / "moved")
                folder.symlink_to(self.assets / "moved", target_is_directory=True)
            return real_read(root, relative)
        with patch.object(cover, "_read_review", side_effect=swapping_read):
            with self.assertRaises(Exception):
                cover.approved_cover(self.title, self.assets)


if __name__ == "__main__":
    unittest.main()
