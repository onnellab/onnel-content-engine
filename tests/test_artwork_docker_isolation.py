"""Synthetic trial tests. Every Docker invocation is mocked, on every OS."""
import copy
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_artwork_docker_isolation as trial

FACTS = {"uid": 1001, "gid": 1001,
         "namespaces": {name: name + ":[parent-test]" for name in trial.NAMESPACES}}


class FakeDocker:
    """Emulate inspect metadata and lifecycle; never delegate to subprocess."""
    def __init__(self):
        self.calls = []
        self.exists = False
        self.identity = "a" * 64
        self.record = None
        self.inspect_change = None
        self.start_error = None
        self.create_error = None
        self.start_stdout = trial.MARKER
        self.start_stderr = ""
        self.keep_after_remove = False
        self.rename_after_remove = False
        self.remove_error = False
        self.list_error = False
        self.cleanup_change = None
        self.exit_change = None
        self.change_host_git_canary = False
        self.started = False
        self.inspect_count = 0
        self.image = [{"Id": trial.APPROVED_IMAGE_ID, "Architecture": "amd64", "Os": "linux",
                       "RepoDigests": [trial.APPROVED_IMAGE.replace("docker.io/library/", "")],
                       "Config": {"Env": list(trial.APPROVED_IMAGE_ENV), "Cmd": ["python3"]}}]
        self.version = {part: {"Version": "28.0.4", "Os": "linux", "Arch": "amd64"}
                        for part in ("Client", "Server")}
        self.info = {"OSType": "linux", "Architecture": "x86_64", "DefaultStorage": True,
                     "SecurityOptions": ["name=apparmor", "name=seccomp,profile=builtin", "name=cgroupns"]}

    def __call__(self, argv, **kwargs):
        assert argv[:4] == [trial.DOCKER, "--host", "unix://" + trial.SOCKET, "--config"]
        config = Path(argv[4])
        assert json.loads((config / "config.json").read_text()) == {}
        assert (config / "config.json").stat().st_mode & 0o777 == 0o600
        assert kwargs["env"] == dict(trial.SAFE_ENV, HOME=str(config))
        assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["cwd"] == "/"
        self.calls.append((argv[5:], kwargs))
        args = argv[5:]

        def result(stdout="", code=0, stderr=""):
            return subprocess.CompletedProcess(argv, code, stdout, stderr)

        if args[0] == "version":
            assert args == ["version", "--format", trial.VERSION_FORMAT]
            return result(json.dumps(self.version))
        if args[0] == "info":
            assert args == ["info", "--format", trial.INFO_FORMAT]
            return result(json.dumps(self.info))
        if args[:2] == ["image", "pull"]:
            return result("public pull output\n")
        if args[:2] == ["image", "inspect"]:
            return result(json.dumps(self.image))
        if args == ["container", "ls", "--no-trunc", "--format", "{{.ID}}"]:
            return result("c" * 64 + "\n")  # A shared workload must remain untouched.
        if args[:2] == ["container", "create"]:
            self.make_record(args)
            self.exists = True
            if self.create_error:
                raise self.create_error
            return result(self.identity + "\n")
        if args[:2] == ["container", "inspect"]:
            if not self.exists:
                return result(code=1, stderr="private diagnostic must not leak")
            self.inspect_count += 1
            record = copy.deepcopy(self.record)
            if self.inspect_count == 1 and self.inspect_change:
                self.inspect_change(record)
            elif self.started and self.inspect_count == 2 and self.exit_change:
                self.exit_change(record)
            elif self.inspect_count > (2 if self.started else 1) and self.cleanup_change:
                self.cleanup_change(record)
            return result(json.dumps([record]))
        if args[:2] == ["container", "start"]:
            if self.start_error:
                raise self.start_error
            self.started = True
            self.record["State"] = {"Running": False, "ExitCode": 0, "Status": "exited"}
            (self.root / "site/result").write_text("public synthetic output\n")
            if self.change_host_git_canary:
                (self.root / "site/.git/config").write_text("changed")
            return result(self.start_stdout, stderr=self.start_stderr)
        if args[:2] == ["container", "rm"]:
            assert args == ["container", "rm", "--force", self.identity]
            if not self.keep_after_remove:
                self.exists = False
            return result(code=int(self.remove_error))
        if args[:2] == ["container", "ls"]:
            assert args[:5] == ["container", "ls", "--all", "--no-trunc", "--filter"]
            assert args[5] in ("name=^/" + self.name + "$", "id=" + self.identity)
            assert args[6:] == ["--format", "{{.ID}}"]
            present = self.exists and (not self.rename_after_remove or args[5].startswith("id="))
            return result(self.identity + "\n" if present else "", code=int(self.list_error))
        raise AssertionError("Unexpected subprocess invocation")

    def make_record(self, args):
        self.name = args[args.index("--name") + 1]
        self.token = args[args.index("--label") + 1].split("=", 1)[1]
        mounts, configured = [], []
        for index, arg in enumerate(args):
            if arg != "--mount":
                continue
            fields = dict(piece.split("=", 1) if "=" in piece else (piece, True)
                          for piece in args[index + 1].split(","))
            readonly = fields.get("readonly") is True
            mounts.append({"Type": "bind", "Source": fields["src"], "Destination": fields["dst"],
                           "RW": not readonly, "Propagation": "rprivate"})
            options = {"Propagation": "rprivate"}
            options["ReadOnlyForceRecursive" if readonly else "NonRecursive"] = True
            configured.append({"Type": "bind", "Source": fields["src"], "Target": fields["dst"],
                               "ReadOnly": readonly, "BindOptions": options})
        self.root = Path(mounts[0]["Source"]).parent
        self.record = {
            "Id": self.identity, "Name": "/" + self.name, "Image": trial.APPROVED_IMAGE_ID,
            "State": {"Running": False}, "Mounts": mounts,
            "Config": {"Labels": {trial.LABEL: self.token}, "User": "1001:1001", "WorkingDir": "/app",
                       "Env": list(trial.APPROVED_IMAGE_ENV),
                       "Entrypoint": ["/usr/bin/env"], "Cmd": args[args.index(trial.APPROVED_IMAGE) + 1:],
                       "Healthcheck": {"Test": ["NONE"]}},
            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                           "CapDrop": ["ALL"], "IpcMode": "private", "CgroupnsMode": "private",
                           "PidMode": "", "UTSMode": "", "UsernsMode": "", "PidsLimit": 64,
                           "Memory": 256 * 1024 * 1024, "NanoCpus": 1000000000,
                           "SecurityOpt": ["no-new-privileges=true", "apparmor=docker-default"],
                           "LogConfig": {"Type": "none"}, "Mounts": configured,
                           "Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777",
                                     "/run": "rw,nosuid,nodev,noexec,size=1m,mode=755"}}}


