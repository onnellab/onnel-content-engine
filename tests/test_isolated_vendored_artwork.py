"""Security-boundary tests use synthetic fixtures, not private template source.

No test here invokes bubblewrap or app code. The separate trusted --self-test
command is for the authorized Linux job and fails closed on denied namespaces.
"""
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import isolated_vendored_artwork as gate


class BundleFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repository"
        (self.repo / ".git/objects").mkdir(parents=True)
        (self.repo / ".git/HEAD").write_text("ref: refs/heads/main\n")
        (self.repo / ".git/config").write_text("[http]\n extraheader = SECRET\n")
        self.project = self.repo / "apps/example"
        self.bundle = self.project / gate.VENDORED
        self.bundle.mkdir(parents=True)
        (self.project / "pubspec.yaml").write_text("version: 1.2.3+4\n")
        adapter = b"# synthetic approved thin adapter, never executed\n"
        (self.project / gate.ROOT_ADAPTER).write_bytes(adapter)
        adapter_pin = patch.object(gate, "ROOT_ADAPTER_SHA256", hashlib.sha256(adapter).hexdigest())
        adapter_pin.start()
        self.addCleanup(adapter_pin.stop)
        self.contents = {"release_artwork.py": b"# synthetic unit-test gate\n",
                         "renderer.py": b"# synthetic unit-test dependency\n",
                         "header_icon_template.svg": b"<svg/>\n",
                         "README.md": b"Synthetic fixture documentation\n"}
        for name, payload in self.contents.items():
            (self.bundle / name).write_bytes(payload)
        self.hashes = {name: hashlib.sha256(payload).hexdigest() for name, payload in self.contents.items()}
        self.ledger = {"schema_version": 1, "repository": "onnellab/onnellab-flutter-template",
                       "source_directory": "template/assets/store_promo",
                       "source_commits": sorted(gate.SOURCE_COMMITS), "sha256": self.hashes}
        self.metadata = {"repository": self.ledger["repository"],
                         "source_directory": self.ledger["source_directory"],
                         "commit": "b6d2332c162a00285c3aa05186a47c0f6b18f5b4",
                         "preserved_safety_hardening": [], "sha256": dict(self.hashes)}
        self.write_metadata()
        self.allow = patch.object(gate, "load_allowlist", return_value=self.ledger)
        self.allow.start()
        self.addCleanup(self.allow.stop)
        self.addCleanup(self.temp.cleanup)

    def write_metadata(self):
        (self.bundle / "TEMPLATE_SOURCE.json").write_text(json.dumps(self.metadata))

    def validate(self):
        return gate.validate_vendored_bundle(self.project)


