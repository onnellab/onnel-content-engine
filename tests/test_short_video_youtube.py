"""Offline provider/state contract tests. No credentials, browser, or network."""
import copy
import json
import os
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import test_short_video as fixtures
from short_video_pipeline import atomic_json, file_hash, VideoError
from short_video_youtube import (YouTube, Uploader, UploadError, session_url, metadata,
                                 CHUNK, check_config, NoRedirect)
from short_video_runtime import worker, enqueue_dir, graceful_signals, readiness

CHANNEL = 'UC' + 'a' * 22
VIDEO = 'abcdefghijk'
URL = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&upload_id=SECRET_SESSION'
ENV = dict(YOUTUBE_CLIENT_ID='SECRET_CLIENT', YOUTUBE_CLIENT_SECRET='SECRET_SECRET',
           YOUTUBE_REFRESH_TOKEN='SECRET_REFRESH', YOUTUBE_CHANNEL_ID=CHANNEL)
CHOICES = dict(made_for_kids=False, synthetic_media=False, privacy='private', publish_at=None, publish_approved=False)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.offset = 0
        self.complete = False
        self.lose_ack = False
        self.channel = CHANNEL
        self.chunk_error = None
        self.expired = False
        self.privacy = 'private'
        self.processing = 'succeeded'
        self.upload_status = 'processed'
        self.publish = None
        self.lost_initiation = False
        self.foreign_video = False
        self.before_chunk = None

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        if url.endswith('/token'):
            return 200, {}, b'{"access_token":"SECRET_ACCESS"}'
        if '/channels?' in url:
            return 200, {}, json.dumps({'items': [{'id': self.channel}]}).encode()
        if '/videos?' in url and method == 'GET':
            status = {'privacyStatus': self.privacy, 'uploadStatus': self.upload_status}
            if self.publish:
                status['publishAt'] = self.publish
            item = {'id': VIDEO, 'snippet': {'channelId': 'foreign' if self.foreign_video else CHANNEL},
                    'status': status, 'processingDetails': {'processingStatus': self.processing}}
            return 200, {}, json.dumps({'items': [item]}).encode()
        if method == 'POST':
            if self.lost_initiation:
                raise OSError('SECRET_SESSION')
            return 200, {'Location': URL}, b''
        if self.expired:
            return 410, {}, b'SECRET_SESSION'
        if headers['Content-Range'].startswith('bytes */'):
            if self.complete:
                return 200, {}, json.dumps({'id': VIDEO}).encode()
            return 308, {'Range': f'bytes=0-{self.offset - 1}'} if self.offset else {}, b''
        if self.before_chunk:
            self.before_chunk()
        if self.chunk_error:
            return self.chunk_error, {}, b'SECRET_BODY'
        self.offset += len(body)
        total = int(headers['Content-Range'].split('/')[-1])
        if self.offset == total:
            self.complete = True
            if self.lose_ack:
                self.lose_ack = False
                raise OSError('SECRET_ACCESS')
            return 200, {}, json.dumps({'id': VIDEO}).encode()
        return 308, {'Range': f'bytes=0-{self.offset - 1}'}, b''

    def inserts(self):
        return [c for c in self.calls if c[0] == 'POST' and '/upload/' in c[1]]

    def chunks(self):
        return [c for c in self.calls if c[0] == 'PUT' and c[3]]


