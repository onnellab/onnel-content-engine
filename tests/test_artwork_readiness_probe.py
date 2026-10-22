"""Regression tests for non-authorizing, read-only artwork source-drift reports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import artwork_readiness_probe as audit


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReadinessProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.project = self.repo / "demo"
        self.bundle = self.project / audit.VENDORED
        self.bundle.mkdir(parents=True)
        (self.project / "pubspec.yaml").write_text("name: demo\n")
        adapter = self.project / audit.ROOT_ADAPTER
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_bytes(b"reviewed shim")
        self.ledger = {
            "repository": "template/repo",
            "source_directory": "template/assets/store_promo",
            "root_adapter": {"sha256": digest(b"reviewed shim")},
            "bundles": {"approved": {"source_commits": ["expectedsource"], "sha256": {
                "one.py": digest(b"canonical one"), "two.svg": digest(b"canonical two")
            }}},
        }
        (self.bundle / "one.py").write_bytes(b"canonical one")
        (self.bundle / "two.svg").write_bytes(b"canonical two")
        self.metadata = {
            "repository": "template/repo",
            "source_directory": "template/assets/store_promo",
            "commit": "expectedsource",
            "sha256": self.ledger["bundles"]["approved"]["sha256"],
            "preserved_safety_hardening": [],
        }
        self.save_metadata()
        self.paths = ["demo/pubspec.yaml", "demo/release/artwork.json"]

    def save_metadata(self) -> None:
        (self.bundle / "TEMPLATE_SOURCE.json").write_text(json.dumps(self.metadata))

    def scan(self):
        with patch.object(audit, "ROOT_ADAPTER_SHA256", digest(b"reviewed shim")):
            return audit.probe(self.repo, "demo", paths=self.paths, ledger=self.ledger)

    def test_exact_source_still_not_release_verified(self) -> None:
        r = self.scan()
        self.assertEqual(r["status"], "data_only_source_conformant_release_unverified")
        self.assertTrue(r["diagnostic_only"])
        self.assertEqual(r["mismatched_files"], [])
        self.assertEqual(r["source_pin"], "approved")
        self.assertFalse(r["blockers"])

    def test_reports_all_drifts_at_once_even_without_inventory(self) -> None:
        self.paths = ["demo/pubspec.yaml"]
        (self.bundle / "one.py").write_bytes(b"customized")
        (self.bundle / "two.svg").unlink()
        (self.bundle / "extra.py").write_bytes(b"unreviewed")
        self.metadata["sha256"]["one.py"] = digest(b"unreviewed")
        self.save_metadata()
        r = self.scan()
        self.assertEqual(r["status"], "data_only_blocked")
        self.assertEqual(r["mismatched_files"], ["one.py"])
        self.assertEqual(r["missing_files"], ["two.svg"])
        self.assertEqual(r["unexpected_files"], ["extra.py"])
        self.assertIn("missing_tracked_inventory", r["blockers"])
        self.assertIn("bundle_metadata_mismatch", r["blockers"])

    def test_unrecognized_pin_does_not_trust_self_declared_hashes(self) -> None:
        self.metadata["commit"] = "unknown"
        self.save_metadata()
        r = self.scan()
        self.assertIn("unknown_bundle_source_pin", r["blockers"])
        self.assertNotEqual(r["status"], "data_only_source_conformant_release_unverified")

    def test_missing_metadata_never_claims_clean_source(self) -> None:
        (self.bundle / "TEMPLATE_SOURCE.json").unlink()
        r = self.scan()
        self.assertIn("missing_or_invalid_bundle_metadata", r["blockers"])

    def test_detects_unsafe_symlink_as_hash_mismatch(self) -> None:
        (self.bundle / "one.py").unlink()
        outside = self.repo / "external.py"
        outside.write_bytes(b"canonical one")
        (self.bundle / "one.py").symlink_to(outside)
        r = self.scan()
        self.assertEqual(r["mismatched_files"], ["one.py"])

    def test_candidate_and_review_presence_are_not_approvals(self) -> None:
        self.paths.extend(["demo/release/artwork-candidate.json", "demo/release/artwork-review.json"])
        r = self.scan()
        self.assertEqual(r["candidate"], "tracked_unverified")
        self.assertEqual(r["independent_review"], "tracked_unverified")
        self.assertEqual(r["status"], "data_only_source_conformant_release_unverified")

    def test_ambiguous_project_discovery_never_selects_automatically(self) -> None:
        other = self.repo / "other"
        (other / audit.VENDORED).mkdir(parents=True)
        (other / "pubspec.yaml").write_text("name: demo\n")
        r = audit.probe(self.repo, "demo",
                        paths=["demo/pubspec.yaml", "other/pubspec.yaml"], ledger=self.ledger)
        self.assertEqual(r["matching_project_count"], 2)
        self.assertIn("project_not_unambiguously_discoverable", r["blockers"])


if __name__ == "__main__":
    unittest.main()
