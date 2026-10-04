import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_pipeline import ROOT, VideoError, product_snapshot
from short_video_recorder import RecordingError, require_promotable_app


class VideoProductEligibilityTests(unittest.TestCase):
    def test_real_registry_restricts_new_apps_to_public_platform(self):
        with (ROOT / 'data/apps_registry.csv').open(encoding='utf-8') as handle:
            apps = {row['app_id']: row for row in csv.DictReader(handle)}
        for app_id, platforms in [('APP-0007', ['android']), ('APP-0008', ['ios'])]:
            with self.subTest(app=app_id):
                self.assertEqual(platforms, product_snapshot(apps[app_id])['platforms'])

    def test_recorder_blocks_unreleased_platform_before_device_work(self):
        for app_id, platform in [('APP-0007', 'ios_simulator'), ('APP-0008', 'android_emulator')]:
            with self.subTest(app=app_id), self.assertRaisesRegex(RecordingError, 'recording_platform_not_public'):
                require_promotable_app({'app_id': app_id, 'production_eligible': True}, platform)

    def test_recorder_accepts_verified_platform(self):
        for app_id, platform in [('APP-0007', 'android_emulator'), ('APP-0008', 'ios_simulator')]:
            # This is the public-store guard in isolation, not a registered capture
            # scenario. Real registrations remain independently quarantined.
            self.assertEqual(app_id, require_promotable_app(
                {'app_id': app_id, 'production_eligible': True}, platform)['app_id'])

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