class UploadTests(unittest.TestCase):
    setUp = fixtures.ShortVideoTests.setUp

    def prepare(self, choices=None, size=20):
        self.fake = FakeTransport()
        self.api = lambda: YouTube(env=ENV, send=self.fake, sleep=lambda _: None)
        self.u = Uploader(self.q, self.api)
        job = self.q.enqueue(dict(self.brief, test_only=False))
        def render(_job, target):
            (target / 'video.mp4').write_bytes(b'v' * size)
            (target / 'preview.png').write_bytes(b'preview')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            self.q.render(job['id'], renderer=render)
            self.u.approve(job['id'], choices or CHOICES, execute=True)
        self.job_id = job['id']
        return job['id']

    def test_success_duplicate_and_private_files(self):
        jid = self.prepare(size=CHUNK + 4)
        def before():
            path = self.q.root / 'jobs' / jid / 'youtube-session.json'
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertEqual(URL, json.loads(path.read_text())['url'])
            self.assertEqual('sending', self.q.status(jid)['upload']['phase'])
        self.fake.before_chunk = before
        result = self.u.run(jid, execute=True)
        self.assertEqual('uploaded_private', result['status'])
        self.assertEqual(VIDEO, result['upload']['video_id'])
        self.assertEqual(2, len(self.fake.chunks()))
        self.u.run(jid, execute=True)
        self.assertEqual(1, len(self.fake.inserts()))
        text = json.dumps(self.q.status())
        for secret in ['SECRET', URL, str(self.q.root)]:
            self.assertNotIn(secret, text)

    def test_missing_credentials_no_upload(self):
        jid = self.prepare()
        self.u.api_factory = lambda: YouTube(env={})
        self.assertEqual('missing_youtube_credentials', self.u.run(jid, execute=True)['error'])
        self.assertEqual([], self.fake.calls)

    def test_test_only_and_incomplete_zero_network(self):
        for testing in [True, False]:
            job = self.q.enqueue(dict(self.brief, test_only=testing, idempotency_key=str(testing)))
            factory = Mock(side_effect=AssertionError('network'))
            result = Uploader(self.q, factory).run(job['id'], execute=True)
            self.assertEqual('blocked', result['status'])
            factory.assert_not_called()

    def test_changed_mp4_and_approval_zero_network(self):
        jid = self.prepare()
        (self.q.root / 'jobs' / jid / 'video.mp4').write_bytes(b'changed')
        self.assertEqual('render_integrity', self.u.run(jid, execute=True)['error'])
        self.assertEqual([], self.fake.calls)

    def test_missing_approval_zero_network(self):
        jid = self.prepare()
        state = self.q._read()
        del state['jobs'][jid]['approval']
        atomic_json(self.q.state_path, state)
        self.assertEqual('upload_approval_required', self.u.run(jid, execute=True)['error'])
        self.assertEqual([], self.fake.calls)

    def test_foreign_channel_zero_inserts(self):
        jid = self.prepare()
        self.fake.channel = 'UC' + 'b' * 22
        self.assertEqual('foreign_channel', self.u.run(jid, execute=True)['error'])
        self.assertEqual([], self.fake.inserts())

    def test_public_and_schedule_require_separate_approval(self):
        jid = self.prepare()
        job = self.q.status(jid)
        for changes in [{'privacy': 'public'}, {'privacy': 'unlisted'}, {'publish_at': '2027-01-01T00:00:00Z'},
                        {'publish_at': '2020-01-01T00:00:00Z', 'publish_approved': True},
                        {'made_for_kids': None}, {'synthetic_media': 0}]:
            with self.subTest(changes=changes), self.assertRaises(UploadError):
                metadata(job, dict(CHOICES, **changes), self.now)
        self.assertEqual([], self.fake.calls)

    def test_schedule_stales_before_execution(self):
        jid = self.prepare(dict(CHOICES, publish_at='2026-09-22T00:00:00Z', publish_approved=True))
        from datetime import timedelta
        self.q.clock = lambda: self.now + timedelta(days=2)
        self.assertEqual('stale_or_nonprivate_schedule', self.u.run(jid, execute=True)['error'])
        self.assertEqual([], self.fake.calls)

    def test_metadata_utf8_limits(self):
        jid = self.prepare()
        job = copy.deepcopy(self.q.status(jid))
        for key, value in [('title', '가' * 101), ('description', '가' * 1667), ('title', '<bad>')]:
            with self.subTest(key=key), self.assertRaises(UploadError):
                metadata(dict(job, brief=dict(job['brief'], **{key: value})), CHOICES, self.now)

    def test_final_ack_lost_probes_same_session(self):
        jid = self.prepare()
        self.fake.lose_ack = True
        self.assertEqual('uploaded_private', self.u.run(jid, execute=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))
        self.assertEqual(1, len(self.fake.chunks()))

    def test_restart_after_308_resumes_offset(self):
        jid = self.prepare(size=CHUNK + 8)
        original = self.fake.__call__
        def send(method, url, headers, body):
            if method == 'PUT' and body and self.fake.offset >= CHUNK:
                raise OSError('connection')
            return original(method, url, headers, body)
        self.u.api_factory = lambda: YouTube(env=ENV, send=send, sleep=lambda _: None)
        self.assertEqual('reconcile_required', self.u.run(jid, execute=True)['status'])
        self.u.api_factory = self.api
        self.assertEqual('uploaded_private', self.u.run(jid, execute=True, reconcile=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))
        self.assertTrue(self.fake.chunks()[-1][2]['Content-Range'].startswith(f'bytes {CHUNK}-'))

    def test_expired_or_missing_uncertain_session_never_inserts(self):
        jid = self.prepare()
        self.fake.chunk_error = 403
        self.u.run(jid, execute=True)
        self.fake.expired = True
        self.assertEqual('reconcile_required', self.u.run(jid, execute=True, reconcile=True)['status'])
        (self.q.root / 'jobs' / jid / 'youtube-session.json').unlink()
        self.assertEqual('manual_reconcile_required', self.u.run(jid, execute=True)['error'])
        self.assertEqual(1, len(self.fake.inserts()))
        with self.assertRaises(VideoError):
            self.q.render(jid)

    def test_initiation_ack_lost_does_not_repeat(self):
        jid = self.prepare()
        self.fake.lost_initiation = True
        self.u.run(jid, execute=True)
        self.u.run(jid, execute=True)
        self.assertEqual(1, len(self.fake.inserts()))

    def test_state_write_after_acceptance_lost_recovers_session(self):
        jid = self.prepare()
        original = atomic_json
        failed = False
        def write(path, value):
            nonlocal failed
            if path == self.q.state_path and value['jobs'][jid].get('upload', {}).get('video_id') and not failed:
                failed = True
                raise OSError('disk')
            original(path, value)
        with patch('short_video_youtube.atomic_json', side_effect=write):
            self.assertEqual('reconcile_required', self.u.run(jid, execute=True)['status'])
        self.assertEqual('uploaded_private', self.u.run(jid, execute=True, reconcile=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))

    def test_process_dies_before_id_persist_probes_completed_session(self):
        jid = self.prepare()
        original = atomic_json
        def write(path, value):
            if path == self.q.state_path and value['jobs'][jid].get('upload', {}).get('video_id'):
                raise SystemExit(99)  # Simulates process loss: no exception recovery write.
            original(path, value)
        with patch('short_video_youtube.atomic_json', side_effect=write), self.assertRaises(SystemExit):
            self.u.run(jid, execute=True)
        self.assertNotIn('video_id', self.q.status(jid)['upload'])
        self.assertEqual('uploaded_private', self.u.run(jid, execute=True, reconcile=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))
        self.assertEqual(1, len(self.fake.chunks()))

    def test_http_errors_bounded_sanitized(self):
        for code, expected in [(401, 'auth_required'), (403, 'permission_or_quota_denied'),
                               (429, 'rate_limited'), (500, 'provider_unavailable')]:
            calls = []
            def send(*args):
                calls.append(args)
                return code, {}, b'SECRET_ACCESS /private/path'
            api = YouTube(env=ENV, send=send, sleep=lambda _: None)
            with self.subTest(code=code), self.assertRaisesRegex(UploadError, expected):
                api.request('GET', 'https://www.googleapis.com/youtube/v3/videos', retry=True)
            self.assertEqual(3 if code in (429, 500) else 1, len(calls))

    def test_url_and_redirect_rejection(self):
        for url in [URL.replace('https:', 'http:'), URL.replace('www.googleapis.com', 'evil.test'),
                    URL.replace('www.googleapis.com', 'www.googleapis.com.evil.test'),
                    URL.replace('/upload/', '/wrong/'), URL + '#fragment',
                    URL.replace('www.googleapis.com', 'user@www.googleapis.com'),
                    URL.replace('www.googleapis.com', 'www.googleapis.com:443')]:
            with self.subTest(url=url), self.assertRaises(UploadError):
                session_url(url)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test'))
        for code in [301, 302, 307, 308]:
            api = YouTube(env=ENV, send=lambda *_: (code, {'Location': 'https://evil.test'}, b''))
            with self.assertRaisesRegex(UploadError, 'redirect_rejected'):
                api.request('PUT', URL)

    def test_provider_semantics_and_no_reupload(self):
        jid = self.prepare(dict(CHOICES, privacy='public', publish_approved=True))
        for privacy, processing, status, expected in [
            ('private', 'processing', 'uploaded', 'processing'),
            ('private', 'failed', 'rejected', 'rejected'),
            ('private', 'succeeded', 'processed', 'forced_private'),
            ('public', 'succeeded', 'processed', 'published'),
            ('unlisted', 'succeeded', 'processed', 'uploaded_unlisted')]:
            self.fake.privacy, self.fake.processing, self.fake.upload_status = privacy, processing, status
            self.assertEqual(expected, self.u.run(jid, execute=True, reconcile=bool(self.fake.inserts()))['status'])
        self.assertEqual(1, len(self.fake.inserts()))
        self.fake.foreign_video = True
        self.assertEqual('video_missing_or_foreign_channel', self.u.run(jid, execute=True)['error'])

    def test_confirmed_schedule_and_past_schedule_observation(self):
        publish = '2026-09-22T00:00:00Z'
        jid = self.prepare(dict(CHOICES, publish_at=publish, publish_approved=True))
        self.fake.publish = publish
        self.assertEqual('scheduled', self.u.run(jid, execute=True)['status'])
        from datetime import timedelta
        self.q.clock = lambda: self.now + timedelta(days=2)
        self.fake.privacy = 'public'
        self.assertEqual('published', self.u.run(jid, execute=True, reconcile=True)['status'])

    def test_dry_runs_no_mutation_network_or_secret_loading(self):
        jid = self.prepare()
        before = {p: p.read_bytes() for p in self.q.root.rglob('*') if p.is_file()}
        factory = Mock(side_effect=AssertionError('secret load'))
        u = Uploader(self.q, factory)
        u.approve(jid, {}, execute=False)
        u.run(jid)
        u.run(jid, reconcile=True)
        worker(self.q, upload=True, execute=True, dry_run=True, api_factory=factory)
        self.assertEqual(before, {p: p.read_bytes() for p in self.q.root.rglob('*') if p.is_file()})
        factory.assert_not_called()
        self.assertEqual([], self.fake.calls)

    def test_worker_config_stop_and_lock(self):
        jid = self.prepare()
        with patch.dict(os.environ, {}, clear=True):
            result = worker(self.q, upload=True, execute=True)
        self.assertEqual('missing_youtube_credentials', result['error'])
        self.assertEqual('rendered', self.q.status(jid)['status'])
        with self.q.lock(), self.assertRaises(VideoError):
            self.u.run(jid, execute=True)
        self.assertEqual('uploaded_private', worker(self.q, upload=True, execute=True, api_factory=self.api)['status'])

    def test_inbox_idempotent_and_dry(self):
        inbox = self.root / 'inbox'
        inbox.mkdir()
        (inbox / 'one.json').write_text(json.dumps(self.brief))
        self.assertEqual(1, enqueue_dir(self.q, inbox, dry_run=True)['brief_count'])
        self.assertFalse(self.q.root.exists())
        enqueue_dir(self.q, inbox)
        enqueue_dir(self.q, inbox)
        self.assertEqual(1, len(self.q.status()))

    def test_signal_raises_and_restores_handler(self):
        previous = signal.getsignal(signal.SIGTERM)
        with self.assertRaises(KeyboardInterrupt), graceful_signals():
            signal.raise_signal(signal.SIGTERM)
        self.assertEqual(previous, signal.getsignal(signal.SIGTERM))

    def test_short_narration_allowed_long_rejected(self):
        (self.assets / 'voice.wav').write_bytes(b'audio')
        job = self.q.enqueue(dict(self.brief, narration='voice.wav'))
        recording = {'format': {'duration': '15'}, 'streams': [{'codec_type': 'video', 'width': 360, 'height': 640}]}
        for seconds in [2, 15, 16]:
            audio = {'format': {'duration': str(seconds)}, 'streams': [{'codec_type': 'audio'}]}
            with patch('short_video_pipeline.probe', side_effect=[recording, audio]):
                if seconds <= 15:
                    self.q._probe_inputs(job)
                else:
                    with self.assertRaises(VideoError): self.q._probe_inputs(job)

    def test_retry_after_is_bounded(self):
        sleeps = []
        api = YouTube(env=ENV, sleep=sleeps.append)
        api.pause({'retry-after': '3'})
        self.assertEqual([3], sleeps)
        for value in ['300', 'tomorrow']:
            with self.assertRaisesRegex(UploadError, 'retry_later'):
                api.pause({'retry-after': value})

    def test_fixed_config_can_retry_same_approved_job(self):
        jid = self.prepare()
        self.u.api_factory = lambda: YouTube(env={})
        self.assertEqual('blocked', self.u.run(jid, execute=True)['status'])
        self.u.api_factory = self.api
        self.assertEqual('uploaded_private', self.u.run(jid, execute=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))

    def test_worker_interrupted_upload_resumes_not_rendered(self):
        jid = self.prepare()
        self.fake.chunk_error = 403
        self.u.run(jid, execute=True)
        self.fake.chunk_error = None
        render = Mock(side_effect=AssertionError('must not render'))
        self.assertEqual('uploaded_private', worker(self.q, upload=True, execute=True,
                         api_factory=self.api, renderer=render)['status'])
        render.assert_not_called()
        self.assertEqual(1, len(self.fake.inserts()))

    def test_lost_ack_with_past_schedule_can_be_observed(self):
        from datetime import timedelta
        jid = self.prepare(dict(CHOICES, publish_at='2026-09-22T00:00:00Z', publish_approved=True))
        self.fake.chunk_error = 403
        self.u.run(jid, execute=True)
        self.fake.complete = True  # Provider accepted bytes before a lost final ACK.
        self.fake.privacy = 'public'
        self.q.clock = lambda: self.now + timedelta(days=2)
        self.assertEqual('published', self.u.run(jid, execute=True, reconcile=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))

    def test_sigterm_cleans_owned_child_group(self):
        from short_video_pipeline import run_process
        process = Mock(pid=12345)
        process.wait.side_effect = [KeyboardInterrupt(), 0, 0]
        with patch('short_video_pipeline.subprocess.Popen', return_value=process), patch('short_video_pipeline.os.killpg') as kill:
            with self.assertRaises(KeyboardInterrupt):
                run_process(['local-child'])
            self.assertEqual([(12345, signal.SIGTERM), (12345, signal.SIGKILL)],
                             [c.args for c in kill.call_args_list])

    def test_cli_dry_run_overrides_execute(self):
        import short_video
        from io import StringIO
        with patch.object(sys, 'argv', ['short_video', '--asset-root', str(self.assets),
                '--state-root', str(self.q.root), 'upload', 'unknown', '--execute', '--dry-run']), \
                patch('short_video.YouTube', side_effect=AssertionError('secrets')), \
                patch('sys.stdout', new_callable=StringIO) as output:
            self.assertEqual(0, short_video.main())
            self.assertTrue(json.loads(output.getvalue())['dry_run'])
        self.assertFalse(self.q.root.exists())

    def test_nested_render_key_no_basename_collision(self):
        job = self.q.enqueue(self.brief)
        fake_root = self.root / 'fake_repo'
        (fake_root / 'video/src/a').mkdir(parents=True)
        (fake_root / 'video/src/b').mkdir()
        first = fake_root / 'video/src/a/same.ts'
        second = fake_root / 'video/src/b/same.ts'
        first.write_text('first')
        second.write_text('second')
        # Patch __file__ too so all manifest entries belong to the fake repository.
        with patch('short_video_pipeline.ROOT', fake_root), patch('short_video_pipeline.__file__', str(fake_root / 'pipeline.py')):
            before = self.q._render_key(job)
            first.write_text('changed')
            after = self.q._render_key(job)
            self.assertNotEqual(before, after)
            second.write_text('changed too')
            self.assertNotEqual(after, self.q._render_key(job))


if __name__ == '__main__':
    unittest.main()
