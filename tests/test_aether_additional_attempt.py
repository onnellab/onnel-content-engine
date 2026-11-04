"""An explicit extra attempt is bounded; old evidence is never erased."""
from contextlib import contextmanager
import hashlib
import json
from unittest.mock import patch
import unittest

import aether_additional_attempt as extra
import aether_manual_release as release
import aether_paid_guard as guard
import aether_single as single
from short_video_pipeline import atomic_json, VideoError
from test_aether_manual_release import fixture


@contextmanager
def setup():
    with fixture() as (q, job):
        manual = release.record_request()
        folder = q.root / "jobs" / job["id"]
        run = folder / "lyria" / extra.PRIOR_RUN
        run.mkdir(parents=True)
        prior = run / "manifest.json"
        atomic_json(prior, {"state": "request_started", "dispatch_started": True, "candidates": []})
        sha = hashlib.sha256(prior.read_bytes()).hexdigest()
        expected = {**extra.EXPECTED, "prior_manifest_sha256": sha,
                    "manual_request_sha256": manual["request_sha256"]}
        job.update(status="blocked", error="lyria_audio_missing")
        atomic_json(q.state_path, {"schema_version": 1, "jobs": {job["id"]: job}})
        with patch.object(extra, "ROOT", q.root), patch.object(extra, "PRIOR_SHA", sha), \
             patch.object(extra, "REQUEST_SHA", manual["request_sha256"]), \
             patch.object(extra, "EXPECTED", expected):
            yield q, job, prior, {k: manual[k] for k in ("job_id", "request_sha256")}


class AdditionalAttemptTests(unittest.TestCase):
    def test_missing_approval_remains_uncertain(self):
        with setup() as (q, job, prior, manual):
            with self.assertRaisesRegex(VideoError, "generation_uncertain"):
                guard.require_no_unsettled_intents(single_root=q.root)
            self.assertFalse(extra.acknowledged_prior(prior))

    def test_acceptance_preserves_prior_bytes_and_uncertain_cost(self):
        with setup() as (q, job, prior, manual):
            before, queue = prior.read_bytes(), q.state_path.read_bytes()
            approval = extra.record_approval()
            self.assertEqual(approval, extra.record_approval())
            self.assertEqual("unknown_accepted_by_owner", approval["prior_charge_status"])
            self.assertEqual(before, prior.read_bytes())
            self.assertEqual(queue, q.state_path.read_bytes())
            guard.require_no_unsettled_intents(single_root=q.root)
            self.assertIsNone(single.recover_generated_result(prior.parent.parent.parent))

    def test_exact_one_extra_claim_and_no_third(self):
        with setup() as (q, job, prior, manual):
            extra.record_approval()
            first = extra.claim_additional(prior.parent.parent, manual)
            self.assertEqual(job["id"], first["job_id"])
            with self.assertRaisesRegex(VideoError, "already_consumed"):
                extra.claim_additional(prior.parent.parent, manual)

    def test_other_pending_attempt_is_not_acknowledged(self):
        with setup() as (q, job, prior, manual):
            extra.record_approval()
            second = prior.parent.parent / "second" / "manifest.json"
            second.parent.mkdir()
            atomic_json(second, {"state": "request_started", "dispatch_started": True})
            self.assertFalse(extra.acknowledged_prior(second))
            with self.assertRaisesRegex(VideoError, "generation_uncertain"):
                guard.require_no_unsettled_intents(single_root=q.root)
            with self.assertRaisesRegex(VideoError, "already_consumed"):
                extra.claim_additional(prior.parent.parent, manual)

    def test_changed_prior_or_budget_or_manual_binding_fails(self):
        for defect in ("prior", "budget", "manual"):
            with self.subTest(defect=defect), setup() as (q, job, prior, manual):
                extra.record_approval()
                if defect == "prior":
                    prior.write_text('{}')
                elif defect == "budget":
                    path = extra.folder() / extra.RECORD
                    value = json.loads(path.read_text()); value["additional_requests"] = 2
                    atomic_json(path, value)
                else:
                    manual = {**manual, "request_sha256": "a" * 64}
                with self.assertRaises(VideoError):
                    extra.claim_additional(prior.parent.parent, manual)


if __name__ == "__main__":
    unittest.main()
