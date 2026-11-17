"""Scoped retained-release fixtures: no real media, credentials or publication."""
from contextlib import ExitStack, contextmanager, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as daily
import aether_retained_release as release
import aether_single as single
from lyria_generate import build_aether_prompt
from short_video_pipeline import atomic_json, digest, file_hash, VideoError
import test_aether_single as media_fixtures

NOW = datetime(2026, 11, 17, 7, tzinfo=timezone.utc)

@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
        root = Path(temporary).resolve() / "singles"
        q = single.SingleQueue(root)
        job = {"id": release.JOB_ID, "title": release.TITLE, "slot": release.SLOT,
               "style": "Fictional frontier travel", "lane": "frontier_surge",
               **release.PRIOR_STATE, "music": None, "cover": None, "result": None,
               "publish_requested": True, "upload_eligible": False}
        job["brief"] = single.brief_for(job)
        job["payload_hash"] = digest(job["brief"])
        atomic_json(q.state_path, {"schema_version": 1, "jobs": {job["id"]: job}})
        folder = root / "jobs" / job["id"]
        folder.mkdir(mode=0o700)
        manifest = folder / release.MANIFEST_RELATIVE
        manifest.parent.mkdir(mode=0o700, parents=True)
        source = manifest.parent / "candidate-01.mp3"
        source.write_bytes(b"fictional-retained-audio" * 100)
        source.chmod(0o600)
        data = {"state": "generated", "candidate_count": 1, "title": job["title"],
                "slot": job["slot"], "style": job["style"], "project_id": release.PROJECT,
                "model": "lyria-3-pro-preview", "estimated_cost_usd": .08,
                "cost_basis": "provider_base_excluding_tax_and_currency_adjustments",
                "prompt_sha256": hashlib.sha256(build_aether_prompt(job["title"], job["style"]).encode()).hexdigest(),
                "candidates": [{"file": str(source), "index": 1, "sha256": file_hash(source)}]}
        atomic_json(manifest, data)
        for name, value in (("ROOT", root), ("SOURCE_SHA256", file_hash(source)),
                            ("MANIFEST_SHA256", file_hash(manifest))):
            stack.enter_context(patch.object(release, name, value))
        stack.enter_context(patch.object(release, "utc_now", return_value=NOW))
        yield q, job, source, manifest