class CanonicalValidation(BundleFixture):
    def test_exact_bundle_preserves_git_root_and_monorepo_relative_path(self):
        result = self.validate()
        self.assertEqual(result.repository_root, self.repo)
        self.assertEqual(result.project_relative, PurePosixPath("apps/example"))
        self.assertEqual(result.file_hashes, self.hashes)
        self.assertEqual(result.files, self.contents)

    def test_root_app_project_is_supported(self):
        root_app = self.root / "root-app"
        self.project.rename(root_app)
        (self.repo / ".git").rename(root_app / ".git")
        result = gate.validate_vendored_bundle(root_app)
        self.assertEqual(result.repository_root, root_app)
        self.assertEqual(result.project_relative, PurePosixPath("."))

    def test_both_explicit_canonical_source_commits_are_accepted(self):
        for commit in gate.SOURCE_COMMITS:
            with self.subTest(commit=commit):
                self.metadata["commit"] = commit
                self.write_metadata()
                self.assertEqual(self.validate().source_commit, commit)

    def test_tag3_legacy_three_key_metadata_is_supported_with_exact_code_pins(self):
        self.metadata = {key: self.metadata[key] for key in ("repository", "commit", "sha256")}
        self.write_metadata()
        self.assertEqual(self.validate().files, self.contents)

    def test_legacy_metadata_cannot_authorize_custom_root_or_changed_import(self):
        self.metadata = {key: self.metadata[key] for key in ("repository", "commit", "sha256")}
        self.write_metadata()
        (self.bundle / "renderer.py").write_text("untrusted")
        with self.assertRaisesRegex(ValueError, "Noncanonical"):
            self.validate()
        (self.bundle / "renderer.py").write_bytes(self.contents["renderer.py"])
        (self.project / gate.ROOT_ADAPTER).write_text("custom root gate")
        with self.assertRaisesRegex(ValueError, "Unsupported custom root"):
            self.validate()

    def test_partial_rich_metadata_and_unknown_fields_are_rejected(self):
        original = dict(self.metadata)
        variants = [dict(original, custom_code="untrusted.py"),
                    {key: value for key, value in original.items() if key != "source_directory"},
                    {key: value for key, value in original.items() if key != "preserved_safety_hardening"}]
        for metadata in variants:
            with self.subTest(keys=set(metadata)):
                self.metadata = metadata
                self.write_metadata()
                with self.assertRaisesRegex(ValueError, "metadata shape"):
                    self.validate()

    def test_unrecognized_source_commit_and_source_location_are_rejected(self):
        for key, bad in (("commit", "a" * 40), ("repository", "other/template"),
                         ("source_directory", "elsewhere")):
            with self.subTest(key=key):
                old = self.metadata[key]
                self.metadata[key] = bad
                self.write_metadata()
                with self.assertRaisesRegex(ValueError, "source pin"):
                    self.validate()
                self.metadata[key] = old

    def test_modified_gate_or_import_or_static_dependency_is_rejected(self):
        for name, original in self.contents.items():
            with self.subTest(name=name):
                (self.bundle / name).write_bytes(original + b"modified")
                with self.assertRaisesRegex(ValueError, "Noncanonical"):
                    self.validate()
                (self.bundle / name).write_bytes(original)

    def test_app_cannot_self_authorize_new_hashes(self):
        (self.bundle / "renderer.py").write_text("raise RuntimeError('untrusted')\n")
        self.metadata["sha256"]["renderer.py"] = hashlib.sha256((self.bundle / "renderer.py").read_bytes()).hexdigest()
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "independent canonical"):
            self.validate()

    def test_custom_preserved_hardening_is_not_silently_trusted(self):
        self.metadata["preserved_safety_hardening"] = ["custom verification module"]
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "custom hardening"):
            self.validate()

    def test_custom_root_gate_is_not_bypassed_by_canonical_bundle(self):
        (self.project / gate.ROOT_ADAPTER).write_text("# Papira-like extra app-specific safety checks\n")
        with patch.object(gate.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Unsupported custom root.*reviewed bridge"):
                gate.run_verified_gate(self.project, "verify-site")
            run.assert_not_called()

    def test_incomplete_declared_map_is_rejected(self):
        self.metadata["sha256"].pop("renderer.py")
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "independent canonical"):
            self.validate()

    def test_missing_canonical_dependency_is_rejected(self):
        (self.bundle / "renderer.py").unlink()
        with self.assertRaisesRegex(ValueError, "Missing canonical"):
            self.validate()

    def test_extra_executables_bytecode_native_modules_and_static_files_are_rejected(self):
        for name in ("sitecustomize.py", "renderer.pyc", "renderer.pyo", "attack.so", "attack.pth",
                     "python3", "unexpected.svg", "unexpected.json", "__init__.py"):
            with self.subTest(name=name):
                extra = self.bundle / name
                extra.write_text("not authorized")
                with self.assertRaisesRegex(ValueError, "Unexpected vendored"):
                    self.validate()
                extra.unlink()

    def test_package_or_bytecode_directory_is_rejected(self):
        for name in ("__pycache__", "json", "new_package"):
            with self.subTest(name=name):
                extra = self.bundle / name
                extra.mkdir()
                with self.assertRaisesRegex(ValueError, "Unexpected vendored"):
                    self.validate()
                extra.rmdir()

    def test_app_root_import_injection_is_never_in_verified_code(self):
        (self.project / "json.py").write_text("raise RuntimeError('injected')")
        (self.repo / "sitecustomize.py").write_text("raise RuntimeError('injected')")
        result = self.validate()
        self.assertNotIn("json.py", result.files)
        self.assertNotIn("sitecustomize.py", result.files)
        self.assertIn('sys.path[:] = ["/gate"]', gate.BOOTSTRAP)
        self.assertNotIn('sys.path.insert(0, project)', gate.BOOTSTRAP)

    def test_symlink_file_and_directory_rejected(self):
        target = self.root / "outside.py"
        target.write_bytes(self.contents["renderer.py"])
        (self.bundle / "renderer.py").unlink()
        (self.bundle / "renderer.py").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.validate()
        (self.bundle / "renderer.py").unlink()
        (self.bundle / "renderer.py").write_bytes(self.contents["renderer.py"])
        link = self.repo / "external-directory"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.validate()

    def test_project_symlink_and_parent_traversal_are_rejected(self):
        link = self.root / "app-link"
        link.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            gate.validate_vendored_bundle(link)
        with self.assertRaisesRegex(ValueError, "traversal"):
            gate.validate_vendored_bundle(self.project / ".." / "example")

    def test_special_file_does_not_block_reader(self):
        os.mkfifo(self.repo / "unsafe-fifo")
        with self.assertRaisesRegex(ValueError, "Non-regular"):
            self.validate()

    def test_unsafe_names_in_self_declared_map_are_rejected(self):
        for name in ("../renderer.py", "/tmp/renderer.py", "package/renderer.py", "evil..py"):
            with self.subTest(name=name):
                self.metadata["sha256"][name] = "a" * 64
                self.write_metadata()
                with self.assertRaisesRegex(ValueError, "Unsafe canonical"):
                    self.validate()
                del self.metadata["sha256"][name]

    def test_duplicate_json_key_is_rejected(self):
        path = self.bundle / "TEMPLATE_SOURCE.json"
        path.write_text('{"commit":"good","commit":"bad"}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            self.validate()

    def test_external_git_object_stores_or_worktree_metadata_are_rejected(self):
        for name in ("commondir", "config.worktree", "objects/info/alternates", "objects/info/http-alternates"):
            with self.subTest(name=name):
                path = self.repo / ".git" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("/private-host-path")
                with self.assertRaisesRegex(ValueError, "External or worktree"):
                    self.validate()
                path.unlink()

    def test_sync_status_document_is_not_added_to_executable_bundle(self):
        (self.bundle / "SYNC_STATUS.md").write_text("App-owned informational document")
        result = self.validate()
        self.assertNotIn("SYNC_STATUS.md", result.files)
        self.assertNotIn("TEMPLATE_SOURCE.json", result.files)


class SandboxContract(BundleFixture):
    def mock_run(self, action="verify-site", site=None):
        captured = {}
        def run(command, **kwargs):
            captured["command"], captured["kwargs"] = command, kwargs
            mounts = self.mounts(command)
            verified = Path(mounts["/gate"][1])
            captured["files"] = {p.name: p.read_bytes() for p in verified.iterdir()}
            captured["bootstrap"] = Path(mounts["/bootstrap.py"][1]).read_text()
            captured["git_config"] = Path(mounts["/app/.git/config"][1]).read_text()
            return subprocess.CompletedProcess(command, 0, "passed", "")
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", side_effect=run):
            gate.run_verified_gate(self.project, action, site)
        return captured

    @staticmethod
    def mounts(command):
        return {command[i + 2]: (item, command[i + 1])
                for i, item in enumerate(command) if item in {"--bind", "--ro-bind"}}

    def test_namespace_env_and_python_startup_contract(self):
        result = self.mock_run()
        command, kwargs = result["command"], result["kwargs"]
        for required in ("--unshare-user", "--unshare-pid", "--unshare-net", "--unshare-ipc",
                         "--unshare-uts", "--unshare-cgroup", "--disable-userns", "--clearenv",
                         "--die-with-parent", "--new-session", "--cap-drop", "-I", "-S", "-B"):
            self.assertIn(required, command)
        self.assertEqual(command[-2:], ["verify-site", "/app/apps/example"])
        self.assertEqual(command[command.index("--chdir") + 1], "/app/apps/example")
        environment = {command[i + 1]: command[i + 2] for i, item in enumerate(command) if item == "--setenv"}
        self.assertEqual(environment, gate.CHILD_ENV)
        self.assertEqual(kwargs["env"], gate.LAUNCH_ENV)
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["cwd"], "/")
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("pass_fds", kwargs)

    def test_only_expected_read_only_mounts_and_no_engine_home_or_secrets(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "CANARY", "HOME": "/secret-home",
                                     "PYTHONPATH": "/injected", "LD_PRELOAD": "/evil.so"}):
            result = self.mock_run()
        mounts = self.mounts(result["command"])
        self.assertEqual(mounts["/app"], ("--ro-bind", str(self.repo)))
        self.assertEqual(set(mounts) - {"/usr", "/lib", "/lib64"},
                         {"/app", "/gate", "/bootstrap.py", "/app/.git/config"})
        self.assertTrue(all(flag == "--ro-bind" for flag, _ in mounts.values()))
        self.assertNotIn("--bind", result["command"])
        self.assertNotIn("CANARY", str(result))
        self.assertNotIn("/secret-home", str(result))
        self.assertEqual(result["files"], self.contents)
        self.assertNotIn("SECRET", result["git_config"])
        self.assertIn("fsmonitor = false", result["git_config"])
        self.assertNotIn(str(gate.ROOT), [source for _, source in mounts.values()])

    def test_stage_site_is_only_writable_host_mount_and_hides_website_git(self):
        site = self.root / "website"
        (site / ".git").mkdir(parents=True)
        (site / ".git/config").write_text("SECRET website token")
        result = self.mock_run("stage-site", site)
        mounts = self.mounts(result["command"])
        self.assertEqual(mounts["/site"], ("--bind", str(site)))
        self.assertEqual([dst for dst, (flag, _) in mounts.items() if flag == "--bind"], ["/site"])
        command = result["command"]
        hide = command.index("/site/.git")
        self.assertEqual(command[hide - 1:hide + 3], ["--tmpfs", "/site/.git", "--remount-ro", "/site/.git"])
        self.assertEqual(command[-2:], ["stage-site", "/app/apps/example"])

    def test_stage_site_worktree_git_file_is_hidden(self):
        site = self.root / "website"
        site.mkdir()
        (site / ".git").write_text("gitdir: /host-private-path")
        result = self.mock_run("stage-site", site)
        mounts = self.mounts(result["command"])
        self.assertEqual(mounts["/site/.git"][0], "--ro-bind")

    def test_existing_publisher_nested_dot_homepage_checkout_is_supported(self):
        engine = self.root / "engine"
        site = engine / ".homepage"
        (site / ".git").mkdir(parents=True)
        with patch.object(gate, "ROOT", engine):
            result = self.mock_run("stage-site", site)
        mounts = self.mounts(result["command"])
        self.assertEqual(mounts["/site"], ("--bind", str(site)))
        self.assertNotIn(str(engine), [source for _, source in mounts.values()])

    def test_verified_snapshot_cannot_reopen_changed_dependency(self):
        original_validate = gate.validate_vendored_bundle
        def validate_then_change(project):
            verified = original_validate(project)
            (self.bundle / "renderer.py").write_text("raise RuntimeError('replacement')")
            return verified
        with patch.object(gate, "validate_vendored_bundle", side_effect=validate_then_change):
            result = self.mock_run()
        self.assertEqual(result["files"]["renderer.py"], self.contents["renderer.py"])

    def test_gate_rejects_actions_and_invalid_site_combinations_before_subprocess(self):
        with patch.object(gate.subprocess, "run") as run:
            for action, site in (("refresh", None), ("inventory", None), ("verify", None),
                                 ("prepare", None), ("stage-site", None), ("verify-site", self.root)):
                with self.subTest(action=action, site=site), self.assertRaises(ValueError):
                    gate.run_verified_gate(self.project, action, site)
            run.assert_not_called()

    def test_site_overlap_with_app_engine_or_filesystem_root_is_rejected(self):
        for site in (self.repo, self.project, self.root, gate.ROOT, gate.ROOT / "data", Path("/")):
            with self.subTest(site=site), self.assertRaises(ValueError):
                gate.run_verified_gate(self.project, "stage-site", site)

    def test_missing_bwrap_never_runs_an_unisolated_command(self):
        with patch.object(gate, "BWRAP", self.root / "missing-bwrap"), patch.object(gate.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "no unisolated fallback"):
                gate.run_verified_gate(self.project, "verify-site")
            run.assert_not_called()

    def test_denied_bwrap_invoked_once_without_fallback(self):
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", return_value=
                subprocess.CompletedProcess(["bwrap"], 1, "", "user namespace denied")) as run:
            with self.assertRaisesRegex(ValueError, "exit 1.*no unisolated fallback"):
                gate.run_verified_gate(self.project, "verify-site")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], str(gate.BWRAP))

    def test_private_child_traceback_source_and_app_data_are_never_reported(self):
        private = 'Traceback: File "/gate/release_artwork.py"\n    PRIVATE_SOURCE_CANARY\nAPP_SECRET_CANARY'
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", return_value=
                subprocess.CompletedProcess(["bwrap"], 1, private, private)):
            with self.assertRaises(ValueError) as error:
                gate.run_verified_gate(self.project, "verify-site")
        self.assertNotIn("CANARY", str(error.exception))
        self.assertNotIn("release_artwork.py", str(error.exception))
        self.assertIn("sandbox_or_canonical_validation_failed", str(error.exception))

    def test_expected_evidence_failure_has_only_fixed_public_category(self):
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", return_value=
                subprocess.CompletedProcess(["bwrap"], 1, "", "ARTWORK RELEASE BLOCKED: Stale capture version/commit: PRIVATE_CANARY")):
            with self.assertRaisesRegex(ValueError, "capture_source_stale") as error:
                gate.run_verified_gate(self.project, "verify-site")
        self.assertNotIn("PRIVATE_CANARY", str(error.exception))

    def test_subprocess_failure_or_timeout_never_falls_back(self):
        for error in (OSError("denied"), subprocess.TimeoutExpired("bwrap", 300)):
            with self.subTest(error=type(error).__name__), patch.object(gate, "_runtime"), \
                    patch.object(gate.subprocess, "run", side_effect=error) as run:
                with self.assertRaisesRegex(ValueError, "no unisolated fallback"):
                    gate.run_verified_gate(self.project, "verify-site")
                self.assertEqual(run.call_count, 1)

    def test_corrupt_bundle_is_blocked_before_any_runtime_invocation(self):
        (self.bundle / "renderer.py").write_text("untrusted")
        with patch.object(gate.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "Noncanonical"):
            gate.run_verified_gate(self.project, "verify-site")
        run.assert_not_called()

    def test_bootstrap_syntax_and_subprocess_audit_are_engine_owned(self):
        ast.parse(gate.BOOTSTRAP)
        ast.parse(gate.SELF_TEST)
        self.assertIn('event == "subprocess.Popen"', gate.BOOTSTRAP)
        self.assertIn('argv not in allowed_git', gate.BOOTSTRAP)
        self.assertIn('"diff", "HEAD", "--name-only"', gate.BOOTSTRAP)
        self.assertIn('"log", "-1", "--format=%H"', gate.BOOTSTRAP)
        self.assertNotIn('"refresh"', gate.BOOTSTRAP)


