"""Default-off adapter tests; all Docker and privileged operations are mocked."""
from contextlib import ExitStack
import copy
import inspect
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_artwork_docker_isolation as policy
import docker_artwork_runtime as runtime
import isolated_vendored_artwork as gate
from test_artwork_docker_isolation import FakeDocker, FACTS


class FakeGateDocker(FakeDocker):
    def make_record(self, args):
        super().make_record(args)
        self.record['Config']['WorkingDir'] = next(x.split('=', 1)[1] for x in args if x.startswith('--workdir='))
        self.created_sources = {m['Destination']: Path(m['Source']) for m in self.record['Mounts']}
        self.bootstrap_bytes = self.created_sources['/probe.py'].read_bytes()
        self.gate_bytes = {p.name: p.read_bytes() for p in self.created_sources['/gate'].iterdir()}

    def __call__(self, argv, **kwargs):
        if argv[5:7] == ['container', 'start']:
            self.calls.append((argv[5:], kwargs))
            if self.start_error:
                raise self.start_error
            self.started = True
            self.record['State'] = {'Running': False, 'ExitCode': 0, 'Status': 'exited'}
            return subprocess.CompletedProcess(argv, 0, 'private gate output', 'private stderr')
        return super().__call__(argv, **kwargs)


class DockerReadonlyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.repo = self.tmp / 'app'
        (self.repo / '.git').mkdir(parents=True)
        (self.repo / '.git/config').write_text('PRIVATE checkout credential')
        self.bundle = gate.ValidatedBundle(self.repo, PurePosixPath('.'), 'reviewed', {},
                                          {'release_artwork.py': b'# reviewed frozen gate\n'})
        self.validation = self.stack.enter_context(patch.object(gate, 'validate_vendored_bundle', return_value=self.bundle))
        self.fake = FakeGateDocker()
        self.stack.enter_context(patch.object(runtime, '_attach_gate', side_effect=lambda client, identity: client.call(['container', 'start', '--attach', identity], 'readonly_artwork_gate_failed', timeout=300)))
        self.stack.enter_context(patch.object(policy.subprocess, 'run', side_effect=self.fake))
        self.stack.enter_context(patch.object(policy.subprocess, 'Popen', side_effect=AssertionError('Real process forbidden')))
        self.stack.enter_context(patch.object(policy, '_host_facts', return_value=copy.deepcopy(FACTS)))
        self.profiles = self.stack.enter_context(patch.object(policy, '_profile_loaded'))
        self.stack.enter_context(patch.object(policy.shutil, 'disk_usage', return_value=SimpleNamespace(free=3 * 1024**3)))

    def calls(self, prefix):
        return [args for args, _ in self.fake.calls if args[:len(prefix)] == prefix]

    def test_default_backend_unchanged_and_cli_does_not_enable_docker(self):
        self.assertEqual(inspect.signature(gate.run_verified_gate).parameters['backend'].default, 'bubblewrap')
        self.assertNotIn('backend', inspect.getsource(gate.main))

    def test_explicit_readonly_gate_validates_and_copies_exact_bytes(self):
        gate.run_verified_gate(self.repo, 'verify-site', backend='docker-readonly')
        self.validation.assert_called_once_with(self.repo)
        self.assertEqual(self.fake.gate_bytes, self.bundle.files)
        self.assertEqual(self.fake.bootstrap_bytes, (runtime.BOUNDARY + gate.BOOTSTRAP).encode())
        self.assertEqual(set(self.fake.created_sources), {'/app', '/gate', '/probe.py', '/app/.git/config'})
        self.assertTrue(all(not m['RW'] for m in self.fake.record['Mounts']))
        self.assertEqual((self.repo / '.git/config').read_text(), 'PRIVATE checkout credential')
        self.assertFalse(self.fake.exists)
        self.assertEqual(len(self.calls(['container', 'start'])), 1)
        self.assertEqual(self.profiles.call_count, 2)  # host readiness is mocked above
        self.assertTrue(all(c.kwargs == {'inspect_profile_readonly': True} for c in self.profiles.call_args_list))

    def test_monorepo_subproject_has_exact_workdir_and_git_allowlist(self):
        self.bundle = gate.ValidatedBundle(self.repo, PurePosixPath('apps/example'), 'reviewed', {}, self.bundle.files)
        self.validation.return_value = self.bundle
        runtime.verify(self.repo / 'apps/example')
        self.assertEqual(self.fake.record['Config']['WorkingDir'], '/app/apps/example')
        self.assertEqual(self.fake.record['Config']['Cmd'][-2:], ['verify-site', '/app/apps/example'])
        command = self.fake.record['Config']['Cmd']
        self.assertIn('GIT_CONFIG_GLOBAL=/dev/null', command)
        self.assertIn('GIT_CONFIG_VALUE_0=/app', command)

    def test_stage_site_and_unknown_backend_block_before_any_runtime(self):
        for action, site, backend in [('stage-site', self.tmp, 'docker-readonly'), ('verify-site', None, 'unknown')]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                gate.run_verified_gate(self.repo, action, site, backend=backend)
        self.assertFalse(self.fake.calls)
        self.validation.assert_not_called()

    def test_noncanonical_input_stops_before_runtime(self):
        self.validation.side_effect = ValueError('not canonical')
        with self.assertRaisesRegex(ValueError, 'not canonical'):
            runtime.verify(self.repo)
        self.assertFalse(self.fake.calls)

    def test_csv_mount_path_rejected_before_runtime(self):
        self.validation.return_value = gate.ValidatedBundle(self.tmp / 'a,b', PurePosixPath('.'), '', {}, {})
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            runtime.verify(self.repo)
        self.assertFalse(self.fake.calls)

    def test_profile_failure_before_create_blocks_without_container(self):
        self.profiles.side_effect = policy.TrialBlocked('profile_unverified')
        with self.assertRaisesRegex(ValueError, 'profile_unverified'):
            runtime.verify(self.repo)
        self.assertFalse(self.calls(['container', 'create']))

    def test_profile_failure_before_start_cleans_owned_container(self):
        self.profiles.side_effect = [None, policy.TrialBlocked('profile_unverified')]
        with self.assertRaisesRegex(ValueError, 'profile_unverified'):
            runtime.verify(self.repo)
        self.assertFalse(self.calls(['container', 'start']))
        self.assertFalse(self.fake.exists)

    def test_container_policy_mismatch_never_starts_and_cleans(self):
        self.fake.inspect_change = lambda record: record['HostConfig'].update(NetworkMode='host')
        with self.assertRaisesRegex(ValueError, 'isolation_mismatch'):
            runtime.verify(self.repo)
        self.assertFalse(self.calls(['container', 'start']))
        self.assertFalse(self.fake.exists)

    def test_gate_failure_suppresses_private_output_and_cleans(self):
        self.fake.start_error = policy.TrialBlocked('readonly_artwork_gate_failed')
        with self.assertRaisesRegex(ValueError, '^Docker artwork verification blocked: readonly_artwork_gate_failed$'):
            runtime.verify(self.repo)
        self.assertFalse(self.fake.exists)

    def test_output_flood_failure_cleans_owned_container(self):
        self.fake.start_error = policy.TrialBlocked('readonly_artwork_gate_output_limit')
        with self.assertRaisesRegex(ValueError, 'output_limit'):
            runtime.verify(self.repo)
        self.assertFalse(self.fake.exists)

    def test_gate_timeout_cleans(self):
        self.fake.start_error = subprocess.TimeoutExpired(['private'], 300, output='private source')
        with self.assertRaisesRegex(ValueError, 'readonly_artwork_gate_failed_timeout'):
            runtime.verify(self.repo)
        self.assertFalse(self.fake.exists)

    def test_nonzero_exit_after_success_output_blocks(self):
        self.fake.exit_change = lambda record: record['State'].update(ExitCode=1)
        with self.assertRaisesRegex(ValueError, 'exit_unverified'):
            runtime.verify(self.repo)
        self.assertFalse(self.fake.exists)

    def test_cleanup_failure_blocks_success(self):
        self.fake.keep_after_remove = True
        with self.assertRaisesRegex(ValueError, 'cleanup_container_still_present'):
            runtime.verify(self.repo)

    def test_boundary_source_compiles_and_checks_runtime(self):
        compile(runtime.BOUNDARY + gate.BOOTSTRAP, '<public bootstrap>', 'exec')
        for required in ['CapBnd', 'Seccomp', 'NoNewPrivs', 'docker-default (enforce)', 'errno.EROFS', 'libc.unshare', 'expected["namespaces"]']:
            self.assertIn(required, runtime.BOUNDARY)
        self.assertIn('sys.addaudithook(audit)', gate.BOOTSTRAP)


class BoundedPrivateOutputTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.process = Mock()
        self.process.stdout.fileno.return_value = 7
        self.process.stderr.fileno.return_value = 8
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        self.popen = self.stack.enter_context(patch.object(runtime.subprocess, 'Popen', return_value=self.process))
        self.selector = Mock()
        manager = Mock()
        manager.__enter__ = Mock(return_value=self.selector)
        manager.__exit__ = Mock(return_value=False)
        self.stack.enter_context(patch.object(runtime.selectors, 'DefaultSelector', return_value=manager))
        self.read = self.stack.enter_context(patch.object(runtime.os, 'read'))
        self.stack.enter_context(patch.object(runtime.time, 'monotonic', return_value=10))
        self.client = SimpleNamespace(prefix=['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock', '--config', '/safe'], env={'PATH': '/usr/bin:/bin'})
        self.keys = [SimpleNamespace(fileobj=self.process.stdout), SimpleNamespace(fileobj=self.process.stderr)]

    def test_fixed_command_and_discarded_outputs(self):
        self.selector.select.return_value = [(key, 1) for key in self.keys]
        self.read.side_effect = [b'private stdout', b'private stderr', b'', b'']
        self.assertIsNone(runtime._attach_gate(self.client, 'a' * 64))
        args, kwargs = self.popen.call_args
        self.assertEqual(args[0], self.client.prefix + ['container', 'start', '--attach', 'a' * 64])
        self.assertEqual(kwargs['env'], self.client.env)
        self.assertFalse(kwargs['shell'])
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.process.stdout.close.assert_called_once()
        self.process.stderr.close.assert_called_once()

    def test_flood_stops_at_combined_cap_and_terminates_owned_client(self):
        self.selector.select.return_value = [(self.keys[0], 1)]
        self.read.side_effect = lambda fd, size: b'x' * size
        with self.assertRaisesRegex(policy.TrialBlocked, '^readonly_artwork_gate_output_limit$'):
            runtime._attach_gate(self.client, 'a' * 64)
        self.assertEqual(sum(c.args[1] for c in self.read.call_args_list), policy.MAX_OUTPUT + 1)
        self.process.terminate.assert_called_once()
        self.assertLessEqual(max(c.args[1] for c in self.read.call_args_list), 4096)

    def test_timeout_terminates_then_kills_only_owned_client(self):
        self.selector.select.return_value = []
        with patch.object(runtime.time, 'monotonic', side_effect=[0, 301]), self.assertRaisesRegex(policy.TrialBlocked, 'gate_timeout'):
            self.process.wait.side_effect = [subprocess.TimeoutExpired('owned', 2), 0]
            runtime._attach_gate(self.client, 'a' * 64)
        self.process.terminate.assert_called_once()
        self.process.kill.assert_called_once()

    def test_cleanup_failure_remains_blocked(self):
        self.selector.select.return_value = []
        with patch.object(runtime.time, 'monotonic', side_effect=[0, 301]), self.assertRaisesRegex(policy.TrialBlocked, 'client_cleanup_unverified'):
            self.process.wait.side_effect = subprocess.TimeoutExpired('owned', 2)
            runtime._attach_gate(self.client, 'a' * 64)

    def test_read_error_is_sanitized(self):
        self.selector.select.return_value = [(self.keys[0], 1)]
        self.read.side_effect = OSError('private source')
        with self.assertRaisesRegex(policy.TrialBlocked, '^readonly_artwork_gate_io_unavailable$'):
            runtime._attach_gate(self.client, 'a' * 64)
        self.process.terminate.assert_called_once()

if __name__ == '__main__': unittest.main()
