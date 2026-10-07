import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_pipeline import ROOT, VideoError, product_snapshot
from short_video_recorder import RecordingError, require_promotable_app


class VideoProductEligibilityTests(unittest.TestCase):
    def setUp(self):
        with (ROOT / 'data/apps_registry.csv').open(encoding='utf-8') as handle:
            self.apps = {row['app_id']: row for row in csv.DictReader(handle)}
        with (ROOT / 'data/store_versions.csv').open(encoding='utf-8') as handle:
            self.public_stores = {
                (row['app_id'], row['platform'], row['store_url'])
                for row in csv.DictReader(handle)
                if row['version'].strip() and row['status'] in {'new', 'updated', 'unchanged'}
            }

    def expected_public_platforms(self, app_id):
        app = self.apps[app_id]
        return [
            platform for platform, url_field in [('ios', 'app_store_url'), ('android', 'play_store_url')]
            if platform in app['platforms'].split('|')
            and (app_id, platform, app[url_field]) in self.public_stores
        ]

    def test_real_registry_restricts_new_apps_to_public_platform(self):
        for app_id in ['APP-0007', 'APP-0008']:
            with self.subTest(app=app_id):
                platforms = self.expected_public_platforms(app_id)
                self.assertTrue(platforms)
                self.assertEqual(platforms, product_snapshot(self.apps[app_id])['platforms'])

    def test_recorder_blocks_unreleased_platform_before_device_work(self):
        blocked = []
        for app_id in ['APP-0007', 'APP-0008']:
            for platform, recorder in [('ios', 'ios_simulator'), ('android', 'android_emulator')]:
                if platform in self.expected_public_platforms(app_id):
                    continue
                blocked.append((app_id, platform))
                with self.subTest(app=app_id, platform=platform), self.assertRaisesRegex(
                    RecordingError, 'recording_platform_not_public'
                ):
                    require_promotable_app({'app_id': app_id, 'production_eligible': True}, recorder)
        self.assertTrue(blocked, 'Current store data must exercise the non-public platform guard')

    def test_recorder_accepts_verified_platform(self):
        for app_id in ['APP-0007', 'APP-0008']:
            for platform in self.expected_public_platforms(app_id):
                recorder = {'ios': 'ios_simulator', 'android': 'android_emulator'}[platform]
                # This is the public-store guard in isolation, not a registered capture
                # scenario. Real registrations remain independently quarantined.
                with self.subTest(app=app_id, platform=platform):
                    self.assertEqual(app_id, require_promotable_app(
                        {'app_id': app_id, 'production_eligible': True}, recorder)['app_id'])

    def test_missing_or_nonmatching_store_evidence_fails_closed(self):
        app = {'app_id': 'APP-0001', 'app_name': 'Fixture', 'status': 'released',
               'content_eligible': 'true', 'platforms': 'android',
               'play_store_url': 'https://play.google.com/store/apps/details?id=fixture'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'store_versions.csv'
            with self.assertRaisesRegex(VideoError, 'public store'):
                product_snapshot(app, path)
            for row in [
                'APP-0001,android,https://play.google.com/store/apps/details?id=fixture,,new',
                'APP-0001,android,https://play.google.com/store/apps/details?id=fixture,1.0,manual_check',
                'APP-0002,android,https://play.google.com/store/apps/details?id=fixture,1.0,new',
                'APP-0001,ios,https://play.google.com/store/apps/details?id=fixture,1.0,new',
                'APP-0001,android,https://play.google.com/store/apps/details?id=other,1.0,new',
            ]:
                path.write_text('app_id,platform,store_url,version,status\n' + row + '\n')
                with self.subTest(row=row), self.assertRaisesRegex(VideoError, 'public store'):
                    product_snapshot(app, path)


if __name__ == '__main__':
    unittest.main()