class TrialFixture(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDocker()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.command = self.stack.enter_context(patch.object(trial.subprocess, "run", side_effect=self.fake))
        self.host = self.stack.enter_context(patch.object(trial, "_host_facts", return_value=copy.deepcopy(FACTS)))
        self.profile = self.stack.enter_context(patch.object(trial, "_profile_loaded"))
        self.disk = self.stack.enter_context(patch.object(trial.shutil, "disk_usage", return_value=SimpleNamespace(free=3 * 1024 ** 3)))

    def commands(self, prefix):
        return [args for args, _ in self.fake.calls if args[:len(prefix)] == prefix]

    def blocked(self, category):
        with self.assertRaisesRegex(trial.TrialBlocked, "^" + category + "$"):
            trial.run_trial()


class SuccessfulTrial(TrialFixture):
    def test_public_only_success_and_cleanup_verified(self):
        report = trial.run_trial()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["scope"], "public_synthetic_only")
        self.assertEqual(report["cleanup"], "verified")
        self.assertEqual(report["existing_running_containers"], 1)
        self.assertFalse(report["production_backend_changed"])
        self.assertEqual(len(self.commands(["container", "start"])), 1)
        self.assertEqual(len(self.commands(["image", "pull"])), 1)
        self.assertFalse(self.fake.exists)
        self.assertFalse(self.fake.root.exists())
        self.assertEqual(self.profile.call_count, 2)

    def test_all_commands_use_clean_environment_and_empty_config(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "ssh://untrusted", "DOCKER_CONFIG": "/secrets",
                                     "HTTP_PROXY": "secret", "GITHUB_TOKEN": "secret", "TMPDIR": "/untrusted"}):
            trial.run_trial()
        for _, kwargs in self.fake.calls:
            self.assertEqual(set(kwargs["env"]), {"PATH", "LANG", "LC_ALL", "HOME"})
            self.assertNotIn("secret", json.dumps(kwargs["env"]))

    def test_exact_safe_create_flags_and_mounts(self):
        trial.run_trial()
        args = self.commands(["container", "create"])[0]
        for flag in ("--pull=never", "--network=none", "--read-only", "--cap-drop=ALL",
                     "--security-opt=no-new-privileges=true", "--security-opt=apparmor=docker-default",
                     "--ipc=private", "--cgroupns=private", "--no-healthcheck", "--log-driver=none"):
            self.assertIn(flag, args)
        for forbidden in ("--privileged", "--network=host", "--pid=host", "--userns=host", "--env-file"):
            self.assertNotIn(forbidden, args)
        self.assertFalse(any("unconfined" in arg for arg in args))
        self.assertEqual(args[args.index("--entrypoint=/usr/bin/env")], "--entrypoint=/usr/bin/env")
        self.assertEqual(args[args.index(trial.APPROVED_IMAGE) + 1], "-i")
        mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
        self.assertEqual(len(mounts), 6)
        self.assertEqual(sum("readonly,bind-recursive=readonly" in mount for mount in mounts), 5)
        self.assertFalse(any("docker.sock" in mount or "/client" in mount for mount in mounts))

    def test_readiness_precedes_pull_and_inspection_precedes_start(self):
        trial.run_trial()
        commands = [args[:2] for args, _ in self.fake.calls]
        self.assertEqual(commands[:2], [["version", "--format"], ["info", "--format"]])
        self.assertLess(commands.index(["image", "inspect"]), commands.index(["container", "create"]))
        self.assertLess(commands.index(["container", "inspect"]), commands.index(["container", "start"]))

    def test_host_metadata_templates_collect_only_reviewed_fields(self):
        self.assertNotIn("{{json .}}", trial.VERSION_FORMAT + trial.INFO_FORMAT)
        for forbidden in (".Labels", ".Name", ".DriverStatus", ".RegistryConfig", ".Plugins"):
            self.assertNotIn(forbidden, trial.INFO_FORMAT)
        self.assertIn('"DefaultStorage":{{eq .DockerRootDir "/var/lib/docker"}}', trial.INFO_FORMAT)
        self.assertNotIn("{{json .DockerRootDir}}", trial.INFO_FORMAT)

    def test_official_normalized_repo_digest_is_accepted(self):
        for repository in ("python", "library/python", "docker.io/library/python"):
            with self.subTest(repository=repository):
                image = copy.deepcopy(self.fake.image)
                image[0]["RepoDigests"] = [repository + "@" + trial.APPROVED_IMAGE.split("@", 1)[1]]
                self.assertEqual(trial._validate_image(image), trial.APPROVED_IMAGE_ID)


