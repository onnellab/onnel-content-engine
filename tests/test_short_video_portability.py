"""Real, lightweight subprocess checks; no media, emulator, Flutter, or network."""
from __future__ import annotations

import json
import errno
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from short_video_pipeline import Queue, VideoError, atomic_json, run_process
from short_video_portability import OutputLines, exclusive_file_lock, spawn_owned, stop_owned
from short_video_recorder import RecordingError, _run, _run_and_capture, android_device, ios_device, recording_lock


def pid_alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT
        finally:
            kernel.CloseHandle(handle)
    try:
        status = Path(f'/proc/{pid}/stat')
        if status.exists() and status.read_text().split(') ', 1)[1].startswith('Z '):
            return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class ShortVideoPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_queue_and_recording_locks_exclude_another_process_then_release(self):
        for kind in ('queue', 'recording'):
            with self.subTest(lock=kind):
                root = self.root / kind
                lock = Queue(root, self.root).lock if kind == 'queue' else lambda: recording_lock(root)
                code = (
                    'import sys; from pathlib import Path; '
                    f'sys.path.insert(0, {str(SCRIPTS)!r}); '
                    'from short_video_pipeline import Queue, VideoError; '
                    'from short_video_recorder import recording_lock; '
                    f'root=Path({str(root)!r}); '
                    f'lock=Queue(root, root).lock() if {kind!r} == "queue" else recording_lock(root)\n'
                    'try:\n'
                    ' with lock: print("acquired")\n'
                    'except VideoError:\n'
                    ' print("busy"); sys.exit(7)\n'
                )
                with lock():
                    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=10)
                    self.assertEqual(7, result.returncode, result.stdout + result.stderr)
                    self.assertEqual('busy', result.stdout.strip())
                result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=10)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual('acquired', result.stdout.strip())

    def test_atomic_state_replacement_works_without_directory_open_on_windows(self):
        path = self.root / 'queue.json'
        atomic_json(path, {'version': 1})
        atomic_json(path, {'version': 2})
        self.assertEqual({'version': 2}, json.loads(path.read_text()))
        self.assertEqual([], list(self.root.glob('.write-*')))

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group cleanup')
    def test_darwin_eperm_requires_owned_reaped_child_and_no_live_group_members(self):
        for members in ('', '4322 4321 Z\n'):
            with self.subTest(members=members):
                proc = Mock(pid=4321, _short_video_pgid=4321, _short_video_stopped=False)
                proc.poll.return_value = 0
                status = subprocess.CompletedProcess([], 0, stdout=members, stderr='')
                with patch('short_video_portability.sys.platform', 'darwin'), \
                        patch('short_video_portability.os.killpg', side_effect=PermissionError(errno.EPERM, 'finished')) as kill, \
                        patch('short_video_portability.subprocess.run', return_value=status) as inspect:
                    stop_owned(proc)
                    stop_owned(proc)
                self.assertTrue(proc._short_video_stopped)
                kill.assert_called_once_with(4321, signal.SIGTERM)
                self.assertEqual(['/bin/ps', '-x', '-o', 'pid=,pgid=,stat=', '-g', '4321'], inspect.call_args.args[0])

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group cleanup')
    def test_darwin_eperm_after_term_does_not_fail_successful_cleanup(self):
        proc = Mock(pid=4321, _short_video_pgid=4321, _short_video_stopped=False)
        proc.poll.return_value = 0
        status = subprocess.CompletedProcess([], 0, stdout='4322 4321 Z\n', stderr='')
        with patch('short_video_portability.sys.platform', 'darwin'), \
                patch('short_video_portability.os.killpg', side_effect=[None, PermissionError(errno.EPERM, 'finished')]) as kill, \
                patch('short_video_portability.subprocess.run', return_value=status):
            stop_owned(proc)
        self.assertEqual([(4321, signal.SIGTERM), (4321, signal.SIGKILL)], [call.args for call in kill.call_args_list])
        self.assertTrue(proc._short_video_stopped)

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group cleanup')
    def test_posix_permission_failures_stay_errors_for_live_or_unproven_groups(self):
        cases = [
            ('darwin', 4321, None, '', 0, errno.EPERM),
            ('darwin', 9999, 0, '', 0, errno.EPERM),
            ('darwin', 4321, 0, '4322 4321 S\n', 0, errno.EPERM),
            ('darwin', 4321, 0, '4322 9999 Z\n', 0, errno.EPERM),
            ('darwin', 4321, 0, 'malformed', 0, errno.EPERM),
            ('darwin', 4321, 0, '', 2, errno.EPERM),
            ('darwin', 4321, 0, '', 0, errno.EACCES),
            ('linux', 4321, 0, '', 0, errno.EPERM),
        ]
        for platform, group, returncode, members, ps_code, error in cases:
            with self.subTest(case=(platform, group, returncode, members, ps_code, error)):
                proc = Mock(pid=4321, _short_video_pgid=group, _short_video_stopped=False)
                proc.poll.return_value = returncode
                status = subprocess.CompletedProcess([], ps_code, stdout=members, stderr='')
                with patch('short_video_portability.sys.platform', platform), \
                        patch('short_video_portability.os.killpg', side_effect=PermissionError(error, 'denied')) as kill, \
                        patch('short_video_portability.subprocess.run', return_value=status):
                    with self.assertRaises(PermissionError):
                        stop_owned(proc)
                self.assertFalse(proc._short_video_stopped)
                kill.assert_called_once_with(4321, signal.SIGTERM)

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group cleanup')
    def test_darwin_eperm_is_not_ignored_when_group_inspection_fails(self):
        failures = (OSError('ps unavailable'), subprocess.TimeoutExpired('ps', 2),
                    subprocess.CompletedProcess([], 1, stdout='', stderr='ps: cannot inspect group'))
        for result in failures:
            with self.subTest(failure=type(result).__name__):
                proc = Mock(pid=4321, _short_video_pgid=4321, _short_video_stopped=False)
                proc.poll.return_value = 0
                with patch('short_video_portability.sys.platform', 'darwin'), \
                        patch('short_video_portability.os.killpg', side_effect=PermissionError(errno.EPERM, 'denied')), \
                        patch('short_video_portability.subprocess.run') as inspect:
                    if isinstance(result, Exception):
                        inspect.side_effect = result
                    else:
                        inspect.return_value = result
                    with self.assertRaises(PermissionError):
                        stop_owned(proc)
                self.assertFalse(proc._short_video_stopped)

    def test_lock_file_symlinks_are_rejected(self):
        destination = self.root / 'real'
        destination.touch()
        link = self.root / 'linked'
        try:
            link.symlink_to(destination)
        except OSError as exc:
            self.skipTest(f'Creating a test symlink is unavailable: {exc}')
        with self.assertRaises(OSError):
            with exclusive_file_lock(link):
                self.fail('must not follow lock-file link')

    def test_process_output_and_literal_arguments_work(self):
        result = run_process([sys.executable, '-c', 'import sys; print(sys.argv[1])', 'literal;& argument'])
        self.assertEqual('literal;& argument', result.decode().strip())
        code, output = _run([sys.executable, '-c', 'print("recorder output")'])
        self.assertEqual((0, 'recorder output'), (code, output.strip()))
        with self.assertRaisesRegex(VideoError, 'exit 7'):
            run_process([sys.executable, '-c', 'raise SystemExit(7)'])

    def _tree_script(self, marker, *, exit_parent=False):
        return (
            'import json, os, subprocess, sys, time; from pathlib import Path; '
            'child=subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], '
            'stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); '
            f'Path({str(marker)!r}).write_text(json.dumps([os.getpid(), child.pid])); '
            + ('print("done")' if exit_parent else 'time.sleep(30)')
        )

    def _assert_tree_stopped(self, marker):
        self.assertTrue(marker.exists(), 'The lightweight child did not start before the deadline')
        pids = json.loads(marker.read_text())
        deadline = time.monotonic() + 3
        while any(pid_alive(pid) for pid in pids) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(any(pid_alive(pid) for pid in pids), f'Owned processes remain alive: {pids}')

    def test_timeout_stops_owned_child_and_grandchild_but_not_unrelated_process(self):
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for runner, error in ((run_process, VideoError), (_run, RecordingError)):
                with self.subTest(runner=runner.__name__):
                    marker = self.root / f'{runner.__name__}.json'
                    with self.assertRaises(error):
                        runner([sys.executable, '-c', self._tree_script(marker)], timeout=1)
                    self._assert_tree_stopped(marker)
                    self.assertIsNone(sentinel.poll(), 'Unrelated process must remain untouched')
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=5)

    def test_normal_parent_exit_also_cleans_owned_descendants(self):
        for runner in (run_process, _run):
            with self.subTest(runner=runner.__name__):
                marker = self.root / f'exited-{runner.__name__}.json'
                runner([sys.executable, '-c', self._tree_script(marker, exit_parent=True)], timeout=5)
                self._assert_tree_stopped(marker)

    def test_pipe_line_reader_keeps_buffered_lines_after_process_exit(self):
        proc = spawn_owned([sys.executable, '-c', 'print("START"); print("END")'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        reader = OutputLines(proc.stdout)
        try:
            lines = []
            deadline = time.monotonic() + 5
            while not reader.eof and time.monotonic() < deadline:
                value = reader.read(0.1)
                if value:
                    lines.append(value.strip())
            self.assertTrue(reader.eof)
            self.assertEqual(['START', 'END'], lines)
        finally:
            stop_owned(proc)
            reader.close()
        self.assertFalse(reader.thread.is_alive())

    def test_recorder_reads_real_pipe_markers_with_only_capture_actions_mocked(self):
        scenario = {'max_seconds': 1, 'start_marker': 'START', 'end_marker': 'END'}
        argv = [sys.executable, '-c', 'print("START", flush=True); print("END", flush=True)']
        raw = self.root / 'fixture-only.mp4'
        with patch('short_video_recorder._test_command', return_value=argv), \
                patch('short_video_recorder._start_android_recording', return_value=(None, 123, '/owned-fixture')) as start, \
                patch('short_video_recorder._finish_android_recording', return_value=raw), \
                patch('short_video_recorder._run', return_value=(0, '')):
            result, log = _run_and_capture(self.root, scenario, 'android_emulator', 'emulator-fixture', self.root)
        self.assertEqual(raw, result)
        self.assertIn('START', log)
        self.assertIn('END', log)
        start.assert_called_once()

    def test_failed_emulator_boot_cleans_only_spawned_process_not_a_reused_serial(self):
        process = Mock()
        with patch('short_video_recorder._emulator_binary', return_value='fixture-emulator'), \
                patch('short_video_recorder._run', side_effect=[(0, 'fixture-avd'), (0, '')]) as run, \
                patch('short_video_recorder._free_android_port', return_value=5580), \
                patch('short_video_recorder.spawn_owned', return_value=process), \
                patch('short_video_recorder._wait_android', side_effect=RecordingError('boot_failed')), \
                patch('short_video_recorder._stop_group') as stop, \
                patch('short_video_recorder._wait_android_gone') as wait:
            with self.assertRaisesRegex(RecordingError, 'boot_failed'):
                with android_device({'android_avd': 'fixture-avd'}):
                    self.fail('failed boot must not yield a device')
        stop.assert_called_once_with(process, interrupt=False)
        wait.assert_not_called()
        self.assertFalse(any('kill' in call.args[0] for call in run.call_args_list))

    def test_remote_cleanup_failure_still_stops_both_owned_local_processes(self):
        # Exercise the internal capture loop with a one-second deadline, without
        # a real scenario/emulator or waiting for its normal 180-second allowance.
        scenario = {'max_seconds': -179, 'start_marker': 'START', 'end_marker': 'END'}
        children = []

        def spawn(*args, **kwargs):
            proc = spawn_owned(*args, **kwargs)
            children.append(proc)
            return proc

        def start(*args):
            proc = spawn([sys.executable, '-c', 'import time; time.sleep(30)'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return proc, 123, '/fixture-owned'

        argv = [sys.executable, '-c', 'import time; print("START", flush=True); time.sleep(30)']
        try:
            with patch('short_video_recorder._test_command', return_value=argv), \
                    patch('short_video_recorder.spawn_owned', side_effect=spawn), \
                    patch('short_video_recorder._start_android_recording', side_effect=start), \
                    patch('short_video_recorder._stop_android_remote', side_effect=RecordingError('fixture_remote_failure')), \
                    patch('short_video_recorder._run', return_value=(0, '')):
                with self.assertRaisesRegex(RecordingError, 'fixture_remote_failure'):
                    _run_and_capture(self.root, scenario, 'android_emulator', 'emulator-fixture', self.root)
            self.assertEqual(2, len(children))
            self.assertTrue(all(child.poll() is not None for child in children))
            self.assertTrue(all(child._short_video_stopped for child in children))
        finally:
            for child in children:
                stop_owned(child)

    @unittest.skipUnless(os.name == 'nt', 'Windows-specific ownership guard')
    def test_windows_refuses_to_clean_a_process_it_did_not_create(self):
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with self.assertRaisesRegex(OSError, 'without an owned job'):
                stop_owned(proc)
            self.assertIsNone(proc.poll())
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    @unittest.skipUnless(os.name == 'nt', 'iOS is unavailable on Windows')
    def test_windows_ios_recording_fails_before_device_commands(self):
        with patch('short_video_recorder._simulator_rows') as commands:
            with self.assertRaisesRegex(RecordingError, 'ios_simulator_requires_macos'):
                with ios_device({}):
                    self.fail('must not launch an iOS simulator')
            commands.assert_not_called()


if __name__ == '__main__':
    unittest.main()
