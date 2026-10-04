import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from marketing_measurement import (CHANNELS, MeasurementError, campaign_token,
                                   metric_rates, report, tracking_link)

START = '2026-10-01T00:00:00+00:00'
AS_OF = '2026-10-15T00:00:00+00:00'
KEY = 'TOPIC-0001::x::en::x'


class MarketingMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        (self.root / 'generated/social').mkdir(parents=True)
        (self.root / 'data/apps_registry.csv').write_text(
            'app_id,app_name,status,content_eligible,platforms,app_store_url,play_store_url\n'
            'APP-0001,Fixture,released,true,android,,https://play.google.com/store/apps/details?id=fixture\n')
        (self.root / 'data/store_versions.csv').write_text(
            'app_id,platform,store_url,status,version\nAPP-0001,android,https://play.google.com/store/apps/details?id=fixture,new,1.0\n')
        (self.root / 'data/topics.csv').write_text(
            'id,related_apps,published_at\nTOPIC-0001,Fixture,2026-10-02T00:00:00+00:00\n')
        self.post = dict(topic_id='TOPIC-0001', platform='x', language='en', template_id='x',
                         status='failed', error='old failure', error_type='transient', retry_count=2,
                         last_attempt_at='2026-10-02T00:00:00+00:00',
                         destination_urls='https://play.google.com/store/apps/details?id=fixture&utm_campaign=test&utm_source=x')
        self.write_json('generated/social/manifest.json', {'posts': [self.post]})
        self.write_json('data/manual_publish_state.json', {'done': {KEY: {'posted_url': 'https://x.com/fixture/status/123',
            'published_at': '2026-10-03T00:00:00+00:00'}}})
        self.config = dict(schema_version=1, window_days=28, baseline_weight=1, channels=sorted(CHANNELS),
                           metric_samples=[], extra_publications=[], notes=[])

    def write_json(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def sample(self):
        evidence = self.root / 'export.csv'
        evidence.write_text('aggregate,example\n')
        return dict(sample_id='sample-1', manual_key=KEY, app_id='APP-0001', source='google_play_export',
                    period_start=START, period_end=AS_OF,
                    dimensions={'store_platform': 'android', 'campaign': 'test'},
                    metrics={'listing_visitors': 100, 'listing_button_click_users': 20, 'listing_acquisitions': None},
                    evidence_path='export.csv', evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())

    def test_receipts_join_over_old_failure_without_mutation(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = report(self.root, self.config, START, AS_OF)
        item = result['records'][0]
        self.assertTrue(item['publication_recorded'])
        self.assertTrue(item['publication_permalink_recorded'])
        self.assertTrue(item['historical_error_present'])
        self.assertEqual(2, item['retry_count_snapshot'])
        self.assertIsNone(item['metrics'])
        self.assertEqual(1, item['week'])
        self.assertEqual(1, result['baseline'][0]['weight'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_duplicate_post_is_not_double_counted_and_conflicts_fail(self):
        self.write_json('generated/social/manifest.json', {'posts': [self.post, self.post]})
        result = report(self.root, self.config, START, AS_OF)
        self.assertEqual(1, result['summary']['publication_recorded'])
        self.assertEqual(1, result['summary']['duplicate_input_rows_ignored'])
        changed = dict(self.post, retry_count=3)
        self.write_json('generated/social/manifest.json', {'posts': [self.post, changed]})
        with self.assertRaisesRegex(MeasurementError, 'Conflicting duplicate'):
            report(self.root, self.config, START, AS_OF)

    def test_unknown_publication_time_is_not_bucketed_by_receipt_or_old_due_date(self):
        self.write_json('data/manual_publish_state.json', {'done': {KEY: {
            'posted_url': 'https://x.com/fixture/status/123', 'published_at': '',
            'published_at_precision': 'unknown', 'marked_at': '2026-10-04T07:00:00Z',
            'observed_at': '2026-10-04T06:33:36Z', 'observed_at_precision': 'approximate'}}})
        item = report(self.root, self.config, START, AS_OF)['records'][0]
        self.assertTrue(item['publication_recorded'])
        self.assertIsNone(item['event_at'])
        self.assertIsNone(item['week'])
        self.assertFalse(item['in_observed_window'])
        self.assertEqual('2026-10-04T06:33:36Z', item['observed_at'])
        self.assertEqual('approximate', item['observed_at_precision'])

    def test_generic_profile_receipt_preserves_dedupe_without_claiming_permalink(self):
        self.write_json('data/manual_publish_state.json', {'done': {KEY: {'posted_url': 'https://x.com/fixture'}}})
        item = report(self.root, self.config, START, AS_OF)['records'][0]
        self.assertTrue(item['publication_recorded'])
        self.assertFalse(item['publication_permalink_recorded'])

    def test_week_boundaries_and_future_are_not_observed(self):
        self.write_json('data/manual_publish_state.json', {'done': {KEY: {'posted_url': 'https://x.com/fixture/status/123',
            'published_at': '2026-10-08T00:00:00+00:00'}}})
        self.assertEqual(2, report(self.root, self.config, START, AS_OF)['records'][0]['week'])
        self.assertIsNone(report(self.root, self.config, START, '2026-10-07T00:00:00+00:00')['records'][0]['week'])

    def test_play_ctr_is_not_an_install_count(self):
        metrics = {'listing_visitors': 100, 'listing_button_click_users': 20, 'listing_acquisitions': None}
        self.assertEqual({'listing_click_through_rate': .2}, metric_rates('google_play_export', metrics))
        self.assertIsNone(metrics['listing_acquisitions'])

    def test_apple_conversion_uses_unique_impressions_and_preorders(self):
        self.assertEqual({'app_store_conversion_rate': .12}, metric_rates('app_store_connect_export',
            dict(total_downloads=10, preorders=2, unique_impressions=100, unique_product_page_views=20)))
        self.assertIsNone(metric_rates('app_store_connect_export', dict(total_downloads=10, unique_impressions=100))['app_store_conversion_rate'])

    def test_missing_zero_and_invalid_metrics(self):
        self.assertIsNone(metric_rates('channel_export', {})['link_click_rate'])
        self.assertIsNone(metric_rates('channel_export', dict(impressions=0, link_clicks=0))['link_click_rate'])
        self.assertEqual(0, metric_rates('channel_export', dict(impressions=10, link_clicks=0))['link_click_rate'])
        for value in [-1, True, float('nan'), '13']:
            with self.subTest(value=value), self.assertRaises(MeasurementError):
                metric_rates('channel_export', dict(impressions=value))
        with self.assertRaises(MeasurementError):
            metric_rates('google_play_export', {'installs': 13})

    def test_metric_samples_require_matching_attribution_and_export_bytes(self):
        sample = self.sample()
        self.config['metric_samples'] = [sample, sample]
        result = report(self.root, self.config, START, AS_OF)
        self.assertEqual(1, result['summary']['metric_samples'])
        self.assertEqual(.2, result['records'][0]['metrics'][0]['rates']['listing_click_through_rate'])
        bad = copy.deepcopy(sample)
        bad['dimensions']['campaign'] = 'other'
        self.config['metric_samples'] = [bad]
        with self.assertRaisesRegex(MeasurementError, 'matching published campaign'):
            report(self.root, self.config, START, AS_OF)
        self.config['metric_samples'] = [sample]
        (self.root / 'export.csv').write_text('changed')
        with self.assertRaisesRegex(MeasurementError, 'hash mismatch'):
            report(self.root, self.config, START, AS_OF)

    def test_overlapping_samples_and_unknown_app_fail(self):
        first = self.sample()
        self.config['metric_samples'] = [first, dict(first, sample_id='sample-2')]
        with self.assertRaisesRegex(MeasurementError, 'Overlapping'):
            report(self.root, self.config, START, AS_OF)
        self.config['metric_samples'] = [dict(first, app_id='APP-9999')]
        with self.assertRaisesRegex(MeasurementError, 'known publication and app'):
            report(self.root, self.config, START, AS_OF)

    def test_shared_campaign_cannot_duplicate_store_totals_across_posts(self):
        self.config['metric_samples'] = [self.sample()]
        other = dict(self.post, platform='linkedin', template_id='linkedin', status='posted',
                     posted_url='https://www.linkedin.com/feed/update/urn:li:activity:123/')
        self.write_json('generated/social/manifest.json', {'posts': [self.post, other]})
        with self.assertRaisesRegex(MeasurementError, 'Shared campaign'):
            report(self.root, self.config, START, AS_OF)

    def test_multi_app_topic_campaign_is_bound_to_actual_store_package(self):
        apps = self.root / 'data/apps_registry.csv'
        apps.write_text(apps.read_text() + 'APP-0002,Other,released,true,android,,https://play.google.com/store/apps/details?id=other\n')
        topics = self.root / 'data/topics.csv'
        topics.write_text(topics.read_text().replace('TOPIC-0001,Fixture,', 'TOPIC-0001,Fixture|Other,'))
        sample = self.sample()
        self.config['metric_samples'] = [dict(sample, app_id='APP-0002')]
        with self.assertRaisesRegex(MeasurementError, 'matching published campaign'):
            report(self.root, self.config, START, AS_OF)
        self.config['metric_samples'] = [sample]
        self.assertEqual(1, report(self.root, self.config, START, AS_OF)['summary']['metric_samples'])

    def test_multi_app_apple_campaign_is_bound_to_actual_app_store_id(self):
        (self.root / 'data/apps_registry.csv').write_text(
            'app_id,app_name,status,content_eligible,platforms,app_store_url,play_store_url\n'
            'APP-0001,Fixture,released,true,ios,https://apps.apple.com/app/id123,\n'
            'APP-0002,Other,released,true,ios,https://apps.apple.com/app/id456,\n')
        topics = self.root / 'data/topics.csv'
        topics.write_text(topics.read_text().replace('TOPIC-0001,Fixture,', 'TOPIC-0001,Fixture|Other,'))
        self.post['destination_urls'] = 'https://apps.apple.com/us/app/fixture/id123?pt=9&ct=test&mt=8'
        self.write_json('generated/social/manifest.json', {'posts': [self.post]})
        sample = self.sample()
        sample.update(source='app_store_connect_export', dimensions={'store_platform': 'ios', 'campaign': 'test'},
                      metrics={'total_downloads': 10, 'preorders': 0, 'unique_impressions': 100})
        self.config['metric_samples'] = [dict(sample, app_id='APP-0002')]
        with self.assertRaisesRegex(MeasurementError, 'matching published campaign'):
            report(self.root, self.config, START, AS_OF)
        self.config['metric_samples'] = [sample]
        self.assertEqual(.1, report(self.root, self.config, START, AS_OF)['records'][0]['metrics'][0]['rates']['app_store_conversion_rate'])

    def test_tracking_links_preserve_identity_and_require_real_apple_provider(self):
        google = tracking_link('https://play.google.com/store/apps/details?id=com.example.app', 'google_play', 'x', 'trial-1')
        self.assertEqual({'id': ['com.example.app'], 'utm_source': ['x'], 'utm_campaign': ['trial-1']}, parse_qs(urlsplit(google).query))
        with self.assertRaisesRegex(MeasurementError, 'existing App Store Connect'):
            tracking_link('https://apps.apple.com/app/id123', 'app_store', 'x', 'trial-1')
        apple = tracking_link('https://apps.apple.com/app/id123', 'app_store', 'x', 'trial-1', '123456')
        self.assertEqual({'pt': ['123456'], 'ct': ['trial-1'], 'mt': ['8']}, parse_qs(urlsplit(apple).query))
        with self.assertRaisesRegex(MeasurementError, 'overwritten'):
            tracking_link(apple, 'app_store', 'x', 'trial-2', '123456')

    def test_tracking_rejects_spoofed_hosts_and_personal_campaign_values(self):
        for url in ['https://apps.apple.com.evil/app/id123', 'https://user@apps.apple.com/app/id123']:
            with self.assertRaises(MeasurementError):
                tracking_link(url, 'app_store', 'x', 'trial-1', '123')
        with self.assertRaises(MeasurementError):
            tracking_link('https://apps.apple.com/app/id123', 'app_store', 'x', 'person@example.com', '123')
        token = campaign_token('APP-0001', 'TOPIC-0001', 'x', START)
        self.assertLessEqual(len(token), 30)
        self.assertEqual(token, campaign_token('APP-0001', 'TOPIC-0001', 'x', START))

    def test_user_reported_purchases_do_not_become_metrics(self):
        self.config['notes'] = [{'app_id': 'APP-0002', 'reported_purchase_count': 13, 'kind': 'user_reported_unverified'}]
        result = report(self.root, self.config, START, AS_OF)
        self.assertIsNone(result['records'][0]['metrics'])
        self.assertEqual(13, result['notes'][0]['reported_purchase_count'])
        self.assertIsNone(result['experiment_proposals'][0]['weight_change'])

    def test_hashnode_and_variants_are_excluded(self):
        self.write_json('generated/social/manifest.json', {'posts': [self.post, dict(self.post, platform='hashnode'), dict(self.post, is_variant=True)]})
        self.assertEqual(1, len(report(self.root, self.config, START, AS_OF)['records']))


if __name__ == '__main__':
    unittest.main()