class ReadinessRejection(TrialFixture):
    def test_host_rejection_runs_no_command(self):
        self.host.side_effect = trial.TrialBlocked("existing_enforcing_docker_profile_required")
        self.blocked("existing_enforcing_docker_profile_required")
        self.command.assert_not_called()

    def test_unreviewed_client_or_server_version_blocks_before_pull(self):
        for part in ("Client", "Server"):
            with self.subTest(part=part):
                original = self.fake.version[part]["Version"]
                self.fake.version[part]["Version"] = "99.0.0"
                self.blocked("docker_version_not_reviewed")
                self.fake.version[part]["Version"] = original
        self.assertFalse(self.commands(["image", "pull"]))

    def test_unreviewed_platform_blocks_before_pull(self):
        self.fake.version["Server"]["Arch"] = "arm64"
        self.blocked("docker_platform_not_reviewed")
        self.assertFalse(self.commands(["image", "pull"]))

    def test_missing_seccomp_or_apparmor_or_cgroup_blocks(self):
        for missing in list(self.fake.info["SecurityOptions"]):
            with self.subTest(missing=missing):
                original = self.fake.info["SecurityOptions"]
                self.fake.info["SecurityOptions"] = [value for value in original if value != missing]
                self.blocked("existing_default_confinement_required")
                self.fake.info["SecurityOptions"] = original
        self.assertFalse(self.commands(["image", "pull"]))

    def test_rootless_and_remapped_daemons_are_not_implicitly_adopted(self):
        for option in ("name=rootless", "name=userns"):
            with self.subTest(option=option):
                self.fake.info["SecurityOptions"].append(option)
                self.blocked("docker_namespace_configuration_not_reviewed")
                self.fake.info["SecurityOptions"].pop()

    def test_profile_disappearance_prevents_create(self):
        self.profile.side_effect = trial.TrialBlocked("existing_enforcing_docker_profile_required")
        self.blocked("existing_enforcing_docker_profile_required")
        self.assertFalse(self.commands(["container", "create"]))

    def test_profile_disappearance_before_start_cleans_created_container(self):
        self.profile.side_effect = [None, trial.TrialBlocked("existing_enforcing_docker_profile_required")]
        self.blocked("existing_enforcing_docker_profile_required")
        self.assertFalse(self.commands(["container", "start"]))
        self.assertFalse(self.fake.exists)

    def test_missing_or_floating_image_pin_blocks_before_readiness(self):
        for value in ("", "python:latest", "example.invalid/python@sha256:" + "b" * 64):
            with self.subTest(value=value), patch.object(trial, "APPROVED_IMAGE", value):
                self.blocked("reviewed_official_image_digest_required")
        self.host.assert_not_called()

    def test_insufficient_space_blocks_before_pull(self):
        self.disk.return_value = SimpleNamespace(free=1000)
        self.blocked("insufficient_trial_disk_space")
        self.assertFalse(self.commands(["image", "pull"]))


