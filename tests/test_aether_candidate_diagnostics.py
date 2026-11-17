"""Offline candidate diagnostics; all media, queues and providers are fixtures."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_single as single
from aether_single_duration import NEW_SINGLE_DURATION_DIRECTION
from short_video_pipeline import file_hash


class CandidateDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "fixture.mp3"
        self.source.write_bytes(b"fixture-only-not-real-audio" * 100)
        self.row = {"index": 1, "file": str(self.source), "sha256": file_hash(self.source)}
        self.review = Mock(return_value={"accepted": True, "weighted_score": 8.5,
                                        "source_sha256": self.row["sha256"]})

    def failed(self, *, duration=139.434208, rows=None, prior=None):
        with patch.object(single, "audio_duration", return_value=duration):
            with self.assertRaises(single.CandidateSelectionError) as caught:
                single.select_candidate({"candidates": rows if rows is not None else [self.row]},
                                        prior or set(), reviewer=self.review)
        return caught.exception.diagnostic

    def test_below_140_is_duration_rejection_not_audio_quality_failure(self):
        detail = self.failed()
        self.assertEqual("duration", detail["failure_stage"])
        self.assertEqual({"min": 140, "max": 210}, detail["duration_limits_seconds"])
        entry = detail["candidates"][0]
        self.assertEqual(139.434208, entry["duration_seconds"])
        self.assertEqual(["duration_out_of_bounds"], entry["reason_codes"])
        self.assertEqual("not_run_duration_gate", entry["audio_review_state"])
        self.review.assert_not_called()
        self.assertNotIn(str(self.root), json.dumps(detail))

    def test_owner_approved_140_inclusive_boundaries_and_retained_length(self):
        for duration in (140.0, 140.434208, 160.0, 210.0):
            with self.subTest(duration=duration), patch.object(single, "audio_duration", return_value=duration):
                result = single.select_candidate({"candidates": [self.row]}, set(), reviewer=self.review)
                self.assertEqual(duration, result["duration_seconds"])
        for duration in (139.999, 210.001):
            with self.subTest(duration=duration):
                self.assertEqual("duration", self.failed(duration=duration)["failure_stage"])

    def test_missing_invalid_hash_and_changed_file_are_distinct(self):
        cases = [({**self.row, "file": str(self.root / "absent.mp3")}, "candidate_source_missing_or_unsafe"),
                 ({**self.row, "sha256": "invalid"}, "candidate_hash_invalid"),
                 ({**self.row, "sha256": "a" * 64}, "candidate_hash_mismatch")]
        for row, reason in cases:
            with self.subTest(reason=reason):
                detail = self.failed(rows=[row])
                self.assertEqual([reason], detail["candidates"][0]["reason_codes"])
                self.assertEqual("integrity", detail["failure_stage"])
        self.review.assert_not_called()

    def test_exact_duplicate_is_not_bad_quality(self):
        detail = self.failed(prior={self.row["sha256"]})
        self.assertEqual("duplicate", detail["failure_stage"])
        self.review.assert_not_called()

    def test_signal_rejection_keeps_known_reason_not_raw_provider_text(self):
        self.review.return_value = {"accepted": False, "reason_codes": ["audio_clipping", "private/path SECRET", {}]}
        detail = self.failed(duration=180)
        entry = detail["candidates"][0]
        self.assertEqual("rejected", entry["audio_review_state"])
        self.assertEqual(["audio_clipping"], entry["reason_codes"])
        self.assertNotIn("SECRET", json.dumps(detail))

    def test_review_exception_is_unavailable_and_never_exposes_exception(self):
        self.review.side_effect = RuntimeError("Authorization: private fixture")
        detail = self.failed(duration=180)
        self.assertEqual("unavailable", detail["candidates"][0]["audio_review_state"])
        self.assertNotIn("Authorization", json.dumps(detail))

    def test_nonfinite_probe_is_unavailable_not_zero_or_accepted(self):
        for duration in (float("nan"), float("inf"), None, True):
            with self.subTest(duration=duration):
                detail = self.failed(duration=duration)
                self.assertEqual("probe", detail["failure_stage"])
                self.assertNotIn("duration_seconds", detail["candidates"][0])
                json.dumps(detail, allow_nan=False)
        self.review.assert_not_called()

    def test_probe_exception_is_not_leaked(self):
        with patch.object(single, "audio_duration", side_effect=RuntimeError("private fixture")):
            with self.assertRaises(single.CandidateSelectionError) as caught:
                single.select_candidate({"candidates": [self.row]}, set(), reviewer=self.review)
        self.assertEqual("probe", caught.exception.diagnostic["failure_stage"])
        self.assertNotIn("private fixture", json.dumps(caught.exception.diagnostic))

    def test_malformed_review_fails_closed(self):
        for review in (None, {"accepted": "true"}, {"accepted": True, "weighted_score": float("nan")},
                       {"accepted": True, "weighted_score": 11}, {"accepted": True}):
            with self.subTest(review=review):
                self.review.return_value = review
                detail = self.failed(duration=180)
                self.assertEqual(0, detail["accepted_count"])
                self.assertEqual("unavailable", detail["candidates"][0]["audio_review_state"])

    def test_review_hash_must_match_the_original_candidate(self):
        self.review.return_value["source_sha256"] = "b" * 64
        detail = self.failed(duration=180)
        self.assertEqual(["audio_review_source_mismatch"], detail["candidates"][0]["reason_codes"])

    def test_source_changed_during_review_is_not_selected(self):
        def changed(path):
            path.write_bytes(b"changed-after-check")
            return {"accepted": True, "weighted_score": 8.5}
        self.review.side_effect = changed
        detail = self.failed(duration=180)
        self.assertEqual(["candidate_source_changed"], detail["candidates"][0]["reason_codes"])

    def test_empty_and_malformed_candidates_are_diagnostic_failures(self):
        for rows, stage in (([], "no_candidates"), ([None], "integrity"), ([{"index": 1}], "integrity")):
            with self.subTest(rows=rows):
                self.assertEqual(stage, self.failed(rows=rows)["failure_stage"])

    def test_reused_diagnostic_does_not_retain_old_failure(self):
        detail = {"failure_stage": "old", "secret": "old"}
        with patch.object(single, "audio_duration", return_value=180):
            single.select_candidate({"candidates": [self.row]}, set(), reviewer=self.review, diagnostics=detail)
        self.assertEqual("accepted", detail["status"])
        self.assertNotIn("failure_stage", detail)
        self.assertNotIn("secret", detail)

    def test_worker_keeps_same_job_and_reuses_retained_audio_without_rebuy(self):
        root = self.root / "queue"
        def fake_music(title, style, *, execute, output_root, slot=None):
            run = output_root / "fixture-run"
            run.mkdir(parents=True)
            audio = run / "candidate-01.mp3"
            audio.write_bytes(self.source.read_bytes())
            result = {"state": "generated", "estimated_cost_usd": .08,
                      "cost_basis": "provider_base_excluding_tax_and_currency_adjustments",
                      "candidates": [{"index": 1, "file": str(audio), "sha256": file_hash(audio)}]}
            (run / "manifest.json").write_text(json.dumps(result))
            return result
        generator = Mock(side_effect=fake_music)
        cover = Mock(side_effect=AssertionError("must not render cover"))
        renderer = Mock(side_effect=AssertionError("must not render video"))
        kwargs = dict(slot="2099-09-26", title="Fixture New Ridge", style="Warm frontier travel",
                      lane="frontier_surge", execute=True, publish=False,
                      music_generator=generator, cover_generator=cover, renderer=renderer)
        with patch.object(single, "audio_duration", return_value=139.434208), patch.object(single, "review_audio") as review, patch.object(single.paid_guard, "require_no_unsettled_intents"):
            failures = []
            for _ in range(2):
                with self.assertRaises(single.CandidateSelectionError) as caught:
                    single.worker(root, **kwargs)
                failures.append(caught.exception.worker_result)
            review.assert_not_called()
        self.assertEqual(1, generator.call_count)
        self.assertEqual(failures[0]["job_id"], failures[1]["job_id"])
        for result in failures:
            self.assertEqual(1, result["generation_count"])
            self.assertEqual(.08, result["estimated_cost_usd"])
            self.assertIsNone(result["video_id"])
            self.assertFalse(result["publication_complete"])
        saved = json.loads((root / "queue.json").read_text())
        self.assertEqual(1, len(saved["jobs"]))
        job = next(iter(saved["jobs"].values()))
        self.assertEqual("duration", job["candidate_selection"]["failure_stage"])
        self.assertIsNone(job["music"])
        self.assertFalse(job["upload_eligible"])
        cover.assert_not_called()
        renderer.assert_not_called()

    def test_cli_reports_safe_diagnostics_and_original_job_identity(self):
        error = single.CandidateSelectionError("aether_single_no_accepted_candidate", {"failure_stage": "duration"})
        error.worker_result = {"job_id": "fixture-job", "slot": "2099-09-26", "generation_count": 1,
                               "estimated_cost_usd": .08, "publication_complete": False}
        output = io.StringIO()
        with patch.object(sys, "argv", ["aether_single.py", "worker"]), patch.object(single, "worker", side_effect=error), redirect_stdout(output):
            self.assertEqual(2, single.main())
        payload = json.loads(output.getvalue())
        self.assertEqual("fixture-job", payload["job_id"])
        self.assertEqual("duration", payload["candidate_selection"]["failure_stage"])
        self.assertEqual(.08, payload["estimated_cost_usd"])

    def test_future_duration_request_fits_existing_style_limits(self):
        import aether_daily_local as daily
        from aether_cover import lane_direction
        registry = json.loads((daily.REPO / "data/aether_single_lanes.json").read_text())
        for row in registry["lanes"]:
            style = lane_direction(row["id"]) + daily.COMMON_STYLE + NEW_SINGLE_DURATION_DIRECTION
            self.assertLessEqual(len(style), 1200)
            self.assertIn("180-184-second", style)
        self.assertNotIn("180-184-second", daily.COMMON_STYLE)


if __name__ == "__main__":
    unittest.main()
