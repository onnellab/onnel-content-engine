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


class RoutinePushLifecycle(unittest.TestCase):
    def rows(self, segra_state="scheduled", research_state="published"):
        rows = []
        for name, state in (("segra-working-copy", segra_state),
                            ("research-source-notes", research_state)):
            category, slug = selector.PROFILES[name]
            for locale, topic_id in selector.REGISTERED_IDS[name].items():
                rows.append(dict(
                    id=topic_id, slug=slug, category=category, primary_language=locale,
                    canonical_path=f"generated/markdown/{locale}/{category}/{slug}.md",
                    status=state, review_required="true",
                    scheduled_at="" if state == "review" else "2026-11-02T09:00:00+09:00",
                    published_at="2026-11-02T09:00:00+09:00" if state == "published" else "",
                    published_url=f"https://onnellab.com/blog/{locale.lower()}/{slug}/"
                                  if state == "published" else ""))
        return rows

    def result(self, rows, **kwargs):
        return selector.selection_environment(rows, ref="refs/heads/main", event="push", **kwargs)

    def test_complete_inactive_bundles_report_no_work_without_mutation(self):
        rows = self.rows()
        before = copy.deepcopy(rows)
        self.assertEqual(self.result(rows),
                         "PREVIEW_REQUIRED=false\nPREVIEW_RESULT=no_work\n"
                         "SEGRA_PREVIEW=false\nVAULTXT_PREVIEW=false\nTAGWEAVER_PREVIEW=false")
        self.assertEqual(rows, before)

    def test_valid_review_selects_actual_candidate(self):
        self.assertIn("PREVIEW_REQUIRED=true", self.result(self.rows("review")))
        self.assertIn("SEGRA_PREVIEW=true", self.result(self.rows("review")))

    def test_manual_other_events_and_refs_stay_fail_closed(self):
        for event, ref in (("workflow_dispatch", "refs/heads/main"),
                           ("pull_request", "refs/heads/main"),
                           ("push", "refs/heads/other"), ("", "")):
            with self.subTest(event=event, ref=ref), self.assertRaises(ValueError):
                selector.selection_environment(self.rows(), ref=ref, event=event)

    def test_explicit_candidates_and_verification_refs_are_never_no_work(self):
        for name in selector.PROFILES:
            self.assertIn("PREVIEW_REQUIRED=true", self.result(self.rows(), requested=name))
        for ref in selector.REFS:
            self.assertIn("PREVIEW_REQUIRED=true",
                          selector.selection_environment(self.rows(), ref=ref, event="push"))

    def test_missing_partial_duplicate_identity_and_mixed_states_fail(self):
        for mode in ("missing", "partial", "duplicate", "id", "category", "path",
                     "mixed", "unknown", "review_required"):
            rows = self.rows()
            if mode == "missing": rows = rows[9:]
            elif mode == "partial": rows.pop()
            elif mode == "duplicate": rows[-1] = dict(rows[-2])
            elif mode == "id": rows[-1]["id"] = "TOPIC-9999"
            elif mode == "category": rows[-1]["category"] = "media"
            elif mode == "path": rows[-1]["canonical_path"] = "../outside"
            elif mode == "mixed": rows[-1]["status"] = "scheduled"
            elif mode == "unknown": rows[-1]["status"] = "archived"
            else: rows[-1]["review_required"] = "false"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.result(rows)

    def test_invalid_dates_and_publication_fields_fail(self):
        for key, value in (("scheduled_at", ""), ("scheduled_at", "not-a-date"),
                           ("scheduled_at", "2026-11-02T09:00:00"),
                           ("scheduled_at", "2026-11-03T09:00:00+09:00"),
                           ("published_at", "2026-11-02T09:00:00+09:00"),
                           ("published_url", "https://example.com/")):
            rows = self.rows()
            rows[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.result(rows)

    def test_malformed_published_bundle_fails_even_with_eligible_review(self):
        for key, value in (("published_at", ""), ("published_at", "invalid"),
                           ("published_at", "2026-11-01T09:00:00+09:00"),
                           ("published_url", "https://example.com/")):
            rows = self.rows("review")
            rows[-1][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.result(rows)

    def test_dated_review_and_missing_date_key_fail(self):
        for missing in (False, True):
            rows = self.rows("review")
            if missing: del rows[0]["published_at"]
            else: rows[0]["scheduled_at"] = "2026-11-02T09:00:00+09:00"
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.result(rows)

    def test_workflow_gates_all_render_steps_but_retains_boundary_tests(self):
        import yaml
        workflow = yaml.load((ROOT / ".github/workflows/blog-preview.yml").read_text(),
                             Loader=yaml.BaseLoader)
        steps = {step["name"]: step for step in workflow["jobs"]["preview"]["steps"]}
        guarded = (
            "Install existing publisher renderer dependencies",
            "Validate research source notes with actual native gates in a disposable engine copy",
            "Validate VaultXT with actual native gates in a disposable engine copy",
            "Validate TagWeaver with actual native gates in a disposable engine copy",
            "Validate Segra with actual native gates in a disposable engine copy",
            "Audit locked homepage dependencies", "Install locked homepage dependencies",
            "Verify summary content preservation and existing Astro template contracts",
            "Overlay candidate only in disposable checkout", "Build pinned Astro templates and styles",
            "Install existing homepage test browser",
            "Check desktop and mobile and capture every page", "Retain bounded preview evidence")
        for name in guarded:
            with self.subTest(step=name):
                self.assertIn("env.PREVIEW_REQUIRED == 'true'", steps[name]["if"])
        self.assertNotIn("if", steps["Validate overlay boundaries and source checksums"])
        self.assertNotIn("if", steps["Verify tracked source remains unchanged"])
        self.assertEqual(steps["Record explicit no-preview result"]["if"],
                         "env.PREVIEW_RESULT == 'no_work'")
        self.assertIn("not a render or page-validation pass",
                      steps["Record explicit no-preview result"]["run"])
        self.assertIn('--event "$GITHUB_EVENT_NAME"',
                      steps["Select eligible nonpublishing preview candidate"]["run"])

if __name__ == "__main__":
    unittest.main()