class ImageRejection(TrialFixture):
    def test_automatic_image_behavior_is_rejected_before_create(self):
        for field, value in (("Volumes", {"/data": {}}), ("Healthcheck", {"Test": ["CMD", "secret"]}),
                             ("Entrypoint", ["/unexpected"]), ("OnBuild", ["RUN anything"])):
            with self.subTest(field=field):
                self.fake.image[0]["Config"][field] = value
                self.blocked("image_automatic_behavior_forbidden")
                del self.fake.image[0]["Config"][field]
        self.assertFalse(self.commands(["container", "create"]))

    def test_wrong_architecture_is_rejected(self):
        self.fake.image[0]["Architecture"] = "arm64"
        self.blocked("image_platform_not_reviewed")

    def test_wrong_repository_or_manifest_is_rejected(self):
        self.fake.image[0]["RepoDigests"] = ["attacker/python@" + trial.APPROVED_IMAGE.split("@", 1)[1]]
        self.blocked("image_digest_mismatch")

    def test_same_manifest_claim_with_wrong_config_id_is_rejected(self):
        self.fake.image[0]["Id"] = "sha256:" + "b" * 64
        self.blocked("image_identity_invalid")

    def test_unreviewed_loader_environment_is_rejected(self):
        self.fake.image[0]["Config"]["Env"].append("LD_PRELOAD=/untrusted")
        self.blocked("image_configuration_not_reviewed")


