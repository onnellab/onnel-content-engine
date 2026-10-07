"""Existing artwork imports use local fixed fixtures; no API, ffmpeg or uploader."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_existing_cover as cover
import aether_single
from short_video_pipeline import atomic_json, file_hash
import test_aether_single as single_fixtures


class ExistingCoverTests(unittest.TestCase):
    title = "Beyond the Road of Falling Petals"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.source = self.assets / "art.png"
        self.source.write_bytes(b"fixed-image-fixture")
        self.spec = {"title": self.title, "path": "art.png", "sha256": file_hash(self.source),
                     "commercial_use_confirmed": True, "quality_accepted": True, "kind": "finished_cover"}
        self.payload = {"schema_version": 1, "profile": "aether_inn", "test_only": False,
                        "covers": {self.title: self.spec}}
        self.save()

    def save(self):
        atomic_json(self.assets / cover.APPROVAL_FILE, self.payload)

    def info(self, path):
        return {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}

    def render(self, args, **kwargs):
        Path(args[-1]).write_bytes(b"scaled-finished-cover")

    def imported(self):
        return cover.import_existing_cover(self.title, "style", "quiet_road", self.root / "output",
                                           execute=True, assets_root=self.assets)

    def test_finished_cover_import_has_provenance_and_never_double_brands(self):
        original = self.source.read_bytes()
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background"), \
             patch.object(cover, "run_process", side_effect=self.render), \
             patch.object(cover, "brand_background", side_effect=AssertionError("double branding")):
            result = self.imported()
        self.assertEqual("ready", result["state"])
        self.assertEqual(0, result["generation_count"])
        self.assertEqual("existing_approved_cover", result["source_kind"])
        self.assertEqual(self.spec["sha256"], result["source_sha256"])
        self.assertEqual(file_hash(self.assets / cover.APPROVAL_FILE), result["approval_sha256"])
        self.assertEqual(original, self.source.read_bytes())

    def test_unbranded_source_uses_local_branding(self):
        self.spec["kind"] = "unbranded_background"
        self.save()
        def brand(source, target, title):
            self.assertEqual(self.title, title)
            target.write_bytes(b"branded")
            return {"layout": "local-branding"}
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background"), \
             patch.object(cover, "brand_background", side_effect=brand), \
             patch.object(cover, "run_process", side_effect=AssertionError("unexpected renderer")):
            self.assertEqual("local-branding", self.imported()["layout"])

    def test_missing_or_inexact_approvals_fail_before_copy(self):
        for field in ("commercial_use_confirmed", "quality_accepted"):
            for value in (False, None, 1, "true"):
                with self.subTest(field=field, value=value):
                    self.spec[field] = value
                    self.save()
                    with patch.object(cover.shutil, "copyfile", side_effect=AssertionError("copy")):
                        with self.assertRaisesRegex(Exception, "unconfirmed"):
                            self.imported()
            self.spec[field] = True

    def test_profile_test_flag_and_title_must_match(self):
        for key, value in (("profile", "onnellab"), ("test_only", True), ("test_only", 0)):
            old = self.payload[key]
            self.payload[key] = value
            self.save()
            with self.subTest(key=key, value=value), self.assertRaisesRegex(Exception, "approval_invalid"):
                self.imported()
            self.payload[key] = old
        self.spec["title"] = "Other Song"
        self.save()
        with self.assertRaisesRegex(Exception, "approval_missing"):
            self.imported()

    def test_unapproved_or_missing_title_does_not_use_theme_cover(self):
        self.payload["covers"] = {"open_roads": self.spec}
        self.save()
        with self.assertRaisesRegex(Exception, "approval_missing"):
            self.imported()

    def test_source_hash_mismatch_is_rejected(self):
        self.source.write_bytes(b"changed")
        with self.assertRaisesRegex(Exception, "hash_mismatch"):
            self.imported()

    def test_copy_is_rehashed_before_any_image_processing(self):
        def copy(source, target):
            Path(target).write_bytes(b"changed-during-copy")
        with patch.object(cover.shutil, "copyfile", side_effect=copy), \
             patch.object(cover, "media_info", side_effect=AssertionError("probe")):
            with self.assertRaisesRegex(Exception, "hash_mismatch"):
                self.imported()
        self.assertFalse((self.root / "output" / "approved-source.partial.png").exists())

    def test_traversal_and_symlink_sources_rejected(self):
        self.spec["path"] = "../assets/art.png"
        self.save()
        with self.assertRaisesRegex(Exception, "relative_asset"):
            self.imported()
        self.spec["path"] = "link.png"
        (self.assets / "link.png").symlink_to(self.source)
        self.save()
        with self.assertRaisesRegex(Exception, "symlink_asset"):
            self.imported()

    def test_symlink_approval_and_asset_directory_rejected(self):
        approval = self.assets / cover.APPROVAL_FILE
        real = self.assets / "actual.json"
        approval.rename(real)
        approval.symlink_to(real)
        with self.assertRaisesRegex(Exception, "approval_missing"):
            self.imported()
        linked = self.root / "linked-assets"
        linked.symlink_to(self.assets, target_is_directory=True)
        with self.assertRaisesRegex(Exception, "symlink_asset_root"):
            cover.approved_cover(self.title, linked)

    def test_bad_geometry_or_letterbox_stops_before_render(self):
        with patch.object(cover, "media_info", return_value={"streams": [{"codec_type": "video", "width": 1000, "height": 1000}]}), \
             patch.object(cover, "run_process", side_effect=AssertionError("render")):
            with self.assertRaisesRegex(Exception, "landscape_cover_required"):
                self.imported()
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background", side_effect=ValueError("letterbox")), \
             patch.object(cover, "run_process", side_effect=AssertionError("render")):
            with self.assertRaisesRegex(Exception, "letterbox"):
                self.imported()

    def test_missing_approval_does_not_fall_back_to_paid_cover(self):
        (self.assets / cover.APPROVAL_FILE).unlink()
        with self.assertRaisesRegex(Exception, "approval_missing"):
            self.imported()

    def test_backlog_default_cover_is_existing_import(self):
        self.assertIs(aether_single.worker.__kwdefaults__["cover_generator"], cover.import_existing_cover)
        self.assertIs(aether_single.backlog_worker.__kwdefaults__["cover_generator"], cover.import_existing_cover)

    def test_approved_cover_reaches_backlog_renderer_without_generation(self):
        source = self.root / "master.wav"
        source.write_bytes(b"RIFF" + b"x" * 4096)
        fixture = single_fixtures.SingleTests()
        def importer(title, style, lane, output, *, execute):
            return cover.import_existing_cover(title, style, lane, output, execute=execute, assets_root=self.assets)
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background"), \
             patch.object(cover, "run_process", side_effect=self.render), \
             patch.object(aether_single, "audio_duration", return_value=138):
            result = aether_single.backlog_worker(self.root / "queue", slot="2099-10-10", title=self.title,
                                                 source_wav=source, execute=True, cover_generator=importer,
                                                 renderer=fixture.fake_renderer)
        state = json.loads((self.root / "queue" / "queue.json").read_text())
        job = state["jobs"][result["job_id"]]
        self.assertEqual("rendered", result["status"])
        self.assertEqual("owner_approved_existing_cover", aether_single.policy_for(job)["cover_provider"])
        self.assertEqual(self.spec["sha256"], job["cover"]["source_sha256"])

    def test_dry_run_needs_no_file_access(self):
        with patch.object(cover, "approved_cover", side_effect=AssertionError("read")):
            self.assertEqual(0, cover.import_existing_cover("T", "S", "quiet_road", self.root / "none")["generation_count"])

    def test_render_retry_rejects_changed_approved_cover_without_reimport(self):
        source = self.root / "master.wav"
        source.write_bytes(b"RIFF" + b"x" * 4096)
        def importer(title, style, lane, output, *, execute):
            return cover.import_existing_cover(title, style, lane, output, execute=execute, assets_root=self.assets)
        with patch.object(cover, "media_info", side_effect=self.info), \
             patch.object(cover, "validate_full_bleed_background"), \
             patch.object(cover, "run_process", side_effect=self.render), \
             patch.object(aether_single, "audio_duration", return_value=138):
            with self.assertRaisesRegex(OSError, "interrupted"):
                aether_single.backlog_worker(self.root / "queue", slot="2099-10-10", title=self.title,
                                             source_wav=source, execute=True, cover_generator=importer,
                                             renderer=lambda *args: (_ for _ in ()).throw(OSError("interrupted")))
        job = next(iter(json.loads((self.root / "queue" / "queue.json").read_text())["jobs"].values()))
        Path(job["cover"]["path"]).write_bytes(b"changed-after-approval")
        def never(*args, **kwargs):
            raise AssertionError("retry must not regenerate, reimport or render")
        with self.assertRaisesRegex(Exception, "approved_cover_integrity"):
            aether_single.worker(self.root / "queue", slot="2099-10-10", execute=True,
                                 music_generator=never, cover_generator=never, renderer=never)


if __name__ == "__main__":
    unittest.main()
