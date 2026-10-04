"""No renderer, emulator, network, credentials or external writes in these tests."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import short_video_scheduled_worker as worker

SLOT = '2026-10-05T09:00:00+09:00'
APP = {'app_id': 'APP-0001', 'scenario_id': 'quivra-conversion-flow'}
CHANNEL = 'UC' + 'a' * 22


class ScheduledWorkerTests(unittest.TestCase):
    def test_all_six_templates_make_valid_deterministic_briefs(self):
        scenarios = worker.load_scenarios()
        self.assertEqual(6, len(worker.templates()))
        for scenario_id in worker.templates():
            app = {'app_id': scenarios[scenario_id]['app_id'], 'scenario_id': scenario_id}
            brief = worker.make_brief(SLOT, app, 'recordings/workflow.mp4')
            self.assertFalse(brief['test_only'])
            self.assertNotIn('narration', brief)
            self.assertEqual(brief, worker.make_brief(SLOT, app, 'recordings/workflow.mp4'))

    def test_default_dry_run_has_no_provider_or_queue_writes(self):
        args = SimpleNamespace(config=worker.ROOT / 'data/video_rotation.json', execute=False,
            asset_root=Path('unused-assets'), state_root=Path('unused-state'),
            projects_root=Path('unused-projects'), browser=None, reconcile_slot=None)
        with patch.object(worker, 'Queue') as queue, patch.object(worker, 'YouTube') as api, \
                patch('short_video_coordinator.GitHubLedger') as store, \
                patch.object(worker, 'preflight', return_value=['scheduled_worker_disabled']), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, worker.run_cli(args))
        queue.assert_not_called()
        api.assert_not_called()
        store.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertTrue(result['dry_run'])
        self.assertFalse(result['shared_receipts_checked'])

    def test_disabled_execute_does_not_even_read_remote_ledger(self):
        args = SimpleNamespace(config=worker.ROOT / 'data/video_rotation.json', execute=True,
            asset_root=Path('assets'), state_root=Path('state'), projects_root=Path('projects'),
            browser=None, reconcile_slot=None)
        with patch('short_video_coordinator.GitHubLedger') as store, \
                patch.object(worker, 'preflight', return_value=['scheduled_worker_disabled']), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, worker.run_cli(args))
        store.assert_not_called()

    def fixture(self):
        events = []
        coordinator = Mock()
        coordinator.claim.side_effect = lambda *args: events.append('claim')
        coordinator.mark_upload_started.side_effect = lambda *args: events.append('intent')
        coordinator.complete.side_effect = lambda *args: events.append('receipt')
        queue = Mock()
        queue.assets = Path('assets')
        _, _, job_id = worker.identity(SLOT, APP)
        job = {'id': job_id, 'brief': worker.make_brief(SLOT, APP, 'recordings/workflow.mp4'),
               'upload': {'video_id': 'abcdefghijk'}, 'status': 'published'}
        queue.enqueue.return_value = job
        queue.render.return_value = job
        queue.status.return_value = job
        queue.lock = contextlib.nullcontext
        queue._read.return_value = {'jobs': {job_id: job}}
        api = Mock(channel=CHANNEL)
        recorder = Mock(return_value={'path': 'recordings/workflow.mp4'})
        recorder.side_effect = lambda *args, **kwargs: (events.append('record') or {'path': 'recordings/workflow.mp4'})
        return events, coordinator, queue, api, recorder, job

    def test_shared_claim_and_intent_precede_specific_job_upload(self):
        events, coordinator, queue, api, recorder, job = self.fixture()
        with patch.object(worker, 'check_idle_avd'), patch.object(worker, 'automatic_choices', return_value={}), \
                patch.object(worker, 'Uploader') as uploader:
            uploader.return_value.run.side_effect = lambda *args, **kwargs: (events.append('upload') or job)
            result = worker.execute_slot(coordinator, {'channel_id': CHANNEL}, SLOT, APP,
                queue=queue, projects=Path('projects'), api_factory=lambda: api,
                recorder=recorder, receipt_reader=lambda *args: {'posted_url': 'verified'})
        self.assertEqual(['claim', 'record', 'intent', 'upload', 'receipt'], events)
        uploader.return_value.run.assert_called_once_with(job['id'], execute=True, reconcile=False)
        self.assertEqual('published', result['status'])

    def test_ambiguous_public_verification_requires_reconciliation(self):
        _, coordinator, queue, api, recorder, job = self.fixture()
        with patch.object(worker, 'check_idle_avd'), patch.object(worker, 'automatic_choices', return_value={}), \
                patch.object(worker, 'Uploader') as uploader:
            uploader.return_value.run.return_value = job
            with self.assertRaisesRegex(worker.VideoError, 'requires_reconciliation'):
                worker.execute_slot(coordinator, {'channel_id': CHANNEL}, SLOT, APP,
                    queue=queue, projects=Path('projects'), api_factory=lambda: api,
                    recorder=recorder, receipt_reader=Mock(side_effect=OSError()))
        coordinator.complete.assert_not_called()
        coordinator.mark_reconcile_required.assert_called_once()

    def test_reconcile_without_known_video_id_cannot_upload(self):
        _, coordinator, queue, api, recorder, job = self.fixture()
        job['upload'] = {}
        with patch.object(worker, 'Uploader') as uploader:
            with self.assertRaisesRegex(worker.VideoError, 'manual_identity'):
                worker.execute_slot(coordinator, {'channel_id': CHANNEL}, SLOT, APP,
                    queue=queue, projects=Path('projects'), api_factory=lambda: api,
                    recorder=recorder, reconcile=True)
        recorder.assert_not_called()
        uploader.assert_not_called()
        coordinator.claim.assert_not_called()

    def test_busy_emulator_blocks_before_claim_or_recording(self):
        _, coordinator, queue, api, recorder, _ = self.fixture()
        with patch.object(worker.subprocess, 'run', return_value=SimpleNamespace(stdout='emulator-5554\tdevice\n')):
            with self.assertRaisesRegex(worker.VideoError, 'owned_elsewhere'):
                worker.execute_slot(coordinator, {'channel_id': CHANNEL}, SLOT, APP,
                    queue=queue, projects=Path('projects'), api_factory=lambda: api, recorder=recorder)
        coordinator.claim.assert_not_called()
        recorder.assert_not_called()

    def test_private_provider_status_never_creates_receipt(self):
        _, _, _, api, _, job = self.fixture()
        api.video.return_value = {'snippet': {'channelId': CHANNEL},
            'status': {'privacyStatus': 'private', 'uploadStatus': 'processed'},
            'processingDetails': {'processingStatus': 'succeeded'}}
        fetch = Mock()
        with self.assertRaisesRegex(worker.VideoError, 'not_confirmed'):
            worker.public_receipt(api, job, datetime.now(timezone.utc), fetch=fetch)
        fetch.assert_not_called()

    def test_preflight_reports_fence_history_auth_and_resources_without_startup(self):
        with patch.object(worker, 'check_config', return_value={'configured': False}), \
                patch.object(worker.shutil, 'which', return_value=None), \
                patch.object(worker.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)), \
                patch.object(worker.host_platform, 'system', return_value='Windows'), \
                patch.object(worker.subprocess, 'run') as process:
            blockers = worker.preflight({}, None, assets=Path('.'), state=Path('.'),
                projects=Path('.'), browser=None, recording_platform='android_emulator')
        for expected in ('legacy_writer_not_fenced', 'existing_publication_history_not_reconciled',
                         'existing_onnellab_youtube_credentials_unavailable',
                         'desktop_resource_coordination_required', 'disk_free_below_10gib'):
            self.assertIn(expected, blockers)
        process.assert_not_called()

    def test_foreign_channel_is_blocked_before_claim_and_heavy_work(self):
        _, coordinator, queue, api, recorder, _ = self.fixture()
        api.channel = 'UC' + 'b' * 22
        with self.assertRaisesRegex(worker.VideoError, 'channel_mismatch'):
            worker.execute_slot(coordinator, {'channel_id': CHANNEL}, SLOT, APP,
                queue=queue, projects=Path('projects'), api_factory=lambda: api, recorder=recorder)
        coordinator.claim.assert_not_called()
        recorder.assert_not_called()
        queue.enqueue.assert_not_called()

    def test_repository_drive_disk_floor_applies_when_other_paths_have_space(self):
        with patch.object(worker, 'check_config', return_value={'configured': False}), \
                patch.object(worker, 'private_path_permissions', return_value=False), \
                patch.object(worker.shutil, 'disk_usage',
                    side_effect=lambda path: SimpleNamespace(
                        free=1 if path == worker.ROOT else worker.MIN_FREE * 2)) as usage:
            blockers = worker.preflight({}, None, assets=Path('..'), state=Path('..'),
                projects=Path('..'), browser=None, recording_platform='android_emulator')
        usage.assert_any_call(worker.ROOT)
        self.assertIn('disk_free_below_10gib', blockers)

    def test_missing_timezone_database_blocks_before_recording(self):
        with patch.object(worker, 'ZoneInfo', side_effect=worker.ZoneInfoNotFoundError('Asia/Seoul')), \
                patch.object(worker, 'check_config', return_value={'configured': False}), \
                patch.object(worker, 'private_path_permissions', return_value=False):
            blockers = worker.preflight({}, None, assets=Path('.'), state=Path('.'),
                projects=Path('.'), browser=None, recording_platform='android_emulator')
        self.assertIn('iana_timezone_data_missing_install_runtime_requirements', blockers)

    def test_local_claim_token_is_durable_and_never_taken_from_shared_state(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(config=worker.ROOT / 'data/video_rotation.json', execute=True,
                asset_root=Path(directory) / 'assets', state_root=Path(directory) / 'state',
                projects_root=Path(directory), browser=None, reconcile_slot=None)
            config = {'enabled': True, 'channel_id': CHANNEL, 'owner_id': 'windows-n'}
            proposed = {'slot': SLOT, 'selected_app': APP, 'blockers': []}
            with patch.object(worker, 'load_json', wraps=worker.load_json) as load, \
                    patch('short_video_coordinator.config_blockers', return_value=[]), \
                    patch('short_video_coordinator.GitHubLedger') as ledger, \
                    patch('short_video_coordinator.plan', return_value=proposed), \
                    patch('short_video_coordinator.Coordinator') as coordinator, \
                    patch.object(worker, 'preflight', return_value=[]), \
                    patch.object(worker, 'execute_slot', return_value={'status': 'published'}), \
                    contextlib.redirect_stdout(io.StringIO()):
                original = worker.load_json._mock_wraps
                load.side_effect = lambda path: config if path == args.config else original(path)
                ledger.return_value.read.return_value = ({'schema_version': 1, 'slots': {}}, 'sha')
                worker.run_cli(args)
                first = coordinator.call_args.kwargs['claim_token']
                worker.run_cli(args)
                self.assertEqual(first, coordinator.call_args.kwargs['claim_token'])
                self.assertEqual(32, len(first))


if __name__ == '__main__':
    unittest.main()
