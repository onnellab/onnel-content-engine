"""Reviewer regressions use only injected fake HTTP transports; no network."""
from datetime import timedelta
import json
import unittest
from unittest.mock import patch
import test_short_video_youtube as fixtures
from short_video_runtime import worker
from short_video_youtube import YouTube, metadata


class ReviewedVideoRegressions(unittest.TestCase):
    setUp = fixtures.UploadTests.setUp
    prepare = fixtures.UploadTests.prepare

    def test_korean_title_limit_is_characters_not_utf8_bytes(self):
        jid = self.prepare()
        job = self.q.status(jid)
        job['brief']['title'] = '가' * 100
        result = metadata(job, fixtures.CHOICES, self.now)
        self.assertEqual('가' * 100, result['snippet']['title'])

    def test_ambiguous_channel_context_never_inserts(self):
        jid = self.prepare()
        original = self.fake
        def send(method, url, headers, body):
            if '/channels?' in url:
                return 200, {}, json.dumps({'items': [{'id': fixtures.CHANNEL}, {'id': 'UC' + 'b' * 22}]}).encode()
            return original(method, url, headers, body)
        self.u.api_factory = lambda: YouTube(env=fixtures.ENV, send=send, sleep=lambda _: None)
        self.assertEqual('foreign_channel', self.u.run(jid, execute=True)['error'])
        self.assertEqual([], self.fake.inserts())

    def test_worker_reconciles_schedule_when_due(self):
        publish = '2026-09-22T00:00:00Z'
        jid = self.prepare(dict(fixtures.CHOICES, publish_at=publish, publish_approved=True))
        self.fake.publish = publish
        self.assertEqual('scheduled', self.u.run(jid, execute=True)['status'])
        self.assertEqual('idle', worker(self.q, upload=True, execute=True, api_factory=self.api)['status'])
        self.q.clock = lambda: self.now + timedelta(days=2)
        self.fake.privacy = 'public'
        self.assertEqual('published', worker(self.q, upload=True, execute=True, api_factory=self.api)['status'])
        self.assertEqual('published', self.q.status(jid)['status'])
        self.assertEqual(1, len(self.fake.inserts()))

    def test_provider_fractional_timestamp_matches_approved_instant(self):
        publish = '2026-09-22T00:00:00Z'
        jid = self.prepare(dict(fixtures.CHOICES, publish_at=publish, publish_approved=True))
        self.fake.publish = '2026-09-22T00:00:00.000+00:00'
        result = self.u.run(jid, execute=True)
        self.assertEqual('scheduled', result['status'])
        self.assertEqual(publish, result['upload']['observed']['publish_at'])

    def test_time_budget_preserves_session_without_sending_media(self):
        jid = self.prepare()
        with patch('short_video_youtube.time.monotonic', side_effect=[0, 901]):
            result = self.u.run(jid, execute=True)
        self.assertEqual('reconcile_required', result['status'])
        self.assertEqual('transfer_time_budget_exhausted', result['error'])
        self.assertEqual([], self.fake.chunks())
        self.assertEqual('uploaded_private', self.u.run(jid, execute=True, reconcile=True)['status'])
        self.assertEqual(1, len(self.fake.inserts()))


if __name__ == '__main__':
    unittest.main()
