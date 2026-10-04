from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from short_video_pipeline import atomic_json, canonical, file_hash
from short_video_recorder import (
    RecordingError,
    _safe_rel,
    _marker_line,
    _run_and_capture,
    _start_android_recording,
    _stop_android_remote,
    _test_command,
    _wait_android,
    android_device,
    isolated_source_checkout,
    load_scenarios,
    managed_recording_attestation,
    recording_lock,
    require_promotable_app,
    resolve_project,
    scenario_fingerprint,
    scenario_for_topic,
    validate_scenario,
)


class RecorderPolicyTests(unittest.TestCase):
    def test_vaultxt_contract_requires_disposable_capture_and_separate_completion(self):
        scenario = load_scenarios()['vaultxt-log-inspection-flow']
        self.assertEqual('true', scenario['dart_defines']['VAULTXT_VIDEO_FLOW'])
        self.assertEqual('true', scenario['dart_defines']['VAULTXT_CAPTURE_DISPOSABLE'])
        self.assertEqual('VIDEO_STEP:inspected_unchanged', scenario['end_marker'])
        self.assertEqual('VIDEO_STEP:complete', scenario['completion_marker'])
        for marker in ('', scenario['end_marker'], scenario['start_marker'], 'complete\nforged', None):
            with self.subTest(marker=marker), self.assertRaisesRegex(RecordingError, 'completion_marker_invalid'):
                validate_scenario(dict(scenario, completion_marker=marker))
    def test_mock_backed_repository_scenarios_are_quarantined(self):
        scenarios = load_scenarios()
        scenario = scenarios['tagweaver-core-edit-flow']
        self.assertEqual('APP-0002', scenario['app_id'])
        self.assertEqual(['TOPIC-0008'], scenario['topics'])
        self.assertFalse(scenario['production_eligible'])
        self.assertIn('screenshot_tagcore', scenario['production_block_reason'])
        self.assertFalse(scenarios['quivra-conversion-flow']['production_eligible'])
        self.assertFalse(scenarios['segra-trim-flow']['production_eligible'])
        for app, topic in [('APP-0001', 'TOPIC-0007'), ('APP-0002', 'TOPIC-0008'), ('APP-0004', 'TOPIC-0009')]:
            with self.assertRaisesRegex(RecordingError, 'recording_scenario_not_found_for_topic'):
                scenario_for_topic(app, topic, 'android_emulator')
        for scenario_id in ('quivra-conversion-flow', 'tagweaver-core-edit-flow', 'segra-trim-flow'):
            with self.assertRaisesRegex(RecordingError, 'recording_scenario_production_disabled'):
                require_promotable_app(scenarios[scenario_id], 'android_emulator')
    def test_topic_selects_exact_production_scenario(self):
        expected = {
            ('APP-0003', 'TOPIC-0031', 'android_emulator'): 'vaultxt-log-inspection-flow',
            ('APP-0005', 'TOPIC-0010', 'ios_simulator'): 'clipnest-saved-snippet-flow',
            ('APP-0006', 'TOPIC-0012', 'android_emulator'): 'aligna-preview-before-apply',
        }
        for key, scenario_id in expected.items():
            with self.subTest(key=key):
                self.assertEqual(scenario_id, scenario_for_topic(*key)['scenario_id'])
        with self.assertRaisesRegex(RecordingError, 'recording_scenario_not_found_for_topic'):
            scenario_for_topic('APP-0002', 'TOPIC-0029', 'android_emulator')
        with self.assertRaisesRegex(RecordingError, 'recording_scenario_not_found_for_topic'):
            scenario_for_topic('APP-0005', 'TOPIC-0010', 'android_emulator')

    def test_relative_path_and_physical_device_guards(self):
        for value in ['../escape', '/absolute', 'a/../../b', r'\rooted', r'C:relative', r'C:\absolute', r'..\escape']:
            with self.subTest(value=value), self.assertRaises(RecordingError):
                _safe_rel(value, 'fixture')
        scenario = load_scenarios()['tagweaver-core-edit-flow']
        with self.assertRaisesRegex(RecordingError, 'physical_android_device_forbidden'):
            with android_device(scenario, explicit_serial='R5CT20ATWSH'):
                self.fail('physical device must never be yielded')

    def test_android_boot_fails_immediately_when_owned_emulator_exits(self):
        proc = Mock()
        proc.poll.return_value = 17
        with self.assertRaisesRegex(RecordingError, 'android_emulator_exited_during_boot'):
            _wait_android('emulator-5580', timeout=60, proc=proc)

    def test_recording_lock_rejects_concurrent_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            with recording_lock(tmp):
                with self.assertRaisesRegex(RecordingError, 'another_recording_is_active'):
                    with recording_lock(tmp):
                        pass

    def test_android_screenrecord_uses_owned_remote_pid_only(self):
        proc = Mock()
        proc.poll.return_value = None
        with patch(
            'short_video_recorder._android_screenrecord_pids',
            side_effect=[[], [4321]],
        ), patch(
            'short_video_recorder.spawn_owned',
            return_value=proc,
        ) as popen, patch('short_video_recorder.time.sleep'):
            local, pid, remote = _start_android_recording(
                'emulator-5580', '/tmp', 30)
        self.assertIs(proc, local)
        self.assertEqual(4321, pid)
        self.assertTrue(remote.startswith('/data/local/tmp/onnellab-record-'))
        command = popen.call_args.args[0]
        self.assertEqual(
            ['adb', '-s', 'emulator-5580', 'shell', 'screenrecord'],
            command[:5],
        )
        self.assertIn('--size', command)
        self.assertIn('720x1280', command)
        self.assertIn('--bit-rate', command)
        self.assertNotIn('pkill', command)

    def test_android_stop_targets_only_owned_remote_pid(self):
        calls = []
        states = iter([0, 1])
        def fake_run(argv, **kwargs):
            calls.append(argv)
            if argv[-3:] == ['kill', '-0', '4321']:
                return next(states), ''
            return 0, ''
        with patch('short_video_recorder._run', side_effect=fake_run), \
                patch('short_video_recorder.time.sleep'):
            _stop_android_remote('emulator-5580', 4321)
        self.assertIn(['adb', '-s', 'emulator-5580', 'shell', 'kill', '-2', '4321'], calls)
        self.assertFalse(any('pkill' in ' '.join(call) for call in calls))

    def test_flutter_command_is_fixed_integration_target_and_no_pub(self):
        scenario = load_scenarios()['tagweaver-core-edit-flow']
        with patch('short_video_recorder.shutil.which', return_value='/flutter'):
            command = _test_command(Path('/repo'), scenario, 'emulator-5580')
        self.assertEqual('/flutter', command[0])
        self.assertEqual('test', command[1])
        self.assertEqual(scenario['test_target'], command[2])
        self.assertIn('--no-pub', command)
        self.assertIn('-d', command)
        self.assertIn('emulator-5580', command)
        self.assertNotIn('shell', command)
    def test_managed_recording_attestation_binds_app_topic_and_hash(self):
        self.check_attestation_fixture('aligna-preview-before-apply', allowed=True)

    def test_old_managed_recordings_cannot_bypass_current_scenario_quarantine(self):
        for scenario_id in ('quivra-conversion-flow', 'tagweaver-core-edit-flow', 'segra-trim-flow'):
            with self.subTest(scenario=scenario_id):
                self.check_attestation_fixture(scenario_id, allowed=False)

    def check_attestation_fixture(self, scenario_id, *, allowed):
        scenario = load_scenarios()[scenario_id]
        topic = scenario['topics'][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / 'recordings' / scenario_id / 'a.mp4'
            video.parent.mkdir(parents=True)
            video.write_bytes(b'video-fixture')
            digest = file_hash(video)
            index = {
                'schema_version': 1,
                'recordings': {
                    scenario_id + ':android_emulator': {
                        'scenario_id': scenario['scenario_id'],
                        'scenario_hash': hashlib.sha256(canonical(scenario)).hexdigest(),
                        'app_id': scenario['app_id'],
                        'platform': 'android_emulator',
                        'fingerprint': 'f' * 64,
                        'source_commit': 'a' * 40,
                        'path': str(video.relative_to(root)),
                        'sha256': digest,
                        'recorded_at': '2026-09-21T00:00:00+00:00',
                        'production_eligible': True,
                        'topics': [topic],
                    }
                },
            }
            (root / 'recordings').mkdir(exist_ok=True)
            atomic_json(root / 'recordings/index.json', index)
            job = {
                'brief': {
                    'recording': str(video.relative_to(root)),
                    'app_id': scenario['app_id'],
                    'topic_id': topic,
                },
                'assets': {'recording': {'sha256': digest}},
            }
            if not allowed:
                with patch('short_video_recorder._verified_video', return_value=True), \
                        self.assertRaisesRegex(RecordingError, 'managed_recording_scenario_changed'):
                    managed_recording_attestation(root, job)
                return
            with patch('short_video_recorder._verified_video', return_value=True):
                attestation = managed_recording_attestation(root, job)
            self.assertEqual(scenario_id, attestation['scenario_id'])
            self.assertEqual(digest, attestation['sha256'])
            wrong = json.loads(json.dumps(job))
            wrong['brief']['topic_id'] = 'TOPIC-0029'
            with patch('short_video_recorder._verified_video', return_value=True),                     self.assertRaisesRegex(RecordingError, 'managed_recording_scope_mismatch'):
                managed_recording_attestation(root, wrong)


class CaptureCompletionTests(unittest.TestCase):
    def capture(self, events, *, platform='android_emulator', cleanup_error=False, require_completion=False):
        clock = [0]
        test, recorder = Mock(), Mock()
        recorder.poll.return_value = None
        test.stdout = Mock()
        test.poll.return_value = None
        class Reader:
            def __init__(self, stream):
                self.eof = False
                self.events = iter(events)
            def read(self, timeout):
                elapsed, line, test_code, recorder_code = next(self.events)
                clock[0] = elapsed
                test.poll.return_value = test_code
                recorder.poll.return_value = recorder_code
                self.eof = line == ''
                return line
            def close(self):
                pass
        finished = []
        def finish(*args):
            finished.append(clock[0])
            return Path('owned-raw.mp4')
        with ExitStack() as stack:
            def patched(name, **kwargs):
                return stack.enter_context(patch('short_video_recorder.' + name, **kwargs))
            patched('spawn_owned', return_value=test)
            patched('_test_command', return_value=['fake-flutter'])
            patched('OutputLines', side_effect=Reader)
            patched('time.monotonic', side_effect=lambda: clock[0])
            patched('_start_android_recording', return_value=(recorder, 42, 'owned-remote.mp4'))
            patched('_start_ios_recording', return_value=(recorder, Path('owned-raw.mov')))
            patched('_finish_android_recording', side_effect=finish)
            patched('_finish_ios_recording', side_effect=finish)
            patched('_stop_android_remote')
            stopped = patched('_stop_group')
            run = patched('_run', side_effect=RecordingError('cleanup_failed') if cleanup_error else None)
            try:
                scenario = {'max_seconds': 60, 'start_marker': 'VIDEO_STEP:start', 'end_marker': 'VIDEO_STEP:end'}
                if require_completion:
                    scenario['completion_marker'] = 'VIDEO_STEP:complete'
                result = _run_and_capture(Path('fake'), scenario,
                    platform, 'owned-device', Path('fake-temp'))
                return result, finished
            finally:
                self.assertTrue(any(call.args[0] is test for call in stopped.call_args_list))
                for call in run.call_args_list:
                    self.assertTrue(call.kwargs['check'])

    def test_end_marker_stops_capture_before_later_successful_flutter_teardown(self):
        for platform in ('android_emulator', 'ios_simulator'):
            with self.subTest(platform=platform):
                result, finished = self.capture([(170, 'VIDEO_STEP:start\n', None, None),
                    (200, 'VIDEO_STEP:end\n', None, None), (220, '', 0, 0)], platform=platform)
                self.assertEqual(Path('owned-raw.mp4'), result[0])
                self.assertEqual([200], finished)

    def test_late_end_after_android_time_limit_cannot_accept_truncated_video(self):
        with self.assertRaisesRegex(RecordingError, 'recording_capture_timeout'):
            self.capture([(0, 'VIDEO_STEP:start\n', None, None),
                          (100, 'VIDEO_STEP:end\n', 0, None)])

    def test_recorder_exit_before_end_marker_is_not_success(self):
        with self.assertRaisesRegex(RecordingError, 'recording_ended_before_end_marker'):
            self.capture([(0, 'VIDEO_STEP:start\n', None, None),
                          (10, 'VIDEO_STEP:end\n', 0, 0)])

    def test_quoted_marker_diagnostics_are_not_capture_events(self):
        with self.assertRaisesRegex(RecordingError, 'recording_markers_missing'):
            self.capture([(0, 'Diagnostic: expecting VIDEO_STEP:start\n', None, None),
                          (1, 'Diagnostic: expecting VIDEO_STEP:end\n', None, None),
                          (2, '', 0, None)])

    def test_missing_end_and_nonzero_test_exit_fail_closed(self):
        for events, error in [
            ([(0, 'VIDEO_STEP:start\n', None, None), (10, '', 0, None)], 'recording_markers_missing'),
            ([(0, 'VIDEO_STEP:start\n', None, None), (10, 'VIDEO_STEP:end\n', None, None),
              (11, '', 1, 0)], 'recording_scenario_test_failed')]:
            with self.subTest(error=error), self.assertRaisesRegex(RecordingError, error):
                self.capture(events)

    def test_cleanup_failure_cannot_return_capture_success(self):
        with self.assertRaisesRegex(RecordingError, 'cleanup_failed'):
            self.capture([(0, 'VIDEO_STEP:start\n', None, None),
                (10, 'VIDEO_STEP:end\n', None, None), (11, '', 0, 0)], cleanup_error=True)

    def test_exact_marker_supports_only_documented_flutter_forwarding_prefixes(self):
        for line in ('VIDEO_STEP:end\n', 'flutter: VIDEO_STEP:end\n',
                     'I/flutter ( 123): VIDEO_STEP:end\n', '\x1b[32mVIDEO_STEP:end\x1b[0m\n'):
            self.assertTrue(_marker_line(line, 'VIDEO_STEP:end'))
        for line in ('expected VIDEO_STEP:end', 'VIDEO_STEP:end_extra', 'VIDEO_STEP:end failed',
                     'Exception: VIDEO_STEP:end', 'VIDEO_STEP:start VIDEO_STEP:end'):
            self.assertFalse(_marker_line(line, 'VIDEO_STEP:end'))

    def test_completion_after_disposal_is_required_but_not_part_of_visual_clip(self):
        result, finished = self.capture([(0, 'VIDEO_STEP:start\n', None, None),
            (10, 'VIDEO_STEP:end\n', None, None), (70, 'flutter: VIDEO_STEP:complete\n', None, 0),
            (71, '', 0, 0)], require_completion=True)
        self.assertEqual([10], finished)
        self.assertEqual(Path('owned-raw.mp4'), result[0])

    def test_truncated_stdout_or_quoted_completion_cannot_complete_capture(self):
        for tail in ('', 'Expected VIDEO_STEP:complete after disposal\n'):
            with self.subTest(tail=tail), self.assertRaisesRegex(RecordingError, 'completion_marker_missing'):
                self.capture([(0, 'VIDEO_STEP:start\n', None, None),
                    (10, 'VIDEO_STEP:end\n', None, None), (11, tail, None, 0),
                    (12, '', 0, 0)], require_completion=True)

    def test_completion_before_visual_end_or_failed_test_is_rejected(self):
        cases = [
            ([(0, 'VIDEO_STEP:start\n', None, None), (1, 'VIDEO_STEP:complete\n', None, None)],
             'completion_before_visual_end'),
            ([(0, 'VIDEO_STEP:start\n', None, None), (10, 'VIDEO_STEP:end\n', None, None),
              (11, 'VIDEO_STEP:complete\n', None, 0), (12, '', 1, 0)], 'scenario_test_failed')]
        for events, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(RecordingError, error):
                self.capture(events, require_completion=True)

    def test_completion_does_not_override_cleanup_failure(self):
        with self.assertRaisesRegex(RecordingError, 'cleanup_failed'):
            self.capture([(0, 'VIDEO_STEP:start\n', None, None),
                (10, 'VIDEO_STEP:end\n', None, None), (11, 'VIDEO_STEP:complete\n', None, 0),
                (12, '', 0, 0)], require_completion=True, cleanup_error=True)


class RecorderSourceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.remote = self.root / 'remote.git'
        self.seed = self.root / 'seed'
        self.work = self.root / 'work'
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(self.remote)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', 'init', '--initial-branch=main', str(self.seed)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', '-C', str(self.seed), 'config', 'user.email', 'test@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(self.seed), 'config', 'user.name', 'Test'], check=True)
        for rel in ['lib/app.dart', 'integration_test/flow_test.dart',
                    'pubspec.yaml', 'pubspec.lock', 'android/app/build.gradle']:
            path = self.seed / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rel)
        subprocess.run(['git', '-C', str(self.seed), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.seed), 'commit', '-m', 'init'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', '-C', str(self.seed), 'remote', 'add', 'origin', str(self.remote)], check=True)
        subprocess.run(['git', '-C', str(self.seed), 'push', '-u', 'origin', 'main'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', 'clone', str(self.remote), str(self.work)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.flutter = self.root / 'flutter'
        self.flutter.write_text('#!/bin/sh\necho \'{"frameworkRevision":"fixture"}\'\n')
        self.flutter.chmod(self.flutter.stat().st_mode | stat.S_IXUSR)
        self.scenario = {
            'scenario_id': 'fixture-flow',
            'app_id': 'APP-0002',
            'repository': 'fixture',
            'runner': 'flutter_integration_test',
            'test_target': 'integration_test/flow_test.dart',
            'start_marker': 'VIDEO_STEP:start',
            'end_marker': 'VIDEO_STEP:end',
            'max_seconds': 30,
            'platforms': ['android_emulator'],
            'android_avd': 'Fixture_AVD',
            'ios_simulator_name': 'Fixture iPhone',
            'dart_defines': {'FIXTURE_MODE': 'video'},
            'watch_paths': ['lib', 'integration_test/flow_test.dart',
                            'pubspec.yaml', 'pubspec.lock'],
            'topics': ['TOPIC-0008'],
            'production_eligible': True,
        }

    def test_fingerprint_uses_origin_tree_not_dirty_worktree(self):
        (self.work / 'lib/app.dart').write_text('uncommitted user work')
        # Real git tree queries remain exercised; only the Flutter version process
        # is faked so this test needs neither a POSIX shell nor an installed SDK.
        from short_video_recorder import _run
        def run_without_flutter(argv, **kwargs):
            if argv[0] == str(self.flutter):
                return 0, '{"frameworkRevision":"fixture"}'
            return _run(argv, **kwargs)
        with patch('short_video_recorder.shutil.which', return_value=str(self.flutter)), \
                patch('short_video_recorder._run', side_effect=run_without_flutter):
            fingerprint, commit = scenario_fingerprint(
                self.work, self.scenario, 'android_emulator', refresh=False)
        self.assertRegex(fingerprint, r'^[0-9a-f]{64}$')
        self.assertRegex(commit, r'^[0-9a-f]{40}$')
        self.assertEqual('uncommitted user work', (self.work / 'lib/app.dart').read_text())
    def test_project_subdir_resolves_flutter_app_inside_monorepo(self):
        project = self.work / 'vaultxt'
        project.mkdir()
        (project / 'pubspec.yaml').write_text('name: fixture')
        resolved = resolve_project(
            self.work,
            {'project_subdir': 'vaultxt'},
        )
        self.assertEqual(project.resolve(), resolved)
        with self.assertRaisesRegex(RecordingError, 'recording_project_missing'):
            resolve_project(self.work, {'project_subdir': 'missing'})

    def test_isolated_checkout_can_change_without_touching_active_worktree(self):
        original = (self.work / 'lib/app.dart').read_text()
        commit = subprocess.run(
            ['git', '-C', str(self.work), 'rev-parse', 'origin/main'],
            check=True, stdout=subprocess.PIPE, text=True,
        ).stdout.strip()
        with tempfile.TemporaryDirectory() as temp:
            with isolated_source_checkout(self.work, commit, temp) as source:
                (source / 'lib/app.dart').write_text('private build mutation')
                self.assertEqual('private build mutation', (source / 'lib/app.dart').read_text())
                self.assertEqual(original, (self.work / 'lib/app.dart').read_text())
        self.assertEqual(original, (self.work / 'lib/app.dart').read_text())


if __name__ == '__main__':
    unittest.main()
