from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_short_video import ShortVideoTests
from short_video_pipeline import VideoError


class EnglishVideoPolicyTests(unittest.TestCase):
    setUp = ShortVideoTests.setUp

    def test_rejects_non_english_video_locales(self):
        for locale in ['ko', 'ja', 'zh-Hans', 'zh-Hant', 'de', 'fr', 'es', 'pt-BR']:
            with self.subTest(locale=locale), self.assertRaises(VideoError):
                self.q.validate(dict(self.brief, locale=locale))

    def test_natural_english_copy_uses_eighty_character_objective_bound(self):
        validated = self.q.validate(dict(self.brief, hook='x' * 80, cta='y' * 80))
        self.assertEqual('Fixture', validated['product']['app_name'])
        with self.assertRaises(VideoError):
            self.q.validate(dict(self.brief, hook='x' * 81))

    def test_released_product_snapshot_is_stored_and_hashed(self):
        job = self.q.enqueue(self.brief)
        self.assertEqual({'app_name': 'Fixture', 'platforms': ['ios', 'android']}, job['product'])
        self.assertEqual(2, json.loads(self.q.state_path.read_text())['schema_version'])
        registry = self.root / 'registry' / 'apps_registry.csv'
        registry.write_text(
            'app_id,app_name,status,platforms,content_eligible\n'
            'APP-0003,Renamed Fixture,released,ios|android,true\n'
        )
        self.assertEqual('Fixture', self.q.status(job['id'])['product']['app_name'])
        with self.assertRaises(VideoError):
            self.q.enqueue(self.brief)

    def test_tampered_product_snapshot_fails_closed(self):
        job = self.q.enqueue(self.brief)
        state = json.loads(self.q.state_path.read_text())
        state['jobs'][job['id']]['product']['app_name'] = 'Tampered'
        self.q.state_path.write_text(json.dumps(state))
        with self.assertRaises(VideoError):
            self.q.status(job['id'])

    def test_legacy_queue_schema_fails_closed(self):
        self.q.enqueue(self.brief)
        state = json.loads(self.q.state_path.read_text())
        state['schema_version'] = 1
        self.q.state_path.write_text(json.dumps(state))
        with self.assertRaises(VideoError):
            self.q.status()

    def test_unreleased_app_is_not_promotion_eligible(self):
        registry = self.root / 'registry' / 'apps_registry.csv'
        registry.write_text(
            'app_id,app_name,status,platforms,content_eligible\n'
            'APP-0003,Fixture,in_review,ios|android,true\n'
        )
        with self.assertRaises(VideoError):
            self.q.validate(self.brief)


if __name__ == '__main__':
    unittest.main()
