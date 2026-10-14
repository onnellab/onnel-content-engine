"""Fixed diagnostic tests: every subprocess and every kernel read is mocked."""
import ast
import builtins
from contextlib import ExitStack
import errno
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_artwork_apparmor_profile as probe

ENABLED = "/sys/module/apparmor/parameters/enabled"
PROFILES = "/sys/kernel/security/apparmor/profiles"


def record(*, root=False, enabled_read="ok", profiles_read="ok", enabled=True, enforcing=True):
    return {"protocol": 1, "identity": "root" if root else "nonroot",
            "enabled_read": enabled_read, "profiles_read": profiles_read,
            "apparmor_enabled": enabled if enabled_read == "ok" else None,
            "docker_default_enforcing_unique": enforcing if profiles_read == "ok" else None}


def encoded(value):
    return (json.dumps(value) + "\n").encode()


class FakeKernel:
    """Only the two permitted target files exist; descriptors never reach OS."""
    def __init__(self, *, root=True):
        self.data = {ENABLED: b"Y\n", PROFILES: b"unrelated (complain)\ndocker-default (enforce)\n"}
        self.failures = {}
        self.modes = {}
        self.sizes = {}
        self.descriptors = {}
        self.positions = {}
        self.next_fd = 100
        self.opens = []
        self.reads = []
        self.root = root
        self.uid = 0 if root else 1001
        self.euid = self.uid
        self.argv = ["-c"]
        self.platform = "linux"
        self.env = dict(probe.SAFE_ENV)
        self.flags = SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1)
        self.stdout = io.StringIO()
        self.alarm = Mock()
        self.signal = Mock()
        self.imports = []

    def open(self, name, flags, *, dir_fd=None):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError("Write flags forbidden")
        assert flags & os.O_NOFOLLOW and flags & os.O_CLOEXEC
        path = name if dir_fd is None else self.descriptors[dir_fd].rstrip("/") + "/" + name
        self.opens.append((path, flags))
        if path in self.failures:
            raise OSError(self.failures[path], "private path and error must never be returned")
        if flags & os.O_DIRECTORY:
            assert any(target.startswith(path.rstrip("/") + "/") for target in self.data)
        else:
            assert path in self.data
            assert flags & os.O_NONBLOCK
        descriptor = self.next_fd
        self.next_fd += 1
        self.descriptors[descriptor] = path
        self.positions[descriptor] = 0
        return descriptor

    def close(self, descriptor):
        del self.descriptors[descriptor]
        del self.positions[descriptor]

    def fstat(self, descriptor):
        path = self.descriptors[descriptor]
        return SimpleNamespace(st_mode=self.modes.get(path, stat.S_IFREG | 0o444),
                               st_size=self.sizes.get(path, 0))

    def read(self, descriptor, size):
        path = self.descriptors[descriptor]
        assert path in (ENABLED, PROFILES)
        self.reads.append((path, size))
        position = self.positions[descriptor]
        self.positions[descriptor] += size
        return self.data[path][position:position + size]

    def execute(self):
        fake_os = SimpleNamespace(
            environ=self.env, getuid=lambda: self.uid, geteuid=lambda: self.euid,
            open=self.open, close=self.close, fstat=self.fstat, read=self.read,
            **{name: getattr(os, name) for name in (
                "O_RDONLY", "O_CLOEXEC", "O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")})
        modules = {"errno": errno, "json": json, "os": fake_os, "stat": stat,
                   "signal": SimpleNamespace(alarm=self.alarm, signal=self.signal, SIGALRM=14, SIG_DFL=0),
                   "sys": SimpleNamespace(platform=self.platform, argv=self.argv,
                                          flags=self.flags, stdout=self.stdout)}

        def import_mock(name, *args, **kwargs):
            self.imports.append(name)
            if name not in modules:
                raise AssertionError("Unexpected import")
            return modules[name]

        safe_builtins = dict(vars(builtins), __import__=import_mock,
                             open=Mock(side_effect=AssertionError("No built-in file reads")),
                             input=Mock(side_effect=AssertionError("No input")))
        source = probe.PUBLIC_PROGRAM if self.root else probe.UNPRIVILEGED_PROGRAM
        exec(compile(source, "<fixed-public-diagnostic>", "exec"), {"__builtins__": safe_builtins})
        self.signal.assert_called_once_with(14, 0)
        self.alarm.assert_called_once_with(5)
        assert not self.descriptors, "All owned file descriptors must be closed"
        return json.loads(self.stdout.getvalue())


