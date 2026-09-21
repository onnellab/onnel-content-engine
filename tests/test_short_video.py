from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_pipeline import Queue, VideoError, load_json


class ShortVideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        (self.assets / 'recording.mp4').write_bytes(b'local recording fixture')
        self.now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        self.q = Queue(self.root / 'state', self.assets, clock=lambda: self.now)
        self.brief = dict(schema_version=1, app_id='APP-0003', topic_id='TOPIC-0001',
            locale='en', template='quick_demo', duration_seconds=15,
            due_at='2026-09-21T00:00:00+00:00', timezone='UTC',
            idempotency_key='demo-1', test_only=True, recording='recording.mp4',
            hook='Large file hard to read?', title='Read a large text file',
            description='Try a focused reading workflow.', cta='Try this on your own file.',
            captions=[dict(start=0, end=7, text='Open your text file'),
                      dict(start=7, end=15, text='Find the passage you need')])

    def test_duplicate_noop_and_conflict(self):
        first = self.q.enqueue(self.brief)
        before = self.q.state_path.read_bytes()
        self.assertEqual(first['id'], self.q.enqueue(copy.deepcopy(self.brief))['id'])
        self.assertEqual(before, self.q.state_path.read_bytes())
        changed = dict(self.brief, title='Different')
        with self.assertRaises(VideoError): self.q.enqueue(changed)
        (self.assets / 'recording.mp4').write_bytes(b'changed')
        with self.assertRaises(VideoError): self.q.enqueue(self.brief)

    def test_reject_invalid_fields(self):
        for field, value in [('app_id', 'APP-9999'), ('topic_id', 'TOPIC-9999'),
                ('locale', 'xx'), ('template', 'code'), ('duration_seconds', 31),
                ('duration_seconds', True), ('timezone', 'Mars/Base'),
                ('due_at', '2026-09-21T00:00:00'), ('test_only', 'false'),
                ('hook', 'x' * 300), ('recording', 'https://example.com/a.mp4')]:
            with self.subTest(field=field), self.assertRaises(VideoError):
                self.q.validate(dict(self.brief, **{field: value}))
        with self.assertRaises(VideoError): self.q.validate(dict(self.brief, executable='oops'))
        with self.assertRaises(VideoError): self.q.validate(dict(self.brief, timezone='Asia/Seoul'))

    def test_paths_and_symlink_escape(self):
        outside = self.root / 'outside.mp4'
        outside.write_bytes(b'x')
        (self.assets / 'escape.mp4').symlink_to(outside)
        for name in ['../outside.mp4', str(outside), 'escape.mp4', 'a/../../outside.mp4']:
            with self.subTest(name=name), self.assertRaises(VideoError):
                self.q.validate(dict(self.brief, recording=name))

    def test_future_jobs_wait_and_direct_render_rejects(self):
        job = self.q.enqueue(dict(self.brief, due_at='2027-01-01T00:00:00+00:00'))
        renderer = unittest.mock.Mock()
        self.assertIsNone(self.q.worker(renderer=renderer))
        with self.assertRaises(VideoError): self.q.render(job['id'], renderer=renderer)
        renderer.assert_not_called()
        self.assertEqual('queued', self.q.status(job['id'])['status'])

    def test_lock_rejects_second_process(self):
        with self.q.lock():
            with self.assertRaises(VideoError): self.q.enqueue(self.brief)

    def test_corrupt_state_fails_closed(self):
        self.q.enqueue(self.brief)
        self.q.state_path.write_text('{bad')
        with self.assertRaises(VideoError): self.q.enqueue(self.brief)
        self.assertEqual('{bad', self.q.state_path.read_text())

    def test_tampered_state_fails_closed(self):
        job = self.q.enqueue(self.brief)
        state = json.loads(self.q.state_path.read_text())
        state['jobs'][job['id']]['brief']['title'] = 'tampered'
        self.q.state_path.write_text(json.dumps(state))
        with self.assertRaises(VideoError): self.q.status()

    def test_dry_run_no_mutation_or_subprocess(self):
        with patch('short_video_pipeline.subprocess.Popen', side_effect=AssertionError('spawn')):
            self.assertIsNone(self.q.worker(dry_run=True))
            self.assertFalse(self.q.root.exists())
            job = self.q.enqueue(self.brief)
            before = {p: p.read_bytes() for p in self.q.root.rglob('*') if p.is_file()}
            self.assertEqual(job['id'], self.q.worker(dry_run=True)['id'])
            self.assertEqual(before, {p: p.read_bytes() for p in self.q.root.rglob('*') if p.is_file()})

    def test_failed_renderer_never_marks_rendered(self):
        job = self.q.enqueue(self.brief)
        with patch.object(self.q, '_probe_inputs'):
            with self.assertRaises(VideoError):
                self.q.render(job['id'], renderer=lambda *_: (_ for _ in ()).throw(RuntimeError('bad')))
        self.assertEqual('failed', self.q.status(job['id'])['status'])

    def test_success_and_cached_output(self):
        job = self.q.enqueue(self.brief)
        def render(_job, target):
            (target / 'video.mp4').write_bytes(b'output')
            (target / 'preview.png').write_bytes(b'preview')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            result = self.q.render(job['id'], renderer=render)
            self.assertEqual('rendered', result['status'])
            self.assertFalse(result['upload_eligible'])
            self.assertEqual(result, self.q.render(job['id'], renderer=lambda *_: self.fail('rerender')))
        self.assertTrue((self.q.root / 'jobs' / job['id'] / 'result.json').exists())

    def test_changed_snapshot_blocks_render(self):
        job = self.q.enqueue(self.brief)
        (self.q.root / 'jobs' / job['id'] / 'recording.mp4').write_bytes(b'changed')
        with self.assertRaises(VideoError): self.q.render(job['id'])
        self.assertEqual('blocked', self.q.status(job['id'])['status'])

    def test_interrupted_render_is_blocked(self):
        job = self.q.enqueue(self.brief)
        state = json.loads(self.q.state_path.read_text())
        state['jobs'][job['id']]['status'] = 'rendering'
        self.q.state_path.write_text(json.dumps(state))
        self.assertIsNone(self.q.worker())
        self.assertEqual('blocked', self.q.status(job['id'])['status'])

    def test_malformed_huge_duplicate_json(self):
        path = self.root / 'brief.json'
        for body in ['{"a":1,"a":2}', '{"a":NaN}', ' ' * 65537, '[]']:
            path.write_text(body)
            with self.assertRaises(VideoError): load_json(path)

