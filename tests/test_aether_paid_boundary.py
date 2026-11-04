"""Hermetic paid-boundary regressions. All receipts below are fictional fixtures."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_paid_guard as guard
import lyria_generate
import aether_single
from short_video_credentials import CredentialError
from short_video_pipeline import atomic_json, file_hash
from short_video_pipeline import digest
from short_video_youtube import Uploader
import short_video_youtube

NOW = datetime(2026, 10, 30, 21, 20, tzinfo=timezone.utc)
SLOT = "2026-10-31"
SETTINGS = {"project_id": "fixture-project", "candidate_count": 1, "max_usd_per_run": 0.08, "enabled": True}


def proof_fixture(root):
    """Fictional public documents; never use a live account or active policy."""
    import aether_lyria_rights as sources
    from test_aether_public_sources import MODEL_TEXT, PREVIEW_TEXT, PRICE_TEXT
    texts = {"model": MODEL_TEXT, "preview": PREVIEW_TEXT, "pricing": PRICE_TEXT,
             "terms": "FICTIONAL TEST service terms; no agreement acceptance"}
    def fetch(url):
        name = next(key for key, value in sources.URLS.items() if value == url)
        text = "FICTIONAL TEST SOURCE: " + texts[name] + "\n"
        return text.encode(), text
    evidence = Path(root).resolve() / "lyria-paid-evidence" / "public-sources"
    sources.collect(evidence, fetch=fetch, now=NOW - timedelta(hours=1))
    return json.loads((evidence / "current.json").read_text())


def replace_source(proof, name, text):
    raw = text.encode()
    sha = hashlib.sha256(raw).hexdigest()
    filename = f"{name}-{sha}.txt"
    (guard.PROOF_PATH.parent / filename).write_bytes(raw)
    proof["sources"][name].update(path=filename, sha256=sha)
    if name == "pricing":
        import aether_lyria_rights as sources
        proof["provider_base_price_usd"] = sources.documented_price(text)
    atomic_json(guard.PROOF_PATH, proof)


@contextmanager
def fixture_environment(root, project_id="fixture-project"):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    proof = proof_fixture(root)
    with patch.object(guard, "AETHER_ROOT", root), \
         patch.object(guard, "PROOF_PATH", root / "lyria-paid-evidence" / "public-sources" / "current.json"), \
         patch.object(guard, "utc_now", return_value=NOW), \
         patch.object(lyria_generate, "load_settings", return_value={**SETTINGS, "project_id": project_id}):
        yield proof


def response_fixture():
    response = io.BytesIO(json.dumps({"status": "completed", "model": "lyria-3-pro-preview",
        "outputs": [{"type": "audio", "mime_type": "audio/mpeg", "data": base64.b64encode(b"x" * 2048).decode()}]}).encode())
    response.headers = {}
    return response


class PaidBoundaryTests(unittest.TestCase):
    def test_missing_provider_sources_fail_before_authorization(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(guard, "PROOF_PATH", Path(temporary) / "absent.json"):
            with self.assertRaisesRegex(CredentialError, "provider_sources_missing"):
                guard.load_paid_proof("fixture-project")

    def test_actual_paid_boundary_closes_at_eight_kst(self):
        with self.assertRaisesRegex(CredentialError, "aether_lyria_generation_window_closed"):
            guard.require_generation_window("2026-10-31", now=datetime(2026, 10, 30, 23, tzinfo=timezone.utc))

    def test_provider_price_does_not_claim_invoice_or_require_manual_proof(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)):
            result = guard.load_paid_proof("fixture-project")
            self.assertEqual("0.08", result["provider_base_price_usd"])
            self.assertFalse(result["gross_cost_verified"])
            self.assertIsNone(result["final_billed_cost_usd"])
            self.assertFalse(result["account_agreement_verified"])
            self.assertFalse(result["copyright_ownership_certified"])
            self.assertNotIn("gross_cost_upper_bound_usd", result)
            self.assertFalse((guard.PROOF_PATH.parent.parent / "proof.json").exists())

    def test_actual_price_increase_or_zero_blocks_without_rounding(self):
        from test_aether_public_sources import PRICE_TEXT
        for amount in ("0.080000000000000001", "0.09", "0"):
            with self.subTest(amount=amount), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof:
                replace_source(proof, "pricing", PRICE_TEXT.replace("$0.08", "$" + amount))
                with self.assertRaisesRegex(CredentialError, "spend_limit"):
                    guard.load_paid_proof("fixture-project")

    def test_malformed_modified_or_expired_receipts_do_not_authorize(self):
        cases = [("schema_version", True), ("schema_version", 1),
                 ("model", "lyria-3-clip-preview"), ("provider_permission_documented", False),
                 ("generation_authorized", True), ("kind", "not_provider_sources"),
                 ("provider_base_price_usd", 0.08), ("provider_base_price_usd", "0.01"),
                 ("checked_at", "2026-10-31T21:00:00Z"),
                 ("expires_at", "2026-10-30T21:20:00Z"), ("expires_at", "2099-01-01T00:00:00Z")]
        for key, value in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof:
                proof[key] = value
                atomic_json(guard.PROOF_PATH, proof)
                with self.assertRaises(CredentialError):
                    guard.load_paid_proof("fixture-project")

    def test_both_terms_and_model_permission_are_rechecked_not_boolean_only(self):
        for source in ("model", "preview"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof:
                replace_source(proof, source, "FICTIONAL updated terms without Lyria permission")
                with self.assertRaises(CredentialError):
                    guard.load_paid_proof("fixture-project")

    def test_source_paths_urls_and_symlinks_are_not_trusted(self):
        for defect in ("url", "path", "symlink"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof:
                source = proof["sources"]["model"]
                if defect == "url":
                    source["reference"] = "https://example.invalid/terms"
                elif defect == "path":
                    source["path"] = "../private.txt"
                else:
                    path = guard.PROOF_PATH.parent / source["path"]
                    target = guard.PROOF_PATH.parent / "other.txt"
                    path.rename(target)
                    path.symlink_to(target)
                atomic_json(guard.PROOF_PATH, proof)
                with self.assertRaises(CredentialError):
                    guard.load_paid_proof("fixture-project")

    def test_every_source_and_project_bound_hash_are_rechecked(self):
        for name in ("pricing", "model", "preview", "terms"):
            with self.subTest(source=name), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof:
                expected = guard.load_paid_proof("fixture-project")["proof_sha256"]
                (guard.PROOF_PATH.parent / proof["sources"][name]["path"]).write_bytes(b"changed")
                with self.assertRaisesRegex(CredentialError, "evidence_integrity"):
                    guard.load_paid_proof("fixture-project", expected_sha256=expected)
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof:
            expected = guard.load_paid_proof("fixture-project")["proof_sha256"]
            with self.assertRaisesRegex(CredentialError, "cost_proof_changed"):
                guard.load_paid_proof("other-project", expected_sha256=expected)
            proof["provider_permission_documented"] = False
            atomic_json(guard.PROOF_PATH, proof)
            with self.assertRaisesRegex(CredentialError, "cost_proof_changed"):
                guard.load_paid_proof("fixture-project", expected_sha256=expected)

    def test_missing_proof_never_reads_token_or_calls_paid_transport(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria_generate, "access_token") as auth, patch.object(lyria_generate, "urlopen") as wire:
            guard.PROOF_PATH.unlink()
            with self.assertRaisesRegex(CredentialError, "provider_sources_missing"):
                lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=Path(temporary) / "lyria")
            auth.assert_not_called()
            wire.assert_not_called()
            self.assertFalse((Path(temporary) / "lyria").exists())

    def test_one_wire_request_has_durable_intent_and_bound_evidence(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria_generate, "access_token", return_value="fixture-token"):
            output = Path(temporary) / "lyria"
            def wire(request, **kwargs):
                intent = json.loads(next(output.glob("*/manifest.json")).read_text())
                self.assertEqual("request_started", intent["state"])
                self.assertTrue(intent["dispatch_started"])
                self.assertEqual("0.08", intent["cost_proof"]["provider_base_price_usd"])
                self.assertNotIn("fixture-token", json.dumps(intent))
                return response_fixture()
            with patch.object(lyria_generate, "urlopen", side_effect=wire) as transport:
                result = lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=output)
            transport.assert_called_once()
            self.assertEqual("generated", result["state"])
            self.assertEqual(1, len(result["candidates"]))

    def test_time_crossing_during_token_and_intent_fsync_causes_zero_post(self):
        for boundary in ("token", "intent_fsync"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
                 patch.object(lyria_generate, "urlopen") as transport:
                clock = [NOW]
                def token():
                    if boundary == "token":
                        clock[0] = datetime(2026, 10, 30, 23, tzinfo=timezone.utc)
                    return "fixture"
                def save(path, value):
                    atomic_json(path, value)
                    if boundary == "intent_fsync" and value.get("state") == "request_started":
                        clock[0] = datetime(2026, 10, 30, 23, tzinfo=timezone.utc)
                with patch.object(guard, "utc_now", side_effect=lambda: clock[0]), \
                     patch.object(lyria_generate, "access_token", side_effect=token), \
                     patch.object(lyria_generate, "atomic_json", side_effect=save):
                    with self.assertRaisesRegex(CredentialError, "generation_window_closed"):
                        lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=Path(temporary) / "lyria")
                transport.assert_not_called()
                for path in (Path(temporary) / "lyria").glob("*/manifest.json"):
                    self.assertEqual("not_sent", json.loads(path.read_text())["state"])

    def test_source_mutation_during_fsync_causes_zero_post(self):
        for source in ("pricing", "model"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
                 patch.object(lyria_generate, "urlopen") as wire, \
                 patch.object(lyria_generate, "access_token", return_value="fixture"):
                def save(path, value):
                    atomic_json(path, value)
                    if value.get("state") == "request_started":
                        (guard.PROOF_PATH.parent / json.loads(guard.PROOF_PATH.read_text())["sources"][source]["path"]).write_bytes(b"changed after fsync")
                with patch.object(lyria_generate, "atomic_json", side_effect=save), self.assertRaisesRegex(CredentialError, "evidence_integrity"):
                    lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=Path(temporary) / "lyria")
                wire.assert_not_called()

    def test_uncertain_exception_never_authorizes_second_post_or_next_slot(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria_generate, "access_token", return_value="fixture"), \
             patch.object(lyria_generate, "urlopen", side_effect=TimeoutError("fixture timeout")) as wire:
            output = Path(temporary) / "lyria"
            with self.assertRaisesRegex(CredentialError, "lyria_network_error"):
                lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=output)
            intent = next(output.glob("*/manifest.json"))
            before = intent.read_bytes()
            for title in ("Fixture Road", "Different Fixture Road"):
                with self.assertRaisesRegex(CredentialError, "generation_uncertain"):
                    lyria_generate.generate(title, "Instrumental travel", slot=SLOT, execute=True, output_root=output)
            self.assertEqual(1, wire.call_count)
            self.assertEqual(before, intent.read_bytes())

    def test_stale_rejected_and_standalone_intents_are_checked_without_mutation(self):
        for relative in ("singles/jobs/old-rejected/lyria/run/manifest.json", "lyria/old-run/manifest.json"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
                 patch.object(lyria_generate, "access_token") as token, patch.object(lyria_generate, "urlopen") as wire:
                path = Path(temporary) / relative
                path.parent.mkdir(parents=True)
                atomic_json(path, {"state": "request_started", "slot": "2026-09-26"})
                before = path.read_bytes()
                with self.assertRaisesRegex(CredentialError, "generation_uncertain"):
                    lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=Path(temporary) / "lyria")
                token.assert_not_called()
                wire.assert_not_called()
                self.assertEqual(before, path.read_bytes())

    def test_manifest_cannot_read_external_source_or_follow_job_symlink(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)):
            root = Path(temporary)
            run = root / "singles/jobs/a/lyria/run"
            run.mkdir(parents=True)
            outside = root / "not-aether-candidate.txt"
            outside.write_bytes(b"private fixture; must not be opened by scanner")
            atomic_json(run / "manifest.json", {"state": "generated", "candidates": [{"file": str(outside), "sha256": file_hash(outside)}]})
            with self.assertRaisesRegex(CredentialError, "manifest_invalid"):
                guard.require_no_unsettled_intents()
            (run / "manifest.json").unlink()
            atomic_json(run / "manifest.json", {"state": "request_started"})
            (root / "singles/jobs/link").symlink_to(root / "singles/jobs/a", target_is_directory=True)
            with self.assertRaises(CredentialError):
                guard.require_no_unsettled_intents()

    def test_unreadable_subtrees_and_replaced_roots_are_not_empty_inventory(self):
        for relative in ("singles/jobs", "singles/jobs/a", "singles/jobs/a/lyria", "singles/jobs/a/lyria/run"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)):
                root = Path(temporary)
                manifest = root / "singles/jobs/a/lyria/run/manifest.json"
                manifest.parent.mkdir(parents=True)
                atomic_json(manifest, {"state": "request_started"})
                blocked = root / relative
                blocked.chmod(0)
                try:
                    with self.assertRaises(CredentialError):
                        guard.require_no_unsettled_intents()
                finally:
                    blocked.chmod(0o700)
                self.assertEqual("request_started", json.loads(manifest.read_text())["state"])
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)):
            (Path(temporary) / "singles").write_bytes(b"not a directory")
            with self.assertRaisesRegex(CredentialError, "manifest_invalid"):
                guard.require_no_unsettled_intents()

    def test_permission_error_is_not_swallowed_by_glob(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(guard.os, "scandir", side_effect=PermissionError("fixture unreadable")):
            (Path(temporary) / "lyria").mkdir()
            with self.assertRaisesRegex(CredentialError, "manifest_unreadable"):
                guard.require_no_unsettled_intents()

    def test_raw_request_requires_exact_unused_intent_even_with_valid_evidence(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria_generate, "access_token") as token, patch.object(lyria_generate, "urlopen") as wire:
            with self.assertRaisesRegex(CredentialError, "charge_intent_required"):
                lyria_generate.request_song("fixture-project", "prompt", slot=SLOT)
            token.assert_not_called()
            wire.assert_not_called()

    def test_model_configuration_proof_and_expiry_change_after_intent_fsync(self):
        for changed in ("model", "enabled", "proof", "expired"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)) as proof, \
                 patch.object(lyria_generate, "access_token", return_value="fixture"), \
                 patch.object(lyria_generate, "urlopen") as wire:
                config = dict(SETTINGS)
                clock = [NOW]
                def save(path, value):
                    atomic_json(path, value)
                    if value.get("state") == "request_started":
                        if changed == "model":
                            proof["model"] = "lyria-3-clip-preview"
                            atomic_json(guard.PROOF_PATH, proof)
                        elif changed == "enabled":
                            config["enabled"] = False
                        elif changed == "proof":
                            proof["provider_permission_documented"] = False
                            atomic_json(guard.PROOF_PATH, proof)
                        else:
                            clock[0] = NOW + timedelta(days=1)
                with patch.object(lyria_generate, "atomic_json", side_effect=save), \
                     patch.object(lyria_generate, "load_settings", return_value=config), \
                     patch.object(guard, "utc_now", side_effect=lambda: clock[0]), self.assertRaises(CredentialError):
                    lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=Path(temporary) / "lyria")
                wire.assert_not_called()

    def test_intent_mismatch_before_post_preserves_external_bytes(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria_generate, "access_token", return_value="fixture"), \
             patch.object(lyria_generate, "urlopen") as wire:
            changed = []
            def save(path, value):
                atomic_json(path, value)
                if value.get("state") == "request_started":
                    other = {**value, "prompt_sha256": "f" * 64, "external_revision": "preserve"}
                    atomic_json(path, other)
                    changed.append((path, path.read_bytes()))
            with patch.object(lyria_generate, "atomic_json", side_effect=save), self.assertRaisesRegex(CredentialError, "charge_intent_invalid"):
                lyria_generate.generate("Fixture Road", "Instrumental travel", slot=SLOT, execute=True, output_root=Path(temporary) / "lyria")
            wire.assert_not_called()
            self.assertEqual(1, len(changed))
            self.assertEqual(changed[0][1], changed[0][0].read_bytes())

    def test_rejected_uncertain_intent_does_not_modify_existing_public_ids_or_queue(self):
        from test_aether_single import SingleTests
        fixture = SingleTests()
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary).resolve()), \
             patch.object(aether_single, "select_candidate", return_value={
                 "candidate_index": 1, "path": str(Path(temporary) / "audio.mp3"),
                 "duration_seconds": 184, "sha256": "a" * 64}):
            # macOS tempfile paths may start with /var -> /private/var. Use the
            # canonical owned fixture, never weaken the production symlink gate.
            root = Path(temporary).resolve() / "singles"
            created = aether_single.worker(root, slot="2026-09-26", title="Fixture Old Road",
                style="Warm fantasy travel", lane="skybound_flight", execute=True,
                music_generator=fixture.fake_music, cover_generator=fixture.fake_cover, renderer=fixture.fake_renderer)
            state = json.loads((root / "queue.json").read_text())
            job = state["jobs"][created["job_id"]]
            job.update(status="published", thumbnail_status="set", upload={"video_id": "abcdefghijk", "channel_id": "UC" + "x" * 22})
            old = json.loads(json.dumps(job))
            old.update(id="f" * 24, status="rejected", upload=None, music=None)
            state["jobs"][old["id"]] = old
            atomic_json(root / "queue.json", state)
            manifest = root / "jobs" / old["id"] / "lyria" / "old-run" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            atomic_json(manifest, {"state": "request_started"})
            before = (root / "queue.json").read_bytes()
            for existing_only in (True, False):
                with self.subTest(existing_only=existing_only), self.assertRaisesRegex(CredentialError, "generation_uncertain"):
                    aether_single.worker(root, slot=SLOT, title="Fixture New Road", style="Travel", lane="frontier_surge",
                        execute=True, publish=True, existing_only=existing_only,
                        api_factory=Mock(side_effect=AssertionError("no provider access")))
                self.assertEqual(before, (root / "queue.json").read_bytes())
            self.assertEqual("abcdefghijk", json.loads(before)["jobs"][created["job_id"]]["upload"]["video_id"])

    def test_canonical_fixture_path_does_not_relax_queue_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target, alias = root / "canonical", root / "alias"
            target.mkdir(mode=0o700)
            alias.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(Exception, "unsafe_report_directory"):
                aether_single.SingleQueue(alias / "singles")
            queue = aether_single.SingleQueue(alias.resolve() / "singles")
            self.assertEqual(target / "singles", queue.root)


class OwnedInventoryTests(unittest.TestCase):
    def provider(self, *, privacy="private", title="Fixture Road", incomplete=False, cycle=False):
        channel, playlist = "UC" + "x" * 22, "UU" + "x" * 22
        calls = []
        def request(method, url, **kwargs):
            self.assertEqual("GET", method)
            calls.append(url)
            if "channels?" in url:
                return 200, {}, {"items": [{"id": channel, "contentDetails": {"relatedPlaylists": {"uploads": playlist}}}]}
            if "playlistItems?" in url:
                page = {"items": [{"contentDetails": {"videoId": "abcdefghijk"}}]}
                if cycle:
                    page["nextPageToken"] = "same"
                return 200, {}, page
            if "videos?" in url:
                return 200, {}, {"items": [] if incomplete else [{"id": "abcdefghijk",
                    "snippet": {"channelId": channel, "title": title},
                    "status": {"privacyStatus": privacy, "publishAt": "2026-10-31T00:00:00Z"},
                    "processingDetails": {"processingStatus": "processing"}}]}
            raise AssertionError(url)
        return SimpleNamespace(channel=channel, headers=lambda: {}, request=request, calls=calls)

    def test_private_scheduled_processing_and_public_title_collisions_hold(self):
        for privacy in ("private", "public", "unlisted"):
            with self.subTest(privacy=privacy), self.assertRaisesRegex(Exception, "existing_remote_title_requires_reconcile"):
                aether_single.require_no_owned_title_match(self.provider(privacy=privacy), "Fixture Road")

    def test_complete_absence_is_not_public_search_absence(self):
        api = self.provider(title="Different Fixture Title")
        aether_single.require_no_owned_title_match(api, "Fixture Road")
        self.assertEqual(3, len(api.calls))
        self.assertTrue(all("search?" not in url for url in api.calls))

    def test_missing_video_permission_and_incomplete_pagination_hold(self):
        for api in (self.provider(incomplete=True), self.provider(title="Other", cycle=True),
                    SimpleNamespace(channel="UC" + "x" * 22, headers=lambda: {}, request=Mock(side_effect=short_video_youtube.UploadError("insufficient_permissions")))):
            with self.subTest(api=api), self.assertRaises(Exception):
                aether_single.require_no_owned_title_match(api, "Fixture Road")


class UploadBoundaryTests(unittest.TestCase):
    def prepared(self, root):
        root.chmod(0o700)
        folder = root / "jobs" / "fixture"
        folder.mkdir(parents=True, mode=0o700)
        (folder / "video.mp4").write_bytes(b"fixture video")
        job = {"id": "fixture", "status": "rendered", "upload_eligible": True,
               "payload_hash": "a" * 64,
               "brief": aether_single.brief_for({"title": "Fixture Road", "style": "Travel", "lane": "skybound_flight"}),
               "result": {"job_id": "fixture", "test_only": False, "upload_eligible": True,
                          "sha256": {"video.mp4": file_hash(folder / "video.mp4")}}}
        state = {"jobs": {"fixture": job}}
        clock = [datetime(2026, 10, 30, 23, 59, 59, tzinfo=timezone.utc)]
        q = SimpleNamespace(root=root, state_path=root / "queue.json", clock=lambda: clock[0], _render=lambda *args: None)
        uploader = Uploader(q)
        uploader.bind_approval_locked(state, job, {"made_for_kids": False, "synthetic_media": True,
            "privacy": "private", "publish_at": "2026-10-31T00:00:00Z", "publish_approved": True})
        from test_aether_single import Provider
        return uploader, state, job, Provider(), clock

    def test_first_upload_post_after_intent_save_crosses_nine_and_never_retries(self):
        with tempfile.TemporaryDirectory() as temporary:
            uploader, state, job, api, clock = self.prepared(Path(temporary))
            def save(path, value):
                atomic_json(path, value)
                if job.get("upload", {}).get("phase") == "initiating":
                    clock[0] = datetime(2026, 10, 31, tzinfo=timezone.utc)
            with patch.object(short_video_youtube, "atomic_json", side_effect=save):
                result = uploader.run_locked(state, job, api=api)
            self.assertEqual("stale_or_nonprivate_schedule", result["error"])
            self.assertEqual(0, api.inserts)
            clock[0] -= timedelta(seconds=2)
            uploader.run_locked(state, job, api=api)
            self.assertEqual(0, api.inserts)

    def test_known_session_probe_and_accepted_id_observation_survive_after_nine(self):
        with tempfile.TemporaryDirectory() as temporary:
            uploader, state, job, api, clock = self.prepared(Path(temporary))
            video = uploader.q.root / "jobs/fixture/video.mp4"
            job["upload"] = {"phase": "session_ready", "channel_id": api.channel,
                             "size": video.stat().st_size, "sha256": file_hash(video)}
            atomic_json(video.parent / "youtube-session.json", {"url": "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&upload_id=fixture"})
            clock[0] = datetime(2026, 10, 31, tzinfo=timezone.utc)
            self.assertEqual("published", uploader.run_locked(state, job, api=api, reconcile=True)["status"])
            self.assertEqual("abcdefghijk", job["upload"]["video_id"])
            self.assertEqual("published", uploader.run_locked(state, job, api=api, reconcile=True)["status"])
            self.assertEqual(0, api.inserts)


if __name__ == "__main__":
    unittest.main()