class NoRealProcesses(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.popen = self.stack.enter_context(patch.object(
            probe.subprocess, "Popen", side_effect=AssertionError("Real subprocess prohibited")))
        self.stack.enter_context(patch.object(
            probe.subprocess, "run", side_effect=AssertionError("Real subprocess prohibited")))


class FixedProgramTests(NoRealProcesses):
    def test_only_fixed_reads_and_public_status_success(self):
        kernel = FakeKernel()
        result = kernel.execute()
        self.assertEqual(result, record(root=True))
        self.assertEqual(set(path for path, _ in kernel.reads), {ENABLED, PROFILES})
        self.assertEqual(kernel.imports, ["errno", "json", "os", "signal", "stat", "sys"])
        self.assertNotIn("unrelated", kernel.stdout.getvalue())
        self.assertNotIn("/sys", kernel.stdout.getvalue())
        self.popen.assert_not_called()

    def test_nonroot_constant_has_separate_identity_check(self):
        self.assertEqual(FakeKernel(root=False).execute(), record())

    def test_errno_enums_per_target_without_errors_or_paths(self):
        for target in (ENABLED, PROFILES):
            for number, label in ((errno.EACCES, "EACCES"), (errno.EPERM, "EPERM"),
                                  (errno.ENOENT, "ENOENT"), (errno.EIO, "other"),
                                  (errno.ELOOP, "other")):
                with self.subTest(target=target, errno=number):
                    kernel = FakeKernel()
                    kernel.failures[target] = number
                    result = kernel.execute()
                    key = "enabled_read" if target == ENABLED else "profiles_read"
                    self.assertEqual(result[key], label)
                    self.assertEqual(result["profiles_read" if target == ENABLED else "enabled_read"], "ok")
                    self.assertNotIn("private", kernel.stdout.getvalue())
                    self.assertNotIn(target, kernel.stdout.getvalue())

    def test_no_symlink_following_at_final_or_intermediate_components(self):
        for path in ("/sys", "/sys/module/apparmor", ENABLED, "/sys/kernel/security", PROFILES):
            with self.subTest(path=path):
                kernel = FakeKernel()
                kernel.failures[path] = errno.ELOOP
                result = kernel.execute()
                self.assertIn("other", (result["enabled_read"], result["profiles_read"]))
                self.assertFalse(any(opened.startswith(path + "/") for opened, _ in kernel.opens))

    def test_nonregular_targets_are_not_read(self):
        for mode in (stat.S_IFIFO, stat.S_IFDIR, stat.S_IFLNK):
            with self.subTest(mode=mode):
                kernel = FakeKernel()
                kernel.modes[PROFILES] = mode
                self.assertEqual(kernel.execute()["profiles_read"], "other")
                self.assertFalse(any(path == PROFILES for path, _ in kernel.reads))

    def test_virtual_file_nominal_stat_size_does_not_reject_tiny_content(self):
        kernel = FakeKernel()
        kernel.sizes[ENABLED] = 4096
        kernel.sizes[PROFILES] = 1024 * 1024 + 1
        self.assertEqual(kernel.execute(), record(root=True))

    def test_profile_read_is_bounded_before_decoding(self):
        kernel = FakeKernel()
        kernel.data[PROFILES] = b"docker-default (enforce)\n" + b"x" * (1024 * 1024)
        result = kernel.execute()
        self.assertEqual(result["profiles_read"], "other")
        self.assertIsNone(result["docker_default_enforcing_unique"])
        self.assertLessEqual(sum(size for path, size in kernel.reads if path == PROFILES), 1024 * 1024 + 1)

    def test_enabled_read_is_bounded(self):
        kernel = FakeKernel()
        kernel.data[ENABLED] = b"Y" * 1000
        self.assertEqual(kernel.execute()["enabled_read"], "other")
        self.assertEqual([size for path, size in kernel.reads if path == ENABLED], [17])

    def test_exact_unique_complete_enforcing_line_required(self):
        for data in (b"", b"other (enforce)\n", b"docker-default (complain)\n",
                     b"docker-default (unconfined)\n", b"docker-default (kill)\n",
                     b"docker-default-other (enforce)\n", b" docker-default (enforce)\n",
                     b"docker-default (enforce)\ndocker-default (enforce)\n",
                     b"docker-default (enforce)\ndocker-default (complain)\n"):
            with self.subTest(data=data):
                kernel = FakeKernel()
                kernel.data[PROFILES] = data
                result = kernel.execute()
                self.assertEqual(result["profiles_read"], "ok")
                self.assertIs(result["docker_default_enforcing_unique"], False)

    def test_malformed_or_non_utf8_profiles_are_inconclusive(self):
        for data in (b"docker-default (enforce)", b"docker-default (enforce)\r\n",
                     b"docker-default (enforce)\n\xff\n", b"\x00\n", b"\n",
                     b"docker-default\t(enforce)\n", b"docker-default (enforce) trailing\n",
                     b"docker-default (enforce)\nmalformed\n"):
            with self.subTest(data=data):
                kernel = FakeKernel()
                kernel.data[PROFILES] = data
                result = kernel.execute()
                self.assertEqual(result["profiles_read"], "other")
                self.assertIsNone(result["docker_default_enforcing_unique"])

    def test_enabled_exact_states_and_invalid_bytes(self):
        for data, expected in ((b"Y", True), (b"Y\n", True), (b"N", False), (b"N\n", False),
                               (b" Y\n", None), (b"Y\nN\n", None), (b"\xff", None), (b"", None)):
            with self.subTest(data=data):
                kernel = FakeKernel()
                kernel.data[ENABLED] = data
                result = kernel.execute()
                self.assertIs(result["apparmor_enabled"], expected)
                self.assertEqual(result["enabled_read"], "other" if expected is None else "ok")

    def test_identity_flags_environment_and_arguments_fail_before_reads(self):
        changes = ({"uid": 1001, "euid": 1001}, {"uid": 1001}, {"euid": 1001},
                   {"argv": ["-c", "/arbitrary"]}, {"platform": "darwin"},
                   {"env": dict(probe.SAFE_ENV, PYTHONPATH="/untrusted")},
                   {"flags": SimpleNamespace(isolated=0, no_site=1, dont_write_bytecode=1)},
                   {"flags": SimpleNamespace(isolated=1, no_site=0, dont_write_bytecode=1)},
                   {"flags": SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=0)})
        for change in changes:
            with self.subTest(change=change):
                kernel = FakeKernel()
                vars(kernel).update(change)
                self.assertEqual(kernel.execute()["identity"], "invalid")
                self.assertEqual(kernel.opens, [])
        kernel = FakeKernel(root=False)
        kernel.uid = kernel.euid = 0
        self.assertEqual(kernel.execute()["identity"], "invalid")
        self.assertEqual(kernel.opens, [])

    def test_unexpected_exception_is_sanitized_without_traceback(self):
        kernel = FakeKernel()
        kernel.read = Mock(side_effect=RuntimeError("private error"))
        result = kernel.execute()
        self.assertEqual(result["identity"], "invalid")
        self.assertNotIn("private", kernel.stdout.getvalue())

    def test_payload_has_no_external_input_or_subprocess_or_repository_imports(self):
        tree = ast.parse(probe.PUBLIC_PROGRAM)
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(imports, {"errno", "json", "os", "signal", "stat", "sys"})
        self.assertFalse(any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree)))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertTrue({"input", "eval", "exec", "__import__", "open"}.isdisjoint(names))
        self.assertEqual(probe.ELEVATED_COMMAND, (
            "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "LANG=C.UTF-8",
            "/usr/bin/python3", "-I", "-S", "-B", "-c", probe.PUBLIC_PROGRAM))


