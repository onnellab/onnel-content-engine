from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_single as single
from short_video_pipeline import atomic_json, file_hash


class BacklogReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "singles"
        self.assets = self.base / "assets"
        self.assets.mkdir()
        self.title = "The Meadow Where Skylarks Sing"
        self.job_id = "a" * 24
        self.source = self.root / "jobs" / self.job_id / "source/master.wav"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"retained canonical WAV fixture")
        self.job = {
            "id": self.job_id, "title": self.title, "slot": "2026-10-10",
            "style": "Warm meadow guitar and flute", "lane": "quiet_road",
            "source_expected_duration": 157,
            "status": "rejected", "error": "aether_single_publish_time_stale",
            "source_kind": "backlog_wav", "source_filename": self.title + ".wav",
            "music": {"path": str(self.source), "sha256": file_hash(self.source),
                      "source_kind": "backlog_wav", "source_filename": self.title + ".wav"},
        }
        self.job["brief"] = single.brief_for(self.job)
        self.job["payload_hash"] = single.digest(self.job["brief"])
        self.rights = {"schema_version": 1, "profile": "aether_inn", "tracks": {
            "asset": {"title": self.title, "commercial_use_confirmed": True}}}
        self.persist()

    def persist(self):
        atomic_json(self.root / "queue.json", {"schema_version": 1, "jobs": {self.job_id: self.job}})
        atomic_json(self.assets / "approval.json", self.rights)

    def resolve(self):
        return single.reusable_backlog_master(self.title, self.root, self.assets)

    def test_rejected_slot_can_supply_hash_bound_audio_without_mutating_queue(self):
        before = (self.root / "queue.json").read_bytes()
        result = self.resolve()
        self.assertEqual(self.source, result["path"])
        self.assertEqual(file_hash(self.source), result["sha256"])
        self.assertEqual(self.job_id, result["job_id"])
        self.assertEqual(before, (self.root / "queue.json").read_bytes())

    def stage_master(self):
        self.staged = self.assets / "staged/singles/masters" / (self.title + ".wav")
        self.staged.parent.mkdir(parents=True)
        self.staged.write_bytes(self.source.read_bytes())
        self.rights["tracks"]["asset"]["local_master"] = {
            "path": str(self.staged.relative_to(self.assets)),
            "sha256": file_hash(self.staged),
            "source_filename": self.title + ".wav",
        }
        atomic_json(self.root / "queue.json", {"schema_version": 1, "jobs": {}})
        atomic_json(self.assets / "approval.json", self.rights)

    def test_staged_recovered_master_requires_no_job_and_preserves_records(self):
        self.stage_master()
        before = [(p, p.read_bytes()) for p in (self.root / "queue.json", self.assets / "approval.json")]
        result = self.resolve()
        self.assertIsNotNone(result)
        self.assertEqual(self.staged, result["path"])
        self.assertEqual(file_hash(self.staged), result["sha256"])
        for p, raw in before:
            self.assertEqual(raw, p.read_bytes())

    def test_staged_master_rejects_corruption_and_unsafe_paths(self):
        self.stage_master()
        self.staged.write_bytes(b"corrupt")
        with self.assertRaises(single.VideoError):
            self.resolve()
        self.rights["tracks"]["asset"]["local_master"]["path"] = "../outside.wav"
        atomic_json(self.assets / "approval.json", self.rights)
        with self.assertRaises(single.VideoError):
            self.resolve()

    def test_staged_master_requires_existing_commercial_rights(self):
        self.stage_master()
        self.rights["tracks"]["asset"]["commercial_use_confirmed"] = False
        atomic_json(self.assets / "approval.json", self.rights)
        self.assertIsNone(self.resolve())

    def test_staged_master_rejects_symlink_and_wrong_title_filename(self):
        self.stage_master()
        other = self.base / "outside.wav"
        other.write_bytes(self.staged.read_bytes())
        self.staged.unlink()
        self.staged.symlink_to(other)
        with self.assertRaises(single.VideoError):
            self.resolve()
        self.staged.unlink()
        self.staged.write_bytes(other.read_bytes())
        self.rights["tracks"]["asset"]["local_master"]["source_filename"] = "Other.wav"
        atomic_json(self.assets / "approval.json", self.rights)
        with self.assertRaises(single.VideoError):
            self.resolve()

    def test_different_title_and_non_backlog_job_are_not_candidates(self):
        self.job["title"] = "The Meadow Before Dawn"
        self.persist()
        self.assertIsNone(self.resolve())
        self.job["title"] = self.title
        self.job["source_kind"] = "generated"
        self.persist()
        self.assertIsNone(self.resolve())

    def test_missing_rights_never_reuses_audio(self):
        self.rights["tracks"]["asset"]["commercial_use_confirmed"] = False
        self.persist()
        self.assertIsNone(self.resolve())

    def test_corrupt_retained_wav_fails_closed(self):
        self.source.write_bytes(b"changed")
        with self.assertRaisesRegex(single.VideoError, "backlog_source_integrity"):
            self.resolve()

    def test_untrusted_path_and_symlink_are_rejected(self):
        foreign = self.base / "foreign.wav"
        foreign.write_bytes(self.source.read_bytes())
        self.job["music"]["path"] = str(foreign)
        self.persist()
        with self.assertRaisesRegex(single.VideoError, "backlog_source_unsafe"):
            self.resolve()
        self.job["music"]["path"] = str(self.source)
        self.source.unlink()
        self.source.symlink_to(foreign)
        self.persist()
        with self.assertRaisesRegex(single.VideoError, "backlog_source_unsafe"):
            self.resolve()

    def test_missing_local_file_allows_existing_mybox_path(self):
        self.source.unlink()
        self.assertIsNone(self.resolve())

    def test_dataless_candidate_is_skipped_without_hashing_or_hydrating(self):
        with patch.object(single, "_is_dataless", return_value=True), \
             patch.object(single, "file_hash", side_effect=AssertionError("no placeholder read")), \
             patch.object(single, "_warm_mybox_provider", side_effect=AssertionError("no MYBOX startup")):
            self.assertIsNone(self.resolve())

    def test_job_id_traversal_is_rejected(self):
        atomic_json(self.root / "queue.json", {"schema_version": 1, "jobs": {"../escape": self.job}})
        with self.assertRaisesRegex(single.VideoError, "reuse_record_invalid"):
            self.resolve()

    def test_missing_or_invalid_hash_is_rejected(self):
        for value in [None, "not-a-hash"]:
            self.job["music"]["sha256"] = value
            self.persist()
            with self.assertRaisesRegex(single.VideoError, "backlog_source_integrity"):
                self.resolve()

    def test_distinct_retained_hashes_for_same_title_are_ambiguous(self):
        from copy import deepcopy
        other_id = "b" * 24
        other = deepcopy(self.job)
        other["id"] = other_id
        source = self.root / "jobs" / other_id / "source/master.wav"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"different master")
        other["music"].update(path=str(source), sha256=file_hash(source))
        atomic_json(self.root / "queue.json", {"schema_version": 1,
                    "jobs": {self.job_id: self.job, other_id: other}})
        with self.assertRaisesRegex(single.VideoError, "backlog_source_ambiguous"):
            self.resolve()

    def test_symlinked_parent_is_rejected(self):
        moved = self.root / "retained-source"
        self.source.parent.rename(moved)
        self.source.parent.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(single.VideoError, "backlog_source_unsafe"):
            self.resolve()

    def test_cross_profile_rights_fail_closed(self):
        self.rights["profile"] = "onnellab"
        self.persist()
        with self.assertRaisesRegex(single.VideoError, "reuse_record_invalid"):
            self.resolve()

    def test_import_binds_copy_to_expected_hash_before_audio_gate(self):
        folder = self.base / "future-fixture"
        with patch.object(single, "audio_duration", side_effect=AssertionError("do not decode corrupt copy")):
            with self.assertRaisesRegex(single.VideoError, "backlog_source_integrity"):
                single.import_backlog_master(self.source, folder, 157, expected_sha256="0" * 64)
        self.assertFalse((folder / "source/master.wav").exists())
        self.assertFalse((folder / "source/master.partial.wav").exists())

    def test_worker_prefers_reusable_source_but_preserves_new_slot_and_gates(self):
        with patch.object(single, "worker", return_value={"fixture": True}) as worker, \
             patch.object(single, "ASSETS_ROOT", self.assets), \
             patch.object(single, "resolve_backlog_wav", side_effect=AssertionError("no MYBOX read")):
            single.backlog_worker(self.root, slot="2026-10-17", title=self.title, execute=True)
        self.assertEqual("2026-10-17", worker.call_args.kwargs["slot"])
        self.assertEqual(self.source, worker.call_args.kwargs["source_wav"])
        self.assertEqual(file_hash(self.source), worker.call_args.kwargs["source_expected_sha256"])
        self.assertEqual(157, worker.call_args.kwargs["source_expected_duration"])
        self.assertEqual(self.title + ".wav", worker.call_args.kwargs["source_filename"])

    def test_selected_different_title_fails_before_import_or_queue_write(self):
        self.job.update(title="The Old Library of Everlight", status="planned",
                        source_filename="The Old Library of Everlight.wav",
                        source_expected_duration=143, music=None,
                        style="Gentle piano fantasy library", lane="night_wonder")
        self.job["brief"] = single.brief_for(self.job)
        self.job["payload_hash"] = single.digest(self.job["brief"])
        self.persist()
        before = (self.root / "queue.json").read_bytes()
        with patch.object(single, "import_backlog_master", side_effect=AssertionError("wrong-title import")), \
             patch.object(single, "generate_music", side_effect=AssertionError("no paid generation")):
            with self.assertRaisesRegex(single.VideoError, "backlog_source_job_mismatch"):
                single.worker(self.root, slot="2026-10-10", title=self.title,
                              execute=True, source_kind="backlog_wav", source_wav=self.source,
                              source_filename=self.title + ".wav", source_expected_duration=157,
                              source_expected_sha256=file_hash(self.source))
        self.assertEqual(before, (self.root / "queue.json").read_bytes())

    def assert_other_job_blocked(self, same_slot):
        from copy import deepcopy
        other = deepcopy(self.job)
        other.update(id="b" * 24, title="The Old Library of Everlight", music=None,
                     slot="2026-10-17" if same_slot else "2026-10-13", status="planned",
                     source_filename="The Old Library of Everlight.wav",
                     source_expected_duration=143, lane="night_wonder")
        other["brief"] = single.brief_for(other)
        other["payload_hash"] = single.digest(other["brief"])
        atomic_json(self.root / "queue.json", {"schema_version": 1,
                    "jobs": {self.job_id: self.job, other["id"]: other}})
        before = (self.root / "queue.json").read_bytes()
        with patch.object(single, "ASSETS_ROOT", self.assets), \
             patch.object(single, "import_backlog_master", side_effect=AssertionError("wrong-title import")), \
             patch.object(single, "generate_music", side_effect=AssertionError("no paid generation")):
            with self.assertRaisesRegex(single.VideoError, "backlog_source_job_mismatch"):
                single.backlog_worker(self.root, slot="2026-10-17", title=self.title, execute=True)
        self.assertEqual(before, (self.root / "queue.json").read_bytes())
        self.assertEqual(self.job["music"]["sha256"], file_hash(self.source))

    def test_backlog_entry_blocks_another_title_in_same_slot(self):
        self.assert_other_job_blocked(same_slot=True)

    def test_backlog_entry_blocks_another_title_unfinished_job(self):
        self.assert_other_job_blocked(same_slot=False)

    def test_lock_rechecks_retained_path_not_just_claimed_filename(self):
        foreign = self.base / "other.wav"
        foreign.write_bytes(self.source.read_bytes())
        before = (self.root / "queue.json").read_bytes()
        with patch.object(single, "ASSETS_ROOT", self.assets), \
             patch.object(single, "import_backlog_master", side_effect=AssertionError("unbound import")):
            with self.assertRaisesRegex(single.VideoError, "backlog_source_job_mismatch"):
                single.worker(self.root, slot="2026-10-17", title=self.title,
                              execute=True, source_kind="backlog_wav", source_wav=foreign,
                              source_filename=self.title + ".wav", source_expected_duration=157,
                              source_expected_sha256=file_hash(foreign))
        self.assertEqual(before, (self.root / "queue.json").read_bytes())

    def test_caller_cannot_relabel_retained_master_before_new_job_creation(self):
        before = (self.root / "queue.json").read_bytes()
        with self.assertRaisesRegex(single.VideoError, "backlog_source_job_mismatch"):
            single.worker(self.root, slot="2026-10-17", title=self.title,
                          execute=True, source_kind="backlog_wav", source_wav=self.source,
                          source_filename="The Old Library of Everlight.wav",
                          source_expected_duration=157)
        self.assertEqual(before, (self.root / "queue.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
