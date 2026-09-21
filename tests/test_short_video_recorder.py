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
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from short_video_pipeline import atomic_json, canonical, file_hash
from short_video_recorder import (
    RecordingError,
    _safe_rel,
    _start_android_recording,
    _stop_android_remote,
    _test_command,
    _wait_android,
    android_device,
    isolated_source_checkout,
    load_scenarios,
    managed_recording_attestation,
    recording_lock,
    resolve_project,
    scenario_fingerprint,
    scenario_for_topic,
)


class RecorderPolicyTests(unittest.TestCase):
    def test_repository_scenario_is_scoped_and_production_eligible(self):
        scenarios = load_scenarios()
        scenario = scenarios['tagweaver-core-edit-flow']
        self.assertEqual('APP-0002', scenario['app_id'])
        self.assertEqual(['TOPIC-0008'], scenario['topics'])
        self.assertTrue(scenario['production_eligible'])
    def test_topic_selects_exact_production_scenario(self):
        expected = {
            ('APP-0001', 'TOPIC-0007', 'android_emulator'): 'quivra-conversion-flow',
            ('APP-0002', 'TOPIC-0008', 'android_emulator'): 'tagweaver-core-edit-flow',
            ('APP-0003', 'TOPIC-0031', 'android_emulator'): 'vaultxt-log-inspection-flow',
            ('APP-0004', 'TOPIC-0009', 'android_emulator'): 'segra-trim-flow',
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
        for value in ['../escape', '/absolute', 'a/../../b']:
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
            'short_video_recorder.subprocess.Popen',
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
        scenario = load_scenarios()['tagweaver-core-edit-flow']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / 'recordings/app-0002/tagweaver-core-edit-flow/a.mp4'
            video.parent.mkdir(parents=True)
            video.write_bytes(b'video-fixture')
            digest = file_hash(video)
            index = {
                'schema_version': 1,
                'recordings': {
                    'tagweaver-core-edit-flow:android_emulator': {
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
                        'topics': ['TOPIC-0008'],
                    }
                },
            }
            (root / 'recordings').mkdir(exist_ok=True)
            atomic_json(root / 'recordings/index.json', index)
            job = {
                'brief': {
                    'recording': str(video.relative_to(root)),
                    'app_id': 'APP-0002',
                    'topic_id': 'TOPIC-0008',
                },
                'assets': {'recording': {'sha256': digest}},
            }
            with patch('short_video_recorder._verified_video', return_value=True):
                attestation = managed_recording_attestation(root, job)
            self.assertEqual('tagweaver-core-edit-flow', attestation['scenario_id'])
            self.assertEqual(digest, attestation['sha256'])
            wrong = json.loads(json.dumps(job))
            wrong['brief']['topic_id'] = 'TOPIC-0029'
            with patch('short_video_recorder._verified_video', return_value=True),                     self.assertRaisesRegex(RecordingError, 'managed_recording_scope_mismatch'):
                managed_recording_attestation(root, wrong)


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
        with patch('short_video_recorder.shutil.which', return_value=str(self.flutter)):
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
