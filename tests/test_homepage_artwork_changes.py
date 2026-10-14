"""Synthetic local Git fixtures only; these are not approved app candidates."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_homepage_artwork_changes as probe


def expected(slug="app", raw=b"synthetic-image-one", candidate="a"):
    return {"status": "staged_not_published", "app_slug": slug,
            "version": "1.2.3+4", "source_commit": "b" * 40,
            "candidate_sha256": candidate * 64,
            "assets": [{"locale": "en", "kind": "android", "index": 1,
                        "site_path": "en/01.png", "size": [1080, 2160],
                        "sha256": hashlib.sha256(raw).hexdigest()}]}


def report_app(receipt):
    slug = receipt["app_slug"]
    return {"app_slug": slug, "status": "staged_not_published", "expected": receipt,
            "staged_paths": [f"public/release-artwork/{slug}.json"] + [
                f"src/content/apps/{slug}/assets/screenshots/{asset['site_path']}"
                for asset in receipt["assets"]]}


def trigger(run_id="123", attempt="1"):
    identity = probe.app_identity(expected())
    return {"schema_version": 1, "run_id": run_id, "run_attempt": attempt,
            "status": "artwork_changed", "apps": [identity]}


class LocalChangeProbe(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.engine = self.root / "engine"
        (self.engine / "data").mkdir(parents=True)
        self.site = self.root / "site"
        self.site.mkdir()
        self.work = self.root / "work"
        self.trigger = self.engine / probe.TRIGGER
        self.report = self.root / "report.json"
        self.output = self.root / "github-output"
        self.receipt = expected()
        self.put(self.receipt, b"synthetic-image-one")
        (self.site / "README.md").write_text("Unrelated tracked content\n")
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic local baseline")
        self.before_head = self.git("rev-parse", "HEAD").strip()
        self.root_patch = patch.object(probe, "ROOT", self.engine)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.site), *args],
                                       text=True, stderr=subprocess.PIPE)

    def put(self, receipt, raw):
        for name in report_app(receipt)["staged_paths"]:
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(json.dumps(receipt).encode() if name.endswith(".json") else raw)

    def sandbox(self):
        # Isolation is mocked, never enabled or bypassed by these unit tests.
        return None

    def run_probe(self, receipt=None, raw=None, *, apps=None, mutate=None, run_id="123", attempt="1"):
        def stage(releases, stores, site, gate, work):
            sandbox.assert_called_once_with()
            self.assertEqual(releases, self.engine / "data/app_releases.csv")
            self.assertEqual(stores, self.engine / "data/store_versions.csv")
            self.assertEqual(site, self.site)
            self.assertIsNone(gate)
            self.assertEqual(work.name, "apps")
            if receipt is not None:
                self.put(receipt, raw or b"synthetic-image-one")
            if mutate:
                mutate()
            return {"schema_version": 1, "status": "staged_not_published",
                    "apps": copy.deepcopy(apps if apps is not None else [report_app(receipt or self.receipt)])}
        with patch.object(probe, "sandbox_preflight", side_effect=self.sandbox) as sandbox, \
             patch.object(probe, "stage_all", side_effect=stage) as stage_mock:
            result = probe.stage_changes(self.site, run_id, attempt, self.work, self.trigger)
        sandbox.assert_called_once_with()
        stage_mock.assert_called_once()
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.before_head)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")
        return result

    def test_identical_candidate_and_image_bytes_never_create_trigger(self):
        result = self.run_probe(self.receipt)
        self.assertFalse(result["changed"])
        self.assertEqual(result["status"], "no_artwork_changes")
        self.assertFalse(self.trigger.exists())

    def test_candidate_change_writes_minimal_sanitized_trigger(self):
        receipt = expected(candidate="c")
        app = report_app(receipt)
        app["private_notes"] = "must not enter trigger"
        result = self.run_probe(receipt, apps=[app])
        actual = json.loads(self.trigger.read_text())
        self.assertTrue(result["changed"])
        self.assertEqual(actual["apps"], [probe.app_identity(receipt)])
        self.assertEqual(set(actual), {"schema_version", "run_id", "run_attempt", "status", "apps"})
        self.assertTrue(probe.gate_auto_publication(actual, "123", "1"))
        self.assertNotIn("private_notes", self.trigger.read_text())
        self.assertEqual(result["apps"][0]["changed_paths"], ["public/release-artwork/app.json"])

    def test_changed_image_bytes_are_real_changes_even_with_same_identity(self):
        raw = b"synthetic-image-two"
        result = self.run_probe(expected(raw=raw), raw)
        self.assertTrue(result["changed"])
        self.assertIn("src/content/apps/app/assets/screenshots/en/01.png", result["apps"][0]["changed_paths"])

    def test_new_untracked_expected_receipt_detected(self):
        receipt_path = "public/release-artwork/app.json"
        self.git("rm", receipt_path)
        self.git("commit", "-qm", "No previous receipt")
        self.before_head = self.git("rev-parse", "HEAD").strip()
        result = self.run_probe(self.receipt)
        self.assertTrue(result["changed"])
        self.assertEqual(result["apps"][0]["changed_paths"], [receipt_path])

    def test_restoring_uncommitted_deleted_receipt_to_head_does_not_trigger(self):
        (self.site / "public/release-artwork/app.json").unlink()
        result = self.run_probe(self.receipt)
        self.assertFalse(result["changed"])
        self.assertFalse(self.trigger.exists())

    def test_existing_untracked_identical_receipt_not_falsely_new(self):
        self.git("rm", "--cached", "public/release-artwork/app.json")
        self.git("commit", "-qm", "Receipt intentionally untracked")
        self.before_head = self.git("rev-parse", "HEAD").strip()
        self.assertFalse(self.run_probe(self.receipt)["changed"])

    def test_old_trigger_is_not_rewritten_or_removed_on_noop(self):
        original = json.dumps(trigger("122"), separators=(",", ":")).encode()
        self.trigger.write_bytes(original)
        before = self.trigger.stat().st_mtime_ns
        result = self.run_probe(self.receipt)
        self.assertFalse(result["changed"])
        self.assertEqual(self.trigger.read_bytes(), original)
        self.assertEqual(self.trigger.stat().st_mtime_ns, before)
        self.assertFalse(probe.gate_auto_publication(json.loads(original), "123", "1"))

    def test_deleted_stale_trigger_stays_deleted_on_noop(self):
        self.trigger.write_text(json.dumps(trigger("122")))
        self.trigger.unlink()
        self.assertFalse(self.run_probe(self.receipt)["changed"])
        self.assertFalse(self.trigger.exists())

    def test_same_run_repeat_preserves_exact_trigger_bytes_and_mtime(self):
        receipt = expected(candidate="c")
        self.assertTrue(self.run_probe(receipt)["changed"])
        original, before = self.trigger.read_bytes(), self.trigger.stat().st_mtime_ns
        self.assertFalse(self.run_probe(receipt)["changed"])
        self.assertEqual(self.trigger.read_bytes(), original)
        self.assertEqual(self.trigger.stat().st_mtime_ns, before)

    def test_rerun_attempt_cannot_reuse_previous_attempt_trigger(self):
        receipt = expected(candidate="c")
        self.run_probe(receipt)
        original = self.trigger.read_bytes()
        self.assertFalse(self.run_probe(receipt, attempt="2")["changed"])
        self.assertEqual(self.trigger.read_bytes(), original)
        self.assertFalse(probe.gate_auto_publication(json.loads(original), "123", "2"))

    def test_timestamp_and_format_only_receipt_changes_do_not_trigger(self):
        receipt = dict(self.receipt, checked_at="2030-01-01T00:00:00Z")
        self.assertFalse(self.run_probe(receipt)["changed"])
        self.assertFalse(self.trigger.exists())
        self.assertFalse(self.run_probe(self.receipt)["changed"])
        self.assertFalse(self.trigger.exists())

    def test_preexisting_dirty_artwork_and_unrelated_status_changes_do_not_trigger(self):
        self.put(expected(candidate="c"), b"synthetic-image-one")
        (self.site / "README.md").write_text("Existing unrelated manual work\n")
        unrelated = self.site / "public/ops/index.html"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("Local dashboard timestamp changed\n")
        self.assertFalse(self.run_probe(expected(candidate="c"))["changed"])
        self.assertEqual((self.site / "README.md").read_text(), "Existing unrelated manual work\n")
        self.assertEqual(unrelated.read_text(), "Local dashboard timestamp changed\n")
        self.assertFalse(self.trigger.exists())

    def test_blocked_apps_keep_reason_and_cannot_create_trigger(self):
        blocked = {"app_slug": "app", "status": "blocked", "reason": "Current candidate lacks independent review"}
        result = self.run_probe(apps=[blocked])
        self.assertFalse(result["changed"])
        self.assertEqual(result["apps"], [blocked])
        self.assertFalse(self.trigger.exists())

    def test_independent_valid_change_can_proceed_with_blocked_app(self):
        receipt = expected(candidate="c")
        blocked = {"app_slug": "other", "status": "blocked", "reason": "Store observation stale"}
        result = self.run_probe(receipt, apps=[blocked, report_app(receipt)])
        self.assertTrue(result["changed"])
        self.assertEqual(result["apps"][0]["reason"], "Store observation stale")
        self.assertEqual([a["app_slug"] for a in json.loads(self.trigger.read_text())["apps"]], ["app"])

    def test_no_public_release_is_noop_without_trigger(self):
        self.assertFalse(self.run_probe(apps=[])["changed"])
        self.assertFalse(self.trigger.exists())

    def test_arbitrary_paths_and_mismatched_expected_bytes_block(self):
        for kind in ("extra-path", "traversal", "different-receipt", "wrong-hash"):
            with self.subTest(kind=kind):
                receipt = expected(candidate="c")
                app = report_app(receipt)
                mutate = None
                if kind == "extra-path":
                    app["staged_paths"].append("README.md")
                elif kind == "traversal":
                    app["expected"]["assets"][0]["site_path"] = "en/../../README.md"
                elif kind == "different-receipt":
                    mutate = lambda: (self.site / "public/release-artwork/app.json").write_text("{}")
                else:
                    mutate = lambda: (self.site / "src/content/apps/app/assets/screenshots/en/01.png").write_bytes(b"unexpected")
                # Keep the actual file-writing fixture bounded even for a bad report.
                result = self.run_probe(expected(candidate="c"), apps=[app], mutate=mutate)
                self.assertFalse(result["changed"])
                self.assertEqual(result["apps"][0]["status"], "blocked")
                self.assertFalse(self.trigger.exists())

    def test_stage_cannot_write_trigger_to_arbitrary_destination(self):
        with patch.object(probe, "sandbox_preflight") as sandbox:
            with self.assertRaisesRegex(ValueError, "Only data"):
                probe.stage_changes(self.site, "123", "1", self.work, self.root / "unexpected.json")
        sandbox.assert_not_called()

    def test_symlink_artwork_path_is_not_followed(self):
        outside = self.root / "outside.png"
        outside.write_bytes(b"preserve")
        image = self.site / "src/content/apps/app/assets/screenshots/en/01.png"
        image.unlink()
        image.symlink_to(outside)
        result = self.run_probe(apps=[report_app(self.receipt)])
        self.assertFalse(result["changed"])
        self.assertEqual(result["apps"][0]["status"], "blocked")
        self.assertFalse(self.trigger.exists())
        self.assertEqual(outside.read_bytes(), b"preserve")

    def test_unselected_unsafe_gallery_does_not_block_independent_valid_app(self):
        outside = self.root / "outside.png"
        outside.write_bytes(b"preserve")
        unrelated = self.site / "src/content/apps/other/assets/screenshots/en/01.png"
        unrelated.parent.mkdir(parents=True)
        unrelated.symlink_to(outside)
        result = self.run_probe(expected(candidate="c"))
        self.assertTrue(result["changed"])
        self.assertEqual(outside.read_bytes(), b"preserve")
        self.assertEqual([app["app_slug"] for app in json.loads(self.trigger.read_text())["apps"]], ["app"])

    def test_symlink_trigger_is_rejected_before_network(self):
        outside = self.root / "outside.json"
        outside.write_text("preserve")
        self.trigger.symlink_to(outside)
        with patch.object(probe, "sandbox_preflight") as sandbox:
            with self.assertRaisesRegex(ValueError, "Symlink"):
                probe.stage_changes(self.site, "123", "1", self.work, self.trigger)
        sandbox.assert_not_called()
        self.assertEqual(outside.read_text(), "preserve")

    def test_fresh_work_directory_and_one_sandbox_check_for_every_invocation(self):
        with patch.object(probe, "sandbox_preflight", side_effect=self.sandbox) as sandbox, \
             patch.object(probe, "stage_all", side_effect=lambda *args: {"apps": []}) as stage:
            for _ in range(2):
                probe.stage_changes(self.site, "123", "1", self.work, self.trigger)
        self.assertEqual(sandbox.call_count, 2)
        self.assertEqual(sandbox.call_args.args, ())
        directories = [call.args[4].parent for call in stage.call_args_list]
        self.assertTrue(all(call.args[3] is None for call in stage.call_args_list))
        self.assertNotEqual(*directories)
        self.assertTrue(all(not path.exists() for path in directories))
        with patch.object(probe, "sandbox_preflight") as sandbox, patch.object(probe.subprocess, "run") as run:
            self.assertTrue(probe.gate_auto_publication(trigger(), "123", "1"))
        sandbox.assert_not_called()
        run.assert_not_called()

    def test_stage_cli_safe_boolean_output(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                self.output.unlink(missing_ok=True)
                result = {"schema_version": 1, "status": "artwork_changed" if changed else "no_artwork_changes",
                          "apps": [], "changed": changed}
                with patch.object(probe, "stage_changes", return_value=result) as stage, redirect_stdout(io.StringIO()):
                    code = probe.main(["stage", "--site", str(self.site), "--run-id", "123", "--run-attempt", "1",
                                       "--work-dir", str(self.work), "--trigger", str(self.trigger),
                                       "--report", str(self.report), "--github-output", str(self.output)])
                self.assertEqual(code, 0)
                self.assertEqual(self.output.read_text(), f"changed={str(changed).lower()}\n")
                self.assertEqual(json.loads(self.report.read_text()), result)
                self.assertEqual(stage.call_args.args[1:3], ("123", "1"))

    def test_cli_authorization_missing_malformed_or_stale_is_successful_noop(self):
        for raw in (None, "not-json", "[]", json.dumps(trigger("122")), json.dumps(trigger(attempt="2"))):
            with self.subTest(raw=raw):
                self.trigger.unlink(missing_ok=True)
                self.output.unlink(missing_ok=True)
                if raw is not None:
                    self.trigger.write_text(raw)
                with patch.object(probe, "sandbox_preflight") as sandbox, redirect_stdout(io.StringIO()):
                    code = probe.main(["authorize", "--trigger", str(self.trigger), "--source-run-id", "123",
                                       "--source-run-attempt", "1", "--github-output", str(self.output)])
                sandbox.assert_not_called()
                self.assertEqual(code, 0)
                self.assertEqual(self.output.read_text(), "authorized=false\n")
                self.assertEqual(self.trigger.read_text() if self.trigger.exists() else None, raw)

    def test_cli_exact_authorization_true(self):
        self.trigger.write_text(json.dumps(trigger()))
        with redirect_stdout(io.StringIO()):
            code = probe.main(["authorize", "--trigger", str(self.trigger), "--source-run-id", "123",
                               "--source-run-attempt", "1", "--github-output", str(self.output)])
        self.assertEqual(code, 0)
        self.assertEqual(self.output.read_text(), "authorized=true\n")

    def test_denied_sandbox_has_no_trigger_or_retry(self):
        original = json.dumps(trigger("122")).encode()
        self.trigger.write_bytes(original)
        error = ValueError("Artwork sandbox blocked: secret-token-never-print")
        with patch.object(probe, "sandbox_preflight", side_effect=error) as sandbox, \
             patch.object(probe, "stage_all") as stage, redirect_stderr(io.StringIO()) as stderr:
            code = probe.main(["stage", "--site", str(self.site), "--run-id", "123", "--run-attempt", "1",
                               "--work-dir", str(self.work), "--trigger", str(self.trigger),
                               "--report", str(self.report), "--github-output", str(self.output)])
        self.assertEqual(code, 1)
        self.assertEqual(self.output.read_text(), "changed=false\n")
        report = json.loads(self.report.read_text())
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["changed"])
        self.assertIn("Artwork sandbox unavailable", report["reason"])
        self.assertNotIn("secret-token", stderr.getvalue() + self.report.read_text())
        self.assertEqual(self.trigger.read_bytes(), original)
        sandbox.assert_called_once()
        stage.assert_not_called()
        self.assertEqual(list(self.work.iterdir()), [])

    def test_missing_sandbox_fails_closed(self):
        with patch.object(probe, "sandbox_preflight", side_effect=FileNotFoundError("sandbox unavailable")) as sandbox, \
             patch.object(probe, "stage_all") as stage:
            with self.assertRaises(probe.PreflightBlocked) as caught:
                probe.stage_changes(self.site, "123", "1", self.work, self.trigger)
        self.assertFalse(caught.exception.report["changed"])
        self.assertEqual(caught.exception.report["status"], "blocked")
        self.assertFalse(self.trigger.exists())
        sandbox.assert_called_once_with()
        stage.assert_not_called()
        self.assertEqual(list(self.work.iterdir()), [])

    def test_invalid_stage_source_ids_rejected_before_sandbox(self):
        for run_id, attempt in (("123\nchanged=true", "1"), ("123", "0"), (123, "1")):
            with self.subTest(run_id=run_id, attempt=attempt), patch.object(probe, "sandbox_preflight") as sandbox:
                with self.assertRaises(ValueError):
                    probe.stage_changes(self.site, run_id, attempt, self.work, self.trigger)
                sandbox.assert_not_called()
                self.assertFalse(self.trigger.exists())

    def test_output_and_report_cannot_alias_trigger(self):
        original = json.dumps(trigger("122"))
        self.trigger.write_text(original)
        alias = self.engine / "data/../data/artwork-change-trigger.json"
        for flag in ("--report", "--github-output"):
            with self.subTest(flag=flag), patch.object(probe, "stage_changes") as stage, redirect_stderr(io.StringIO()):
                arguments = ["stage", "--site", str(self.site), "--run-id", "123", "--run-attempt", "1",
                             "--work-dir", str(self.work), "--trigger", str(self.trigger),
                             "--report", str(self.report), "--github-output", str(self.output)]
                arguments[arguments.index(flag) + 1] = str(alias)
                self.assertEqual(probe.main(arguments), 1)
                stage.assert_not_called()
                self.assertEqual(self.trigger.read_text(), original)

    def test_cli_errors_do_not_print_secret_diagnostics(self):
        with patch.object(probe, "stage_changes", side_effect=ValueError("secret-token-never-print")), \
             redirect_stderr(io.StringIO()) as stderr:
            code = probe.main(["stage", "--site", str(self.site), "--run-id", "123", "--run-attempt", "1",
                               "--work-dir", str(self.work), "--trigger", str(self.trigger), "--report", str(self.report)])
        self.assertEqual(code, 1)
        self.assertNotIn("secret-token", stderr.getvalue())
        self.assertFalse(self.trigger.exists())


class AuthorizationSchema(unittest.TestCase):
    def test_valid_exact_run_and_attempt_only(self):
        self.assertTrue(probe.gate_auto_publication(trigger(), "123", "1"))
        self.assertFalse(probe.gate_auto_publication(trigger(), "124", "1"))
        self.assertFalse(probe.gate_auto_publication(trigger(), "123", "2"))

    def test_invalid_schemas_fail_closed(self):
        values = [None, [], {}, "trigger", trigger()]
        values[-1]["apps"] = []
        for key, invalids in {
            "schema_version": [None, 2, True, "1"], "run_id": [None, 123, "0123", "123\nauthorized=true"],
            "run_attempt": [None, 1, "01"], "status": [None, "staged_not_published", "no_artwork_changes"],
            "apps": [{}, None, [None], ["app"]],
        }.items():
            for invalid in invalids:
                value = trigger()
                value[key] = invalid
                values.append(value)
        for key in ("schema_version", "run_id", "run_attempt", "status", "apps"):
            value = trigger()
            del value[key]
            values.append(value)
        extra = trigger()
        extra["timestamp"] = "irrelevant"
        values.append(extra)
        duplicate = trigger()
        duplicate["apps"] *= 2
        values.append(duplicate)
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(probe.gate_auto_publication(value, "123", "1"))

    def test_invalid_app_identity_and_extra_fields_fail_closed(self):
        for key, invalid in (("app_slug", "../other"), ("app_slug", "app\nnew=true"),
                             ("candidate_sha256", "a" * 63), ("source_commit", "b" * 39),
                             ("version", "1.2.3\nnew=true"), ("version", None), ("secret", "unrequested")):
            with self.subTest(key=key, invalid=invalid):
                value = trigger()
                value["apps"][0][key] = invalid
                self.assertFalse(probe.gate_auto_publication(value, "123", "1"))
        for key in probe.APP_KEYS:
            value = trigger()
            del value["apps"][0][key]
            self.assertFalse(probe.gate_auto_publication(value, "123", "1"))

    def test_source_ids_are_required_numeric_strings(self):
        for value in (None, 123, True, "0", "", "123\nauthorized=true"):
            with self.subTest(value=value):
                self.assertFalse(probe.gate_auto_publication(trigger(), value, "1"))
                self.assertFalse(probe.gate_auto_publication(trigger(), "123", value))


if __name__ == "__main__":
    unittest.main()