class ContainerPolicyRejection(TrialFixture):
    def test_isolation_mismatches_never_start(self):
        changes = {"NetworkMode": "host", "ReadonlyRootfs": False, "Privileged": True,
                   "CapDrop": [], "IpcMode": "host", "PidMode": "host", "UTSMode": "host",
                   "CgroupnsMode": "host", "UsernsMode": "host", "PidsLimit": 0, "Memory": 0, "NanoCpus": 0}
        for key, value in changes.items():
            with self.subTest(key=key):
                self.fake.inspect_count = 0
                self.fake.inspect_change = lambda record, k=key, v=value: record["HostConfig"].__setitem__(k, v)
                self.blocked("container_isolation_mismatch")
                self.assertFalse(self.fake.exists)
        self.assertFalse(self.commands(["container", "start"]))

    def test_privilege_and_external_access_additions_never_start(self):
        for key in ("CapAdd", "Devices", "DeviceRequests", "GroupAdd", "VolumesFrom", "Binds", "Links", "ExtraHosts", "PortBindings"):
            with self.subTest(key=key):
                self.fake.inspect_count = 0
                self.fake.inspect_change = lambda record, k=key: record["HostConfig"].__setitem__(k, ["unexpected"])
                self.blocked("container_extra_access_forbidden")
        self.assertFalse(self.commands(["container", "start"]))

    def test_unconfined_or_custom_seccomp_policy_rejected(self):
        self.fake.inspect_change = lambda record: record["HostConfig"]["SecurityOpt"].append("seccomp=unconfined")
        self.blocked("container_confinement_mismatch")

    def test_missing_recursive_readonly_rejected(self):
        self.fake.inspect_change = lambda record: record["HostConfig"]["Mounts"][0]["BindOptions"].pop("ReadOnlyForceRecursive")
        self.blocked("container_recursive_mounts_mismatch")

    def test_writable_app_bind_rejected(self):
        self.fake.inspect_change = lambda record: record["Mounts"][0].__setitem__("RW", True)
        self.blocked("container_mounts_mismatch")

    def test_socket_or_extra_volume_rejected(self):
        self.fake.inspect_change = lambda record: record["Mounts"].append({"Type": "volume", "Destination": "/secret"})
        self.blocked("container_mounts_mismatch")

    def test_unexpected_entrypoint_or_environment_command_rejected(self):
        self.fake.inspect_change = lambda record: record["Config"]["Cmd"].__setitem__(0, "--ignore-signal")
        self.blocked("container_command_mismatch")

    def test_logging_to_host_rejected(self):
        self.fake.inspect_change = lambda record: record["HostConfig"]["LogConfig"].__setitem__("Type", "json-file")
        self.blocked("container_log_storage_forbidden")

    def test_initial_proxy_loader_and_duplicate_environment_rejected(self):
        for variable in ("HTTP_PROXY=secret", "LD_PRELOAD=/unexpected", "PYTHONPATH=/app", "LANG=C"):
            with self.subTest(variable=variable):
                self.fake.inspect_count = 0
                self.fake.inspect_change = lambda record, value=variable: record["Config"]["Env"].append(value)
                self.blocked("container_initial_environment_mismatch")
        self.assertFalse(self.commands(["container", "start"]))

    def test_missing_git_mask_rejected(self):
        self.fake.inspect_change = lambda record: record["Mounts"].pop()
        self.blocked("container_mounts_mismatch")

    def test_site_git_mask_must_be_readonly(self):
        self.fake.inspect_change = lambda record: record["Mounts"][-1].__setitem__("RW", True)
        self.blocked("container_mounts_mismatch")


