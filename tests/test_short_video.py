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


if __name__ == '__main__':
    unittest.main()