class ProbeAndRuntimeTests(unittest.TestCase):
    setUp = ShortVideoTests.setUp
    def test_ffprobe_rejects_short_or_missing_stream(self):
        job = self.q.enqueue(self.brief)
        for result in [{'format': {'duration': '2'}, 'streams': [{'codec_type': 'video', 'width': 360, 'height': 640}]},
                       {'format': {'duration': '15'}, 'streams': []}]:
            with patch('short_video_pipeline.probe', return_value=result), self.assertRaises(VideoError):
                self.q._probe_inputs(job)

    def test_output_geometry_failure_stays_failed(self):
        job = self.q.enqueue(self.brief)
        def renderer(_job, target):
            (target / 'video.mp4').write_bytes(b'wrong geometry')
            (target / 'preview.png').write_bytes(b'preview')
        with patch.object(self.q, '_probe_inputs'), patch('short_video_pipeline.probe', return_value={
                'format': {'duration': '15'}, 'streams': [{'codec_type': 'video', 'codec_name': 'h264',
                    'width': 720, 'height': 1280, 'avg_frame_rate': '30/1'}]}):
            with self.assertRaises(VideoError): self.q.render(job['id'], renderer=renderer)
        self.assertEqual('failed', self.q.status(job['id'])['status'])

    def test_symlink_private_jobs_rejected(self):
        self.q.root.mkdir()
        (self.q.root / 'jobs').symlink_to(self.assets)
        with self.assertRaises(VideoError): self.q.enqueue(self.brief)
        self.assertEqual(['recording.mp4'], sorted(p.name for p in self.assets.iterdir()))

    def test_missing_result_cannot_claim_rendered(self):
        job = self.q.enqueue(self.brief)
        state = json.loads(self.q.state_path.read_text())
        state['jobs'][job['id']]['status'] = 'rendered'
        self.q.state_path.write_text(json.dumps(state))
        with self.assertRaises(VideoError): self.q.status()

    def test_test_only_cannot_enter_upload_state(self):
        job = self.q.enqueue(self.brief)
        state = json.loads(self.q.state_path.read_text())
        state['jobs'][job['id']]['status'] = 'uploaded_private'
        self.q.state_path.write_text(json.dumps(state))
        with self.assertRaises(VideoError): self.q.status()

    def test_template_and_optional_narration(self):
        (self.assets / 'voice.wav').write_bytes(b'test audio')
        job = self.q.enqueue(dict(self.brief, template='problem_solution', narration='voice.wav'))
        with patch('short_video_pipeline.probe', side_effect=[
            {'format': {'duration': '15'}, 'streams': [{'codec_type': 'video', 'width': 360, 'height': 640}]},
            {'format': {'duration': '15'}, 'streams': [{'codec_type': 'audio'}]},
        ]): self.q._probe_inputs(job)
        self.assertEqual({'recording', 'narration'}, set(job['assets']))

    def test_upload_handoff_rejects_test_and_unrendered_jobs(self):
        job = self.q.enqueue(self.brief)
        with self.assertRaises(VideoError): self.q.upload_candidate(job['id'])
        def renderer(_job, target):
            (target / 'video.mp4').write_bytes(b'video')
            (target / 'preview.png').write_bytes(b'preview')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            self.q.render(job['id'], renderer=renderer)
            with self.assertRaises(VideoError): self.q.upload_candidate(job['id'])
            prod = self.q.enqueue(dict(self.brief, test_only=False, idempotency_key='production'))
            with self.assertRaises(VideoError): self.q.upload_candidate(prod['id'])
            self.q.render(prod['id'], renderer=renderer)
            before = self.q.state_path.read_bytes()
            packet = self.q.upload_candidate(prod['id'])
            self.assertFalse(packet['test_only'])
            self.assertEqual(self.brief['topic_id'], packet['source']['topic_id'])
            self.assertEqual({'video.mp4', 'preview.png'}, set(packet['artifacts']))
            self.assertEqual(before, self.q.state_path.read_bytes())
            self.assertEqual('rendered', self.q.status(prod['id'])['status'])

    def test_renderer_change_during_render_fails_closed(self):
        job = self.q.enqueue(self.brief)
        def renderer(_job, target):
            (target / 'video.mp4').write_bytes(b'video')
            (target / 'preview.png').write_bytes(b'preview')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'), patch.object(self.q, '_render_key', side_effect=['before', 'after']):
            with self.assertRaises(VideoError): self.q.render(job['id'], renderer=renderer)
        self.assertEqual('failed', self.q.status(job['id'])['status'])

    def test_process_timeout_cleans_only_owned_group(self):
        import subprocess
        from short_video_pipeline import run_process
        proc = unittest.mock.Mock(pid=12345)
        proc.wait.side_effect = [subprocess.TimeoutExpired('bounded', 1), 0, 0]
        with patch('short_video_pipeline.subprocess.Popen', return_value=proc) as spawn, patch('short_video_pipeline.os.killpg') as kill:
            with self.assertRaises(VideoError): run_process(['local-command', 'literal;argument'], timeout=1)
            self.assertEqual(['local-command', 'literal;argument'], spawn.call_args.args[0])
            self.assertTrue(spawn.call_args.kwargs['start_new_session'])
            self.assertNotIn('shell', spawn.call_args.kwargs)
            self.assertTrue(all(call.args[0] == 12345 for call in kill.call_args_list))


if __name__ == '__main__':
    unittest.main()