class CleanupAndReporting(TrialFixture):
    def test_host_git_canary_mutation_is_detected(self):
        self.fake.change_host_git_canary = True
        self.blocked("synthetic_host_git_canary_changed")
        self.assertFalse(self.fake.exists)

    def test_probe_must_be_exited_successfully_after_success_marker(self):
        self.fake.exit_change = lambda record: record["State"].__setitem__("ExitCode", 1)
        self.blocked("probe_exit_unverified")
        self.assertFalse(self.fake.exists)

    def test_start_timeout_removes_exact_owned_id_and_verifies(self):
        self.fake.start_error = subprocess.TimeoutExpired("private command", 45, stderr="private secret")
        self.blocked("synthetic_probe_failed_timeout")
        self.assertEqual(self.commands(["container", "rm"]), [["container", "rm", "--force", self.fake.identity]])
        self.assertFalse(self.fake.exists)

    def test_ambiguous_create_timeout_cleans_labelled_container(self):
        self.fake.create_error = subprocess.TimeoutExpired("create", 20)
        self.blocked("container_create_failed_timeout")
        self.assertFalse(self.fake.exists)
        self.assertFalse(self.commands(["container", "start"]))

    def test_keyboard_interrupt_cleans_owned_container(self):
        self.fake.start_error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            trial.run_trial()
        self.assertFalse(self.fake.exists)

    def test_cleanup_cannot_delete_different_id_even_with_same_label(self):
        self.fake.cleanup_change = lambda record: record.__setitem__("Id", "b" * 64)
        self.blocked("cleanup_ownership_unverified")
        self.assertFalse(self.commands(["container", "rm"]))

    def test_cleanup_cannot_delete_unrelated_label(self):
        self.fake.cleanup_change = lambda record: record["Config"]["Labels"].__setitem__(trial.LABEL, "other-task")
        self.blocked("cleanup_ownership_unverified")
        self.assertFalse(self.commands(["container", "rm"]))

    def test_remaining_container_is_a_failure(self):
        self.fake.keep_after_remove = True
        self.blocked("cleanup_container_still_present")

    def test_renamed_container_cannot_evade_id_absence_verification(self):
        self.fake.keep_after_remove = True
        self.fake.rename_after_remove = True
        self.fake.remove_error = True
        self.blocked("cleanup_container_still_present")

    def test_unknown_cleanup_state_is_a_failure(self):
        self.fake.list_error = True
        self.blocked("cleanup_verification_failed")

    def test_removal_nonzero_is_accepted_only_if_absence_verified(self):
        self.fake.remove_error = True
        self.assertEqual(trial.run_trial()["cleanup"], "verified")

    def test_probe_private_output_is_never_reported(self):
        self.fake.start_stderr = "Traceback: private/source.py SECRET_CANARY"
        stream = io.StringIO()
        with patch("sys.stdout", stream):
            self.assertEqual(trial.main(), 1)
        self.assertEqual(json.loads(stream.getvalue())["category"], "synthetic_probe_output_invalid")
        self.assertNotIn("SECRET_CANARY", stream.getvalue())
        self.assertNotIn("private/source", stream.getvalue())

    def test_unexpected_exception_details_are_sanitized(self):
        with patch.object(trial, "run_trial", side_effect=ValueError("private SECRET")), patch("sys.stdout", new_callable=io.StringIO) as stream:
            self.assertEqual(trial.main(), 1)
        self.assertNotIn("SECRET", stream.getvalue())
        self.assertEqual(json.loads(stream.getvalue())["category"], "trial_interrupted_or_internal_error")


class HostPolicyTests(unittest.TestCase):
    def test_nonlinux_remains_unsupported(self):
        with patch.object(trial.sys, "platform", "darwin"), patch.object(trial.subprocess, "run") as command:
            with self.assertRaisesRegex(trial.TrialBlocked, "linux_required"):
                trial._host_facts()
            command.assert_not_called()

    def test_root_runner_is_rejected(self):
        with patch.object(trial.sys, "platform", "linux"), patch.object(trial.os, "getuid", return_value=0):
            with self.assertRaisesRegex(trial.TrialBlocked, "nonroot_runner_required"):
                trial._host_facts()

    def test_profile_must_be_loaded_enforcing_and_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary).resolve() / "profiles"
            for content in ("", "docker-default (complain)\n", "other (enforce)\n", "docker-default-extra (enforce)\n"):
                with self.subTest(content=content):
                    profile.write_text(content)
                    with patch.object(trial, "PROFILE_FILE", profile), patch.object(Path, "read_text", return_value="Y\n"):
                        with self.assertRaisesRegex(trial.TrialBlocked, "existing_enforcing_docker_profile_required"):
                            trial._profile_loaded()
            profile.write_text("other (enforce)\ndocker-default (enforce)\n")
            with patch.object(trial, "PROFILE_FILE", profile), patch.object(Path, "read_text", return_value="Y\n"):
                trial._profile_loaded()

    def test_unreadable_policy_fails_closed(self):
        with patch.object(Path, "open", side_effect=PermissionError("secret path")):
            with self.assertRaisesRegex(trial.TrialBlocked, "existing_apparmor_policy_unreadable"):
                trial._profile_loaded()

    def test_public_probe_compiles_without_running(self):
        compile(trial.PROBE, "public-synthetic-probe", "exec")
        self.assertNotIn("release_artwork", trial.PROBE)
        self.assertIn("libc.unshare", trial.PROBE)
        self.assertIn("dict(os.environ) == expected_env", trial.PROBE)
        self.assertIn("os.getgroups() == [gid]", trial.PROBE)


if __name__ == "__main__":
    unittest.main()