class RetainedRelease(unittest.TestCase):
    def test_request_is_immutable_and_preserves_failed_queue(self):
        with fixture() as (q, job, source, manifest):
            before = {p: p.read_bytes() for p in (q.state_path, source, manifest)}
            first = release.record_request()
            self.assertEqual(first, release.record_request())
            self.assertTrue(first["retained_only"])
            for path, raw in before.items():
                self.assertEqual(raw, path.read_bytes())
            receipt = source.parents[1].parent / release.RECEIPT
            original = receipt.read_bytes()
            with patch.object(release, "utc_now", return_value=NOW + timedelta(hours=3)):
                with self.assertRaisesRegex(VideoError, "expired"):
                    release.record_request()
            self.assertEqual(original, receipt.read_bytes())

    def test_changed_source_blocks_without_generation(self):
        with fixture() as (q, job, source, manifest):
            release.record_request()
            source.write_bytes(b"changed")
            generator = Mock(side_effect=AssertionError("forbidden charge"))
            with self.assertRaisesRegex(VideoError, "source_changed"):
                single.worker(q.root, execute=True, publish=True, manual_release_id=release.JOB_ID,
                              music_generator=generator)
            generator.assert_not_called()

    def test_changed_manifest_and_identity_are_rejected(self):
        with fixture() as (q, job, source, manifest):
            release.record_request()
            for key in ("id", "title", "slot"):
                with self.subTest(key=key), self.assertRaisesRegex(VideoError, "identity"):
                    release.validate({**job, key: "other"}, root=q.root)
            manifest.write_text("{}")
            with self.assertRaisesRegex(VideoError, "manifest_changed"):
                release.validate(job, root=q.root)

    def test_request_does_not_authorize_any_new_generation(self):
        with self.assertRaisesRegex(VideoError, "generation_forbidden"):
            release.forbid_generation()
        with fixture() as (q, job, source, manifest):
            release.record_request()
            provider = media_fixtures.Provider()
            generator = Mock(side_effect=AssertionError("forbidden charge"))
            with patch.object(single, "recover_generated_result", return_value=None), \
                 patch.object(single.paid_guard, "require_no_unsettled_intents"), \
                 self.assertRaisesRegex(VideoError, "generation_forbidden"):
                single.worker(q.root, execute=True, publish=True, manual_release_id=release.JOB_ID,
                              music_generator=generator, api_factory=lambda: provider)
            generator.assert_not_called()
            self.assertEqual(0, provider.inserts)

    def test_retained_audio_publishes_same_job_and_video_once(self):
        with fixture() as (q, job, source, manifest):
            release.record_request()
            provider = media_fixtures.Provider()
            media = media_fixtures.SingleTests()
            generator = Mock(side_effect=AssertionError("must never generate"))
            def thumb(queue, state, current, api):
                current["thumbnail_status"] = "set"
                atomic_json(queue.state_path, state)
            with patch.object(single, "audio_duration", return_value=140.434208), \
                 patch.object(single, "review_audio", return_value={"accepted": True,
                    "weighted_score": 8.5, "source_sha256": file_hash(source)}), \
                 patch.object(single.paid_guard, "require_no_unsettled_intents"), \
                 patch.object(single.SingleQueue, "_render"), patch.object(single, "thumbnail", side_effect=thumb):
                kwargs = {"root": q.root, "execute": True, "publish": True,
                          "manual_release_id": release.JOB_ID, "music_generator": generator,
                          "api_factory": lambda: provider, "cover_generator": media.fake_cover,
                          "renderer": media.fake_renderer}
                first, second = single.worker(**kwargs), single.worker(**kwargs)
            self.assertTrue(first["publication_complete"])
            self.assertEqual(release.JOB_ID, first["job_id"])
            self.assertEqual(first["video_id"], second["video_id"])
            self.assertEqual(1, first["generation_count"])
            self.assertEqual(.08, first["estimated_cost_usd"])
            self.assertEqual(1, provider.inserts)
            self.assertEqual("public", provider.body["status"]["privacyStatus"])
            self.assertNotIn("publishAt", provider.body["status"])
            self.assertEqual(1, len(q._read()["jobs"]))
            generator.assert_not_called()

    def test_only_actual_registered_owner_entrypoint_can_publish(self):
        with patch.dict(os.environ, {"XPC_SERVICE_NAME": "other-service"}), \
             patch.object(single, "worker") as worker, self.assertRaisesRegex(VideoError, "gui_owner"):
            release.publish()
        worker.assert_not_called()

    def test_expired_request_or_other_date_never_triggers_daily_override(self):
        with fixture() as (q, job, source, manifest):
            release.record_request()
            self.assertTrue(release.pending_request(now=NOW))
            self.assertFalse(release.pending_request(now=NOW + timedelta(hours=3)))
            self.assertFalse(release.pending_request(now=NOW + timedelta(days=1)))

    def test_daily_owner_routes_only_requested_release_preserving_morning_report(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp).resolve()
            result = root / "result.json"
            original = {"kind": "onnellab_aether_local_daily_result", "mode": "daily",
                        "local_date": release.SLOT, "state": "partial", "blockers": ["old"]}
            atomic_json(result, original)
            for name, value in (("STATE", root), ("RESULT", result), ("LOCK", root / "worker.lock")):
                stack.enter_context(patch.object(daily, name, value))
            stack.enter_context(patch.object(daily, "now_kst", return_value=NOW))
            stack.enter_context(patch.dict(os.environ, {"XPC_SERVICE_NAME": release.OWNER_SERVICE}))
            stack.enter_context(patch.object(sys, "argv", ["aether_daily_local.py"]))
            stack.enter_context(patch.object(release, "pending_request", return_value=True))
            stack.enter_context(patch("aether_single_today.pending_request", return_value=False))
            stack.enter_context(patch("aether_sleep_request.gui_requested", return_value=False))
            stack.enter_context(patch.object(daily, "repo_sync", return_value=True))
            release_call = stack.enter_context(patch.object(daily, "run_retained_single_slot"))
            forbidden = [stack.enter_context(patch.object(daily, name)) for name in (
                "run_single_slot", "run_compilation_slot", "run_youtube_reports", "run_hosted_ops_workflows")]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, daily.main())
            release_call.assert_called_once()
            for call in forbidden:
                call.assert_not_called()
            self.assertEqual(original, json.loads(result.read_text()))
            self.assertEqual("retained_release", json.loads((root / "retained-release-result.json").read_text())["mode"])

    def test_processing_upload_is_not_public_completion(self):
        report = {"steps": [], "blockers": []}
        value = {"job_id": release.JOB_ID, "status": "processing", "video_id": "fixture-id",
                 "publication_complete": False}
        with patch.dict(os.environ, {"XPC_SERVICE_NAME": release.OWNER_SERVICE}), \
             patch.object(daily, "run_step", return_value=(0, json.dumps(value), "")), \
             patch.object(daily, "sync_playlists_after_upload"):
            daily.run_retained_single_slot(report)
        self.assertEqual(["aether_retained_publication_unverified"], report["blockers"])


if __name__ == "__main__":
    unittest.main()