class EngineAllowlistAndProbe(unittest.TestCase):
    def test_committed_ledger_has_all_27_canonical_files_and_exact_gate(self):
        data = gate.load_allowlist()
        self.assertEqual(len(data["sha256"]), 27)
        self.assertEqual(data["sha256"]["release_artwork.py"], gate.GATE_SHA256)
        self.assertEqual(set(data["source_commits"]), gate.SOURCE_COMMITS)
        self.assertIn("header_icon_template.svg", data["sha256"])
        self.assertIn("capture_iphone_duo.py", data["sha256"])
        self.assertIn("store_asset_workflow.py", data["sha256"])

    def test_runtime_probe_contains_no_app_code_or_canonical_bundle(self):
        captured = {}
        def run(command, **kwargs):
            captured["command"] = command
            mounts = SandboxContract.mounts(command)
            self.assertEqual(list(Path(mounts["/gate"][1]).iterdir()), [])
            bootstrap = Path(mounts["/bootstrap.py"][1]).read_text()
            self.assertEqual(bootstrap, gate.SELF_TEST)
            self.assertNotIn("runpy", bootstrap)
            self.assertNotIn("release_artwork", bootstrap)
            return subprocess.CompletedProcess(command, 0, "ARTWORK_SANDBOX_OK\n", "")
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", side_effect=run):
            result = gate.sandbox_preflight()
        self.assertEqual(result["status"], "verified")
        self.assertNotIn("--bind", captured["command"])

    def test_runtime_probe_requires_exact_success_marker(self):
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", return_value=
                subprocess.CompletedProcess(["bwrap"], 0, "", "")):
            with self.assertRaisesRegex(ValueError, "did not confirm"):
                gate.sandbox_preflight()

    def test_runtime_probe_rejects_denied_namespace(self):
        with patch.object(gate, "_runtime"), patch.object(gate.subprocess, "run", return_value=
                subprocess.CompletedProcess(["bwrap"], 1, "", "Operation not permitted")) as run:
            with self.assertRaisesRegex(ValueError, "exit 1.*no unisolated fallback"):
                gate.sandbox_preflight()
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