class FakeProcess:
    def __init__(self, output, *, code=0):
        self.output = bytearray(output)
        self.code = code
        self.returncode = None
        self.stdout = Mock()
        self.stdout.fileno.return_value = 51
        self.terminate = Mock(side_effect=self.stop)
        self.kill = Mock(side_effect=self.stop)
        self.wait = Mock(side_effect=self.finish)

    def stop(self):
        self.returncode = -15

    def finish(self, timeout):
        self.returncode = self.code if self.returncode is None else self.returncode
        return self.returncode

    def poll(self):
        return self.returncode

    def read(self, descriptor, size):
        assert descriptor == 51 and 0 < size <= 1024
        value = bytes(self.output[:size])
        del self.output[:size]
        return value


class InvocationTests(NoRealProcesses):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(probe.sys, "platform", "linux"))
        for name in ("getuid", "geteuid", "getgid", "getegid"):
            self.stack.enter_context(patch.object(probe.os, name, return_value=1001))
        self.selector = Mock()
        self.selector.__enter__ = Mock(return_value=self.selector)
        self.selector.__exit__ = Mock(return_value=False)
        self.selector.select.return_value = [(object(), 1)]
        self.stack.enter_context(patch.object(probe.selectors, "DefaultSelector", return_value=self.selector))
        self.read = self.stack.enter_context(patch.object(probe.os, "read"))
        self.children = []
        self.popen.side_effect = self.spawn

    def spawn(self, command, **kwargs):
        process = self.children.pop(0)
        self.read.side_effect = process.read
        return process

    def add(self, value, **kwargs):
        process = FakeProcess(value if isinstance(value, bytes) else encoded(value), **kwargs)
        self.children.append(process)
        return process

    def test_success_without_elevation_when_existing_files_are_readable(self):
        process = self.add(record())
        result = probe.run_probe()
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["elevation_attempted"])
        self.assertFalse(result["docker_continuation"])
        self.assertIsNone(result["elevated"])
        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.popen.call_args.args, (probe.UNPRIVILEGED_COMMAND,))
        process.stdout.close.assert_called_once()
        process.terminate.assert_not_called()

    def test_permission_denial_allows_only_exact_fixed_clean_elevated_call(self):
        self.add(record(profiles_read="EACCES"))
        self.add(record(root=True))
        with patch.dict(os.environ, {"PYTHONPATH": "/untrusted", "SUDO_ASKPASS": "/untrusted",
                                     "GITHUB_TOKEN": "private", "LD_PRELOAD": "/untrusted"}):
            result = probe.run_probe()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["elevation_attempted"])
        self.assertEqual(result["precheck"]["profiles_read"], "EACCES")
        self.assertEqual(result["elevated"]["profiles_read"], "ok")
        self.assertEqual([call.args[0] for call in self.popen.call_args_list],
                         [probe.UNPRIVILEGED_COMMAND, probe.ELEVATED_COMMAND])
        for call in self.popen.call_args_list:
            self.assertEqual(call.kwargs, {"env": probe.SAFE_ENV, "cwd": "/", "stdin": subprocess.DEVNULL,
                                          "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL,
                                          "bufsize": 0, "close_fds": True, "shell": False})

    def test_eperm_or_both_permission_denials_can_elevate(self):
        for initial in (record(enabled_read="EPERM"), record(profiles_read="EPERM"),
                        record(enabled_read="EPERM", profiles_read="EACCES")):
            with self.subTest(initial=initial):
                self.add(initial)
                self.add(record(root=True))
                self.assertEqual(probe.run_probe()["status"], "passed")

    def test_missing_other_disabled_or_non_enforcing_never_elevates(self):
        for initial in (record(enabled_read="ENOENT", profiles_read="EACCES"),
                        record(profiles_read="other", enabled_read="EPERM"),
                        record(enabled=False, profiles_read="EPERM"),
                        record(enforcing=False, enabled_read="EACCES"),
                        record(enabled=False), record(enforcing=False)):
            with self.subTest(initial=initial):
                before = self.popen.call_count
                self.add(initial)
                result = probe.run_probe()
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["elevation_attempted"])
                self.assertEqual(self.popen.call_count, before + 1)

    def test_unverifiable_elevated_reads_never_pass_or_continue(self):
        for elevated in (record(root=True, profiles_read="EPERM"), record(root=True, enabled_read="ENOENT"),
                         record(root=True, profiles_read="other"), record(root=True, enabled=False),
                         record(root=True, enforcing=False)):
            with self.subTest(elevated=elevated):
                self.add(record(profiles_read="EACCES"))
                self.add(elevated)
                result = probe.run_probe()
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["docker_continuation"])
                self.assertEqual(result["elevated"], elevated)

    def test_linux_and_nonroot_real_effective_identity_required(self):
        for name, value in (("platform", "darwin"), ("getuid", 0), ("geteuid", 0),
                            ("getgid", 0), ("getegid", 0), ("geteuid", 1002), ("getegid", 1002)):
            with self.subTest(name=name):
                target = probe.sys if name == "platform" else probe.os
                with patch.object(target, name, value if name == "platform" else Mock(return_value=value)):
                    self.assertEqual(probe.run_probe()["status"], "blocked")
        self.popen.assert_not_called()

    def test_nonzero_exit_and_spawn_errors_are_fixed_categories(self):
        self.add(b"private stderr is never captured", code=1)
        result = probe.run_probe()
        self.assertEqual(result["reason"], "probe_failed")
        self.assertNotIn("private", json.dumps(result))
        self.popen.side_effect = OSError("private spawn failure")
        self.assertEqual(probe.run_probe()["reason"], "probe_unavailable")

    def test_bounded_output_terminates_only_owned_process(self):
        process = self.add(b"x" * (probe.MAX_OUTPUT * 10))
        result = probe.run_probe()
        self.assertEqual(result["reason"], "probe_output_invalid")
        self.assertEqual(probe.MAX_OUTPUT * 10 - len(process.output), probe.MAX_OUTPUT + 1)
        process.terminate.assert_called_once()
        process.stdout.close.assert_called_once()

    def test_timeout_is_bounded_and_terminates_owned_process(self):
        process = self.add(b"")
        with patch.object(probe.time, "monotonic", side_effect=[0, probe.TIMEOUT + 1]):
            self.assertEqual(probe.run_probe()["reason"], "probe_timeout")
        process.terminate.assert_called_once()
        process.stdout.close.assert_called_once()

    def test_wait_timeout_is_sanitized_and_cleaned_up(self):
        process = self.add(record())
        process.wait.side_effect = [subprocess.TimeoutExpired("private", 1), 0]
        self.assertEqual(probe.run_probe()["reason"], "probe_timeout")
        process.terminate.assert_called_once()

    def test_cleanup_kill_fallback_is_bounded_and_verified(self):
        process = self.add(b"x" * (probe.MAX_OUTPUT + 1))
        process.terminate.side_effect = None
        process.wait.side_effect = [subprocess.TimeoutExpired("private", 2), 0]
        self.assertEqual(probe.run_probe()["reason"], "probe_output_invalid")
        process.kill.assert_called_once()
        self.assertEqual([call.kwargs for call in process.wait.call_args_list], [{"timeout": 2}, {"timeout": 2}])

    def test_unverified_cleanup_blocks(self):
        process = self.add(b"x" * (probe.MAX_OUTPUT + 1))
        process.terminate.side_effect = None
        process.kill.side_effect = None
        process.wait.side_effect = subprocess.TimeoutExpired("private", 2)
        self.assertEqual(probe.run_probe()["reason"], "probe_cleanup_unverified")

    def test_pipe_read_oserror_is_sanitized(self):
        process = self.add(record())
        process.read = Mock(side_effect=OSError("private pipe failure"))
        self.assertEqual(probe.run_probe()["reason"], "probe_io_unavailable")
        process.terminate.assert_called_once()

    def test_extra_cli_arguments_do_not_start_any_process(self):
        with patch.object(probe.sys, "argv", ["script", "--path=/private"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(probe.main(), 1)
        self.assertEqual(json.loads(out.getvalue())["reason"], "arguments_not_supported")
        self.popen.assert_not_called()

    def test_cli_passed_and_blocked_exit_codes(self):
        for initial, code in ((record(), 0), (record(enabled=False), 1)):
            self.add(initial)
            with patch.object(probe.sys, "argv", ["script"]), patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(probe.main(), code)
            self.assertFalse(json.loads(out.getvalue())["docker_continuation"])


class OutputParsingTests(NoRealProcesses):
    def test_strict_protocol_rejects_malformed_duplicate_extra_and_inconsistent_fields(self):
        good = record()
        malformed = [b"", b"\xff", b"[]", b"null", b"{}", encoded(good) + b"{}",
                     encoded(good).rstrip()[:-1] + b',"protocol":1}',
                     b"[" * 2000 + b"]" * 2000]
        for key, value in (("protocol", True), ("protocol", 1.0), ("identity", "root"),
                           ("identity", 0), ("enabled_read", []), ("enabled_read", "private"),
                           ("apparmor_enabled", 1), ("apparmor_enabled", None),
                           ("docker_default_enforcing_unique", "true"), ("extra", "/private"),
                           ("apparmor_enabled", float("nan"))):
            malformed.append(encoded(dict(good, **{key: value})))
        malformed += [encoded(dict(good, enabled_read="EACCES")), encoded(dict(good, profiles_read="other"))]
        for raw in malformed:
            with self.subTest(raw=raw[:100]):
                with self.assertRaisesRegex(probe.ProbeBlocked, "^probe_output_invalid$"):
                    probe._parse(raw, elevated=False)

    def test_elevated_identity_must_be_verified_root(self):
        with self.assertRaisesRegex(probe.ProbeBlocked, "^probe_output_invalid$"):
            probe._parse(encoded(record()), elevated=True)
        self.assertEqual(probe._parse(encoded(record(root=True)), elevated=True), record(root=True))


if __name__ == "__main__":
    unittest.main()
