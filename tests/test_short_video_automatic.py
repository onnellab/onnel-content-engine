"""Unattended publication policy tests. All provider calls use injected fakes."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import test_short_video_youtube as fixtures
from short_video_policy import PolicyError, automatic_choices, load_policy, policy_digest
from short_video_runtime import readiness, worker


class AutomaticPublicationTests(unittest.TestCase):
    setUp = fixtures.UploadTests.setUp

    def renderable_job(self, **brief_changes):
        self.fake = fixtures.FakeTransport()
        self.fake.privacy = 'public'
        self.api = lambda: fixtures.YouTube(
            env=fixtures.ENV, send=self.fake, sleep=lambda _: None)
        brief = dict(self.brief, test_only=False, **brief_changes)
        job = self.q.enqueue(brief)

        def render(_job, target):
            (target / 'video.mp4').write_bytes(b'production-render')
            (target / 'preview.png').write_bytes(b'preview')
        return job, render
    def test_worker_renders_attests_and_publishes_without_human_approval(self):
        job, render = self.renderable_job()
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            result = worker(
                self.q, upload=True, execute=True, api_factory=self.api, renderer=render)
        self.assertEqual('published', result['status'])
        stored = self.q.status(job['id'])
        self.assertEqual('automatic_fail_closed', stored['approval']['mode'])
        self.assertEqual(policy_digest(load_policy()), stored['approval']['policy_hash'])
        self.assertTrue(stored['approval']['choices']['publish_approved'])
        self.assertEqual('public', stored['approval']['choices']['privacy'])
        self.assertEqual(1, len(self.fake.inserts()))

    def test_automatic_policy_blocks_narration_before_insert(self):
        (self.assets / 'voice.wav').write_bytes(b'audio')
        job, render = self.renderable_job(narration='voice.wav')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            result = worker(
                self.q, upload=True, execute=True, api_factory=self.api, renderer=render)
        self.assertEqual('blocked', result['status'])
        self.assertEqual('automatic_review_narration_not_allowed', result['error'])
        self.assertEqual([], self.fake.inserts())
        self.assertNotIn('approval', self.q.status(job['id']))

    def test_automatic_policy_blocks_hype_before_insert(self):
        job, render = self.renderable_job(hook='The best MP3 editor for every file')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            result = worker(
                self.q, upload=True, execute=True, api_factory=self.api, renderer=render)
        self.assertEqual('automatic_review_forbidden_marketing_claim', result['error'])
        self.assertEqual([], self.fake.inserts())
        self.assertNotIn('approval', self.q.status(job['id']))

    def test_automatic_policy_blocks_non_english_copy_before_insert(self):
        job, render = self.renderable_job(hook='MP3 태그를 정리해요')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            result = worker(
                self.q, upload=True, execute=True, api_factory=self.api, renderer=render)
        self.assertEqual('automatic_review_non_english_copy', result['error'])
        self.assertEqual([], self.fake.inserts())
        self.assertNotIn('approval', self.q.status(job['id']))

    def test_test_named_recording_cannot_auto_publish(self):
        (self.assets / 'test-recording.mp4').write_bytes(b'fixture')
        job, render = self.renderable_job(recording='test-recording.mp4')
        with patch.object(self.q, '_probe_inputs'), patch.object(self.q, '_verify_output'):
            result = worker(
                self.q, upload=True, execute=True, api_factory=self.api, renderer=render)
        self.assertEqual('automatic_review_test_recording_name', result['error'])
        self.assertEqual([], self.fake.inserts())

    def test_invalid_policy_blocks_before_new_render(self):
        job, render = self.renderable_job()
        bad = copy.deepcopy(load_policy())
        bad['mode'] = 'manual'
        with patch.object(self.q, '_probe_inputs') as probe:
            result = worker(
                self.q, upload=True, execute=True, api_factory=self.api,
                renderer=render, policy=bad)
        self.assertEqual('automatic_policy_invalid_or_missing', result['error'])
        self.assertEqual('queued', self.q.status(job['id'])['status'])
        probe.assert_not_called()
        self.assertEqual([], self.fake.inserts())
    def test_readiness_declares_no_human_review(self):
        status = readiness(self.q)
        self.assertFalse(status['human_review_required'])
        self.assertEqual('blocked', status['semantic_uncertainty_action'])
        self.assertTrue(status['automatic_publication']['fail_closed'])
        self.assertEqual('youtube_shorts', status['automatic_publication']['destination'])

    def test_policy_choices_are_fixed_for_current_real_screen_format(self):
        job, _render = self.renderable_job()
        choices = automatic_choices(job, load_policy())
        self.assertEqual(
            {
                'made_for_kids': False,
                'synthetic_media': False,
                'privacy': 'public',
                'publish_at': None,
                'publish_approved': True,
            },
            choices,
        )


if __name__ == '__main__':
    unittest.main()
