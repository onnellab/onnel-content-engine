"""Isolated manual-release tests: fictional media and network responses only."""
from contextlib import contextmanager
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_manual_release as release
import aether_single as single
import lyria_generate as lyria
from short_video_pipeline import atomic_json, digest, VideoError
from test_aether_paid_boundary import fixture_environment, response_fixture, NOW
import test_aether_single as media_fixtures


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary).resolve()
        with fixture_environment(base, project_id=release.PROJECT):
            root = base / "singles"
            queue = single.SingleQueue(root)
            folder = root / "jobs" / release.JOB_ID
            folder.mkdir(mode=0o700)
            job = {"id": release.JOB_ID, "title": release.TITLE, "slot": release.SLOT,
                   "style": "Fictional frontier travel", "lane": "frontier_surge",
                   "status": "rejected", "error": "aether_single_publish_time_stale",
                   "music": None, "cover": None, "result": None,
                   "publish_requested": True, "upload_eligible": False}
            job["brief"] = single.brief_for(job)
            job["payload_hash"] = digest(job["brief"])
            atomic_json(queue.state_path, {"schema_version": 1, "jobs": {job["id"]: job}})
            with patch.object(release, "ROOT", root), patch.object(release, "utc_now", return_value=NOW):
                yield queue, job


class ManualReleaseTests(unittest.TestCase):
    def test_record_is_immutable_and_does_not_reset_queue(self):
        with fixture() as (queue, job):
            before = queue.state_path.read_bytes()
            request = release.record_request()
            self.assertEqual(request, release.record_request())
            self.assertEqual(before, queue.state_path.read_bytes())
            path = queue.root / "jobs" / release.JOB_ID / release.RECEIPT
            original = path.read_bytes()
            with patch.object(release, "utc_now", return_value=NOW + timedelta(hours=3)):
                with self.assertRaisesRegex(VideoError, "expired"):
                    release.record_request()
            self.assertEqual(original, path.read_bytes())

    def test_request_binds_job_prompt_project_and_expiry(self):
        with fixture() as (queue, job):
            request = release.record_request()
            context = {k: request[k] for k in ("job_id", "request_sha256")}
            prompt = lyria.build_aether_prompt(job["title"], job["style"])
            lyria.check_generation_schedule(release.SLOT, release.PROJECT, prompt, manual_release=context, now=NOW)
            for project, text, ctx, now in (
                ("other-project", prompt, context, NOW),
                (release.PROJECT, "wrong prompt", context, NOW),
                (release.PROJECT, prompt, {**context, "job_id": "f" * 24}, NOW),
                (release.PROJECT, prompt, context, NOW + timedelta(hours=3)),
                (release.PROJECT, prompt, None, NOW),
            ):
                with self.subTest(project=project, now=now), self.assertRaises(VideoError):
                    lyria.check_generation_schedule(release.SLOT, project, text, manual_release=ctx, now=now)

    def test_real_adapter_requires_one_request_and_preserves_uncertain_intent(self):
        for uncertain in (False, True):
            with self.subTest(uncertain=uncertain), fixture() as (queue, job):
                request = release.record_request()
                context = {k: request[k] for k in ("job_id", "request_sha256")}
                kwargs = {"execute": True, "slot": release.SLOT, "manual_release": context,
                          "output_root": queue.root / "jobs" / release.JOB_ID / "lyria"}
                effect = TimeoutError() if uncertain else lambda *a, **k: response_fixture()
                with patch.object(lyria, "access_token", return_value="fixture"), \
                     patch.object(lyria, "urlopen", side_effect=effect) as wire:
                    if uncertain:
                        with self.assertRaisesRegex(VideoError, "network_error"):
                            lyria.generate(job["title"], job["style"], **kwargs)
                        with self.assertRaisesRegex(VideoError, "generation_uncertain"):
                            lyria.generate(job["title"], job["style"], **kwargs)
                    else:
                        result = lyria.generate(job["title"], job["style"], **kwargs)
                        self.assertEqual("generated", result["state"])
                        self.assertEqual(context, result["manual_release"])
                    wire.assert_called_once()

    def test_worker_uses_same_job_and_video_without_regeneration(self):
        with fixture() as (queue, job):
            release.record_request()
            provider = media_fixtures.Provider()
            media = media_fixtures.SingleTests()
            generation = []
            def music(title, style, **kwargs):
                generation.append(kwargs.pop("manual_release"))
                return media.fake_music(title, style, **kwargs)
            def select(result, previous, **kwargs):
                row = result["candidates"][0]
                return {"path": row["file"], "sha256": row["sha256"], "duration_seconds": 184,
                        "review": {"accepted": True}}
            def thumbnail(q, state, current, api):
                current["thumbnail_status"] = "set"
                atomic_json(q.state_path, state)
            with patch.object(single, "select_candidate", side_effect=select), \
                 patch.object(single.SingleQueue, "_render"), patch.object(single, "thumbnail", side_effect=thumbnail):
                args = {"root": queue.root, "execute": True, "publish": True, "manual_release_id": release.JOB_ID,
                        "api_factory": lambda: provider, "music_generator": music,
                        "cover_generator": media.fake_cover, "renderer": media.fake_renderer}
                first, second = single.worker(**args), single.worker(**args)
            self.assertTrue(first["publication_complete"])
            self.assertEqual(first["video_id"], second["video_id"])
            self.assertEqual(1, len(generation))
            self.assertEqual(1, provider.inserts)
            self.assertEqual("public", provider.body["status"]["privacyStatus"])
            self.assertNotIn("publishAt", provider.body["status"])
            current = queue._read()["jobs"][release.JOB_ID]
            self.assertEqual(release.SLOT, current["slot"])
            self.assertEqual("manual", current["approval"]["mode"])
            self.assertEqual(1, len(queue._read()["jobs"]))

    def test_missing_request_stops_before_provider_access(self):
        with fixture() as (queue, job):
            provider = Mock(side_effect=AssertionError("no provider access"))
            with self.assertRaisesRegex(VideoError, "request_missing"):
                single.worker(queue.root, execute=True, publish=True,
                              manual_release_id=release.JOB_ID, api_factory=provider)
            provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
