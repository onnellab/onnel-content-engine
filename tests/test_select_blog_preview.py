"""Automatic preview selection never resets published or scheduled lifecycle state."""
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
import select_blog_preview as selector
import prepare_segra_preview as segra

def bundle(name, status="review"):
    category, slug = selector.PROFILES[name]
    return [dict(id=f"T-{name}-{i}", slug=slug, category=category, primary_language=l,
                 status=status, review_required="true", scheduled_at="", published_at="", published_url="")
            for i, l in enumerate(sorted(selector.LOCALES))]

class Selection(unittest.TestCase):
    def test_published_old_default_skipped_and_current_review_selected(self):
        rows = bundle("research-source-notes", "published") + bundle("segra-working-copy")
        before = copy.deepcopy(rows)
        self.assertEqual(selector.select_candidate(rows), "segra-working-copy")
        self.assertEqual(rows, before)
    def test_no_eligible_candidate_fails_closed(self):
        for rows in ([], bundle("research-source-notes", "published"),
                     bundle("segra-working-copy", "scheduled")):
            with self.assertRaises(ValueError): selector.select_candidate(rows)
    def test_partial_duplicate_or_dated_review_fails_closed(self):
        for mode in ("partial", "duplicate", "date", "wrong_category"):
            rows = bundle("segra-working-copy")
            if mode == "partial": rows.pop()
            if mode == "duplicate": rows[-1] = dict(rows[0])
            if mode == "date": rows[0]["scheduled_at"] = "2026-11-02T09:00:00+09:00"
            if mode == "wrong_category": rows[0]["category"] = "research"
            with self.subTest(mode=mode), self.assertRaises(ValueError): selector.select_candidate(rows)
    def test_explicit_candidate_respected_even_when_automatic_selection_differs(self):
        rows = bundle("segra-working-copy")
        for name in selector.PROFILES:
            self.assertEqual(selector.select_candidate(rows, name), name)
    def test_verification_ref_keeps_explicit_fixture_path(self):
        for ref, name in selector.REFS.items():
            self.assertEqual(selector.select_candidate([], "auto", ref), name)
    def test_unknown_inputs_never_become_paths_or_environment(self):
        for name in ("../../main", "auto\nX=true", ""):
            with self.assertRaises(ValueError): selector.select_candidate([], name)
            with self.assertRaises(ValueError): selector.environment_lines(name)
    def test_closed_environment_flag_output(self):
        self.assertEqual(selector.environment_lines("segra-working-copy"),
                         "SEGRA_PREVIEW=true\nVAULTXT_PREVIEW=false\nTAGWEAVER_PREVIEW=false")

class RegisteredSegra(unittest.TestCase):
    def fixture(self, root):
        # Only synthesize a historical review state inside an isolated fixture.
        self.assertNotEqual(root.resolve(), ROOT)
        self.assertNotIn(ROOT, root.resolve().parents)
        paths = ["data/topics.csv", "topics/topics.csv", segra.REGISTERED_AUDIT,
                 segra.PREVIEW_DIRECTORY + "/manifest.json",
                 *[segra.PREVIEW_DIRECTORY + "/" + l + ".json" for l in segra.LOCALES],
                 *segra.native_output_paths()]
        for relative in paths:
            p = root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((ROOT / relative).read_bytes())
        # The real queue may legitimately advance to scheduled or published.
        # Keep this unit fixture deterministic without resetting operational data.
        with (root / "data/topics.csv").open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            header, rows = reader.fieldnames, list(reader)
        candidates = [row for row in rows if row["slug"] == segra.SLUG
                      or row["id"] in segra.REGISTERED_IDS.values()]
        self.assertEqual(len(candidates), 9)
        self.assertEqual({(row["primary_language"], row["id"]) for row in candidates},
                         set(segra.REGISTERED_IDS.items()))
        for row in candidates:
            row.update(status="review", scheduled_at="", published_at="", published_url="")
        for relative in ("data/topics.csv", "topics/topics.csv"):
            with (root / relative).open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
    def test_registered_read_only_path_keeps_all_bytes_and_calls_native_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            before = {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch("check_nine_language_publication.check_reviewed_candidates") as gate:
                rows, manifest = segra.validate_registered_candidates(root)
                gate.assert_called_once_with((root / "data/topics.csv").resolve())
            self.assertEqual(len(rows), 9); self.assertEqual(len(manifest["files"]), 72)
            self.assertEqual(before, {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()})
    def test_dated_review_scheduled_and_published_are_rejected_without_reset(self):
        for state in ("review", "scheduled", "published"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); self.fixture(root)
                with (root/"data/topics.csv").open(encoding="utf-8", newline="") as f:
                    reader=csv.DictReader(f); header=reader.fieldnames; rows=list(reader)
                for row in rows:
                    if row["slug"] == segra.SLUG:
                        row["status"] = state
                        row["scheduled_at"] = "2026-11-02T09:00:00+09:00"
                        if state == "published":
                            row["published_at"] = "2026-11-02T09:00:00+09:00"
                            row["published_url"] = (
                                f"https://onnellab.com/blog/{row['primary_language'].lower()}/{segra.SLUG}/")

                for path in ("data/topics.csv", "topics/topics.csv"):
                    with (root/path).open("w",encoding="utf-8",newline="") as f:
                        writer=csv.DictWriter(f,fieldnames=header); writer.writeheader();writer.writerows(rows)
                before = {str(p.relative_to(root)): p.read_bytes()
                          for p in root.rglob("*") if p.is_file()}
                with self.assertRaisesRegex(ValueError,"unscheduled review"):
                    segra.validate_registered_candidates(root)
                self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes()
                                          for p in root.rglob("*") if p.is_file()})
    def test_mutated_artifact_and_mirror_are_rejected(self):
        for relative in (segra.native_output_paths()[0], "topics/topics.csv"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.fixture(root)
                with (root/relative).open("ab") as f: f.write(b"\n")
                with self.assertRaises(ValueError): segra.validate_registered_candidates(root)
    def test_receipt_identity_and_unknown_manifest_paths_are_rejected(self):
        for field in ("slug", "files"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.fixture(root);p=root/segra.REGISTERED_AUDIT
                data=json.loads(p.read_text())
                if field=="slug": data["slug"]="another"
                else: data["automated"]["native_manifest"]["files"][0]["path"]="../outside"
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError): segra.validate_registered_candidates(root)

if __name__ == "__main__":
    unittest.main()
