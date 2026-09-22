from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from short_video_pipeline import atomic_json, file_hash
import aether_single


class Provider:
    profile = "aether_inn"
    channel = "UC" + "x" * 22
    token = True
    def __init__(self):
        self.inserts = 0
        self.thumbnails = 0
        self.body = None
    def verify(self):
        return {"channel_verified": True}
    def initiate(self, body, size):
        self.inserts += 1
        self.body = body
        if body["snippet"]["categoryId"] != "10":
            raise AssertionError("wrong category")
        return "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&upload_id=single-fixture"
    def probe(self, url, size):
        return 201, {}, {"id": "abcdefghijk"}
    def video(self, video_id):
        status = {"uploadStatus": "processed", "privacyStatus": "public"}
        if self.body and self.body.get("status", {}).get("publishAt"):
            status = {
                "uploadStatus": "processed",
                "privacyStatus": "private",
                "publishAt": self.body["status"]["publishAt"],
            }
        return {"id": video_id, "snippet": {"channelId": self.channel},
                "status": status,
                "processingDetails": {"processingStatus": "succeeded"}}
    def headers(self, **extra):
        return extra
    def request(self, method, url, *args, **kwargs):
        self.thumbnails += 1
        return 200, {}, {"items": [{}]}


class SingleTests(unittest.TestCase):
    def fake_music(self, title, style, *, execute, output_root):
        output_root.mkdir(parents=True, exist_ok=True)
        audio = output_root / "candidate.mp3"
        audio.write_bytes(b"audio-fixture")
        return {"candidates": [{"index": 1, "file": str(audio), "sha256": file_hash(audio)}]}

    def fake_cover(self, title, style, lane, output_dir, *, execute):
        output_dir.mkdir(parents=True, exist_ok=True)
        cover = output_dir / "cover.png"
        cover.write_bytes(b"cover-fixture")
        return {"state": "generated", "path": str(cover), "sha256": file_hash(cover),
                "model": "fixture", "layout": "upper_left_matte_gold_serif"}

    def fake_renderer(self, audio, cover, output):
        output.mkdir(parents=True, exist_ok=True)
        for name in ("video.mp4", "thumbnail.jpg"):
            (output / name).write_bytes(b"render-fixture")
        return {"test_only": False, "upload_eligible": True, "duration_seconds": 184,
                "sha256": {name: file_hash(output / name) for name in ("video.mp4", "thumbnail.jpg")}}

    def test_candidate_review_prefers_best_accepted_audio(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(aether_single, "audio_duration", return_value=184):
            root=Path(temporary)
            rows=[]
            for index,name in enumerate(("one.mp3","two.mp3"),1):
                path=root/name;path.write_bytes((name*200).encode())
                rows.append({"index":index,"file":str(path),"sha256":file_hash(path)})
            scores={"one.mp3":7.2,"two.mp3":8.7}
            def reviewer(path):
                return {"accepted":True,"weighted_score":scores[path.name]}
            chosen=aether_single.select_candidate({"candidates":rows},set(),reviewer=reviewer)
            self.assertEqual(2,chosen["candidate_index"])
            self.assertEqual(8.7,chosen["review"]["weighted_score"])

    def test_brief_is_music_profile_and_under_limits(self):
        job = {"title": "Sails Above the Cloud Sea", "style": "Buoyant JRPG flight theme", "lane": "skybound_flight"}
        brief = aether_single.brief_for(job)
        self.assertEqual("aether_inn", brief["youtube_profile"])
        self.assertEqual("aether_single", brief["content_kind"])
        self.assertLessEqual(len(brief["title"]), 100)
        self.assertIn("Aether Inn", brief["description"])

    def test_reconcile_idle_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = aether_single.worker(Path(temporary).resolve(), publish=True, execute=True, existing_only=True,
                                          api_factory=lambda: (_ for _ in ()).throw(AssertionError("network")))
            self.assertEqual("idle", result["status"])

    def test_full_worker_is_idempotent_and_schedules_same_video(self):
        api = Provider()
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(aether_single, "select_candidate", return_value={
                 "candidate_index": 1, "path": str(Path(temporary) / "chosen.mp3"),
                 "duration_seconds": 184, "sha256": "a" * 64}), \
             patch.object(aether_single.SingleQueue, "_render", return_value=None), \
             patch.object(aether_single, "thumbnail") as thumb:
            Path(temporary, "chosen.mp3").write_bytes(b"chosen")
            def thumbnail(q, state, job, provider):
                job["thumbnail_status"] = "set"
                atomic_json(q.state_path, state)
            thumb.side_effect = thumbnail
            first = aether_single.worker(
                Path(temporary).resolve(), slot="2026-09-26", title="Sails Above the Cloud Sea",
                style="Buoyant JRPG flight theme", lane="skybound_flight", publish=True, execute=True,
                api_factory=lambda: api, music_generator=self.fake_music,
                cover_generator=self.fake_cover, renderer=self.fake_renderer,
            )
            second = aether_single.worker(
                Path(temporary).resolve(), slot="2026-09-26", title="Ignored New Title",
                style="Ignored", lane="quiet_road", publish=True, execute=True,
                api_factory=lambda: api, music_generator=self.fake_music,
                cover_generator=self.fake_cover, renderer=self.fake_renderer,
            )
        self.assertEqual("scheduled", first["status"])
        self.assertFalse(first["publication_complete"])
        self.assertEqual("private", api.body["status"]["privacyStatus"])
        self.assertEqual("2026-09-26T00:00:00Z", api.body["status"]["publishAt"])
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(first["video_id"], second["video_id"])
        self.assertEqual(1, api.inserts)

    def test_backlog_worker_imports_catalog_wav_without_lyria_generation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(aether_single, "audio_duration", return_value=138):
            root = Path(temporary).resolve()
            source = root / "Beyond the Road of Falling Petals.wav"
            source.write_bytes(b"RIFF" + b"catalog-master" * 512)
            calls = []
            def paid_music(*args, **kwargs):
                calls.append((args, kwargs))
                raise AssertionError("backlog must not call Lyria")
            result = aether_single.backlog_worker(
                root / "queue", slot="2026-09-26", title="Beyond the Road of Falling Petals",
                execute=True, publish=False, source_wav=source, music_generator=paid_music,
                cover_generator=self.fake_cover, renderer=self.fake_renderer,
            )
            state = json.loads((root / "queue" / "queue.json").read_text())
            job = state["jobs"][result["job_id"]]
            durable = Path(job["music"]["path"])
            self.assertEqual("rendered", result["status"])
            self.assertEqual("backlog_wav", result["source_kind"])
            self.assertEqual([], calls)
            self.assertTrue(durable.is_file())
            self.assertNotEqual(source, durable)
            self.assertEqual(file_hash(source), file_hash(durable))
            self.assertEqual("not_run_existing_catalog_master", job["music"]["review"]["state"])
            self.assertEqual("canonical_wav_master", aether_single.policy_for(job)["music_provider"])

    def test_backlog_worker_skips_title_already_public_before_wav_access(self):
        class ExistingApi:
            profile = "aether_inn"
            channel = "UC_AETHER"

            def verify(self):
                return None

        existing = {
            "video_id": "7IgogI2u42I",
            "title": "Beyond the Road of Falling Petals 🌿 Fantasy RPG Music",
            "published_at": "2026-09-20T00:00:00Z",
        }
        with patch.object(aether_single, "find_existing_public_video", return_value=existing), \
             patch.object(aether_single, "resolve_backlog_wav", side_effect=AssertionError("must not read WAV")):
            result = aether_single.backlog_worker(
                Path("/tmp/not-used"), slot="2026-09-26",
                title="Beyond the Road of Falling Petals", execute=True, publish=True,
                api_factory=lambda: ExistingApi(),
            )
        self.assertEqual("already_public", result["status"])
        self.assertEqual("7IgogI2u42I", result["video_id"])
        self.assertFalse(result["created_new_job"])

    def test_confirmed_legacy_upload_is_no_longer_registered_as_backlog(self):
        with self.assertRaisesRegex(Exception, "backlog_title_not_registered"):
            aether_single.backlog_catalog_entry("A Fantasy Still Breathing")

    def test_backlog_resolver_handles_decomposed_mybox_names(self):
        import unicodedata
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / unicodedata.normalize("NFD", "개인 폴더")
            parent = parent / "Aether Inn" / "01_Audio_Master"
            parent.mkdir(parents=True)
            source = parent / unicodedata.normalize("NFD", "When the Northern Lights Returned.wav")
            source.write_bytes(b"fixture")
            resolved = aether_single.resolve_backlog_wav("When the Northern Lights Returned", root=root)
            self.assertEqual(source, resolved)

    def test_backlog_unregistered_title_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Unknown Song.wav"
            source.write_bytes(b"fixture")
            with self.assertRaisesRegex(Exception, "backlog_title_not_registered"):
                aether_single.backlog_worker(
                    Path(temporary) / "queue", slot="2026-09-26", title="Unknown Song",
                    execute=True, source_wav=source, cover_generator=self.fake_cover, renderer=self.fake_renderer,
                )

    def test_lane_rotation_blocks_third_calm_track(self):
        state = {"jobs": {
            "a": {"id": "a", "slot": "2026-09-01", "lane": "quiet_road"},
            "b": {"id": "b", "slot": "2026-09-02", "lane": "night_wonder"},
        }}
        with self.assertRaisesRegex(Exception, "calm_streak"):
            aether_single.enforce_lane_rotation(state, "quiet_road")
        aether_single.enforce_lane_rotation(state, "skybound_flight")

    def test_catalog_exact_duplicate_is_rejected_before_paid_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            called = False
            def music(*args, **kwargs):
                nonlocal called
                called = True
                raise AssertionError("paid generation must not run")
            with self.assertRaisesRegex(Exception, "catalog_duplicate"):
                aether_single.worker(
                    root, slot="2026-09-22", title="Beyond the Silent Stone Gate",
                    style="Fantasy Frontier Theme, Warm Guitar Arpeggios, Gentle Piano Harmony, Ancient Stone Gateway Leading Into Unknown Lands, Nostalgic JRPG World Exploration, Restrained Emotional Development, Hopeful Fantasy Ending",
                    lane="frontier_surge", execute=True, publish=False, music_generator=music,
                )
            self.assertFalse(called)

    def test_existing_paid_generation_is_recovered_without_new_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            jobdir=root/"job"
            gen=jobdir/"lyria"/"run1"
            gen.mkdir(parents=True)
            audio=gen/"candidate-01.mp3"
            audio.write_bytes(b"x"*4096)
            manifest={"state":"generated","candidates":[{"index":1,"file":str(audio),"sha256":file_hash(audio)}]}
            (gen/"manifest.json").write_text(json.dumps(manifest))
            recovered=aether_single.recover_generated_result(jobdir)
            self.assertEqual("recovered",recovered["state"])
            self.assertEqual(1,len(recovered["candidates"]))
            self.assertEqual(file_hash(audio),recovered["candidates"][0]["sha256"])

    def test_wrong_youtube_profile_rejected_before_generation(self):
        class Wrong:
            profile = "onnellab"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(Exception):
                aether_single.worker(
                    Path(temporary).resolve(), slot="2026-09-22", title="Title", style="Style",
                    lane="quiet_road", publish=True, execute=True, api_factory=lambda: Wrong(),
                )


if __name__ == "__main__":
    unittest.main()
