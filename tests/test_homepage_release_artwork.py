import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync_homepage_release_artwork as stage
import verify_homepage_release_artwork as live
from check_store_versions import STORE_HEADER


def write_csv(path, rows, header=None):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def release(slug='app', version='1.2.3', **extra):
    return dict(app_id=slug, app_slug=slug, repository='onnellab/' + slug,
                status='released', release_channel='public', platform='android',
                release_id='rel-' + slug, version=version, **extra)


def store(slug='app', version='1.2.3', **extra):
    out = dict.fromkeys(STORE_HEADER, '')
    out.update(app_id=slug, app_slug=slug, platform='android', version=version,
               status='unchanged', checked_at='2026-10-14T00:00:00+00:00', store_url='https://play.google.com/store/apps/details?id=app')
    out.update(extra)
    return out


def expected(slug='app', locales=('en', 'ko')):
    raw = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + struct.pack('>II', 1080, 2160) + b'reviewed-bytes'
    value = dict(status='staged_not_published', app_slug=slug, version='1.2.3+4',
                 source_commit='b' * 40, candidate_sha256='a' * 64,
                 assets=[dict(locale=locale, kind='android', index=1, site_path=locale + '/01.png',
                              sha256=hashlib.sha256(raw).hexdigest(), size=[1080, 2160]) for locale in locales])
    return value, raw


def public_fixture(value, raw):
    def fetch(url):
        if '/release-artwork/' in url:
            return json.dumps(value).encode()
        if '/app-assets/' in url:
            return raw
        segment = url.split('/apps/' + value['app_slug'] + '/')[1].split('/')[0].split('?')[0]
        locale = next((locale for locale in live.LOCALES if locale.lower() == segment), 'en')
        images = []
        for asset in value['assets']:
            if asset['locale'] != locale:
                continue
            src = f"/app-assets/{value['app_slug']}/assets/screenshots/{asset['site_path']}?v={asset['sha256']}"
            images.append(f'<figure><a data-screenshot-link><img src="{src}" width="{asset["size"][0]}" height="{asset["size"][1]}"></a></figure>')
        return (f'<main data-product-slug="{value["app_slug"]}" data-product-locale="{locale}">'
                '<div data-screenshot-row>' + ''.join(images) + '</div>'
                '<img src="/home-original.png"></main>').encode()
    return fetch


class PublicSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.releases, self.stores = self.root / 'releases.csv', self.root / 'stores.csv'

    def tearDown(self):
        self.temp.cleanup()

    def selected(self, row=None, snapshot=None):
        write_csv(self.releases, [row or release()])
        write_csv(self.stores, [snapshot or store()], STORE_HEADER)
        return stage.eligible_releases(self.releases, self.stores, now=datetime(2026, 10, 14, 1, tzinfo=timezone.utc))

    def test_public_observation_rechecks_released_row(self):
        self.assertEqual(len(self.selected()), 1)

    def test_uploaded_or_in_review_does_not_mean_public(self):
        for status in ('uploaded', 'in_review', 'manual_check', 'unknown', ''):
            with self.subTest(status=status):
                self.assertEqual(self.selected(snapshot=store(status=status)), [])

    def test_fallback_after_public_lookup_failure_is_not_public_evidence(self):
        self.assertEqual(self.selected(snapshot=store(notes='Public page lookup failed; using console')), [])

    def test_private_and_mismatched_versions_block(self):
        row = release()
        row['release_channel'] = 'private_test'
        self.assertEqual(self.selected(row=row), [])
        self.assertEqual(self.selected(snapshot=store(version='1.2.2')), [])

    def test_stale_future_missing_and_naive_observations_are_flagged(self):
        for checked_at in ('2026-10-12T00:00:00Z', '2026-10-15T00:00:00Z', '', '2026-10-14T00:00:00'):
            with self.subTest(checked_at=checked_at):
                self.assertTrue(self.selected(snapshot=store(checked_at=checked_at))[0]['store_evidence_error'])
        self.assertEqual(self.selected()[0]['store_evidence_error'], '')

    def test_slug_mismatch_and_path_escape_block(self):
        with self.assertRaises(ValueError):
            self.selected(snapshot=store(app_slug='other'))
        row = release()
        row['repository'] = '../app'
        with self.assertRaises(ValueError):
            self.selected(row=row)


class Staging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.site = self.root / 'site'
        self.site.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def project(self, subdir='nested/app'):
        app = self.repo / subdir
        (app / 'release').mkdir(parents=True)
        (app / 'pubspec.yaml').write_text('version: 1.2.3+4\n')
        (app / 'release/artwork.json').write_text('{"app_slug":"app"}')
        (app / 'release/artwork-candidate.json').write_text(json.dumps(expected()[0]))
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        return app

    def test_monorepo_discovery_unique_inventory(self):
        project = self.project()
        self.assertEqual(stage.locate_project(self.repo, 'app'), project)
        self.project('another/app')
        with self.assertRaises(ValueError):
            stage.locate_project(self.repo, 'app')

    def test_nonobject_inventory_becomes_reportable_failure(self):
        self.project()
        bad = self.repo / 'other/release/artwork.json'
        bad.parent.mkdir(parents=True)
        bad.write_text('[]')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        with self.assertRaisesRegex(ValueError, 'JSON object'):
            stage.locate_project(self.repo, 'app')

    def test_stale_observation_blocks_before_network_or_site_changes(self):
        row = release(store_evidence_error='Public store observation is older than 24 hours')
        with patch.object(stage, 'eligible_releases', return_value=[row]), patch.object(stage, 'checkout') as checkout:
            report = stage.stage_all(Path('releases'), Path('stores'), self.site, Path('gate'), self.root / 'work')
        checkout.assert_not_called()
        self.assertEqual(report['apps'][0]['status'], 'blocked')
        self.assertIn('24 hours', report['apps'][0]['reason'])

    def test_missing_inventory_does_not_fallback_to_existing_site_images(self):
        with self.assertRaises(ValueError):
            stage.locate_project(self.repo, 'app')

    def report(self, gate_effect=None, version='1.2.3'):
        self.project()
        rows = [release(version=version, store_checked_at='2026-10-14T00:00:00Z', store_url='https://play.google.com')]
        with patch.object(stage, 'eligible_releases', return_value=rows), patch.object(stage, 'checkout', return_value=self.repo), patch.object(stage, 'run_gate', side_effect=gate_effect):
            return stage.stage_all(Path('releases'), Path('stores'), self.site, Path('gate'), self.root / 'work')

    def test_stale_review_blocks_without_staging(self):
        calls = []
        def gate(*args):
            calls.append(args[1])
            raise ValueError('Stale candidate source commit')
        report = self.report(gate)
        self.assertEqual(calls, ['verify'])
        self.assertEqual(report['apps'][0]['status'], 'blocked')
        self.assertEqual(list(self.site.iterdir()), [])

    def test_nonpublic_current_candidate_blocks_without_staging(self):
        calls = []
        report = self.report(lambda *args: calls.append(args[1]), version='1.2.2')
        self.assertEqual(calls, ['verify'])
        self.assertIn('not independently public', report['apps'][0]['reason'])

    def test_verified_candidate_stages_exact_paths_only(self):
        def gate(*args):
            if args[1] == 'stage-site':
                dest = self.site / 'public/release-artwork/app.json'
                dest.parent.mkdir(parents=True)
                dest.write_text(json.dumps(expected()[0]))
        app = self.report(gate)['apps'][0]
        self.assertEqual(app['status'], 'staged_not_published')
        self.assertEqual(app['staged_paths'], ['public/release-artwork/app.json',
                         'src/content/apps/app/assets/screenshots/en/01.png',
                         'src/content/apps/app/assets/screenshots/ko/01.png'])

    def test_blocked_repository_does_not_prevent_independent_valid_app(self):
        self.project()
        badrepo = self.root / 'badrepo'
        subprocess.run(['git', 'init', '-q', str(badrepo)], check=True)
        rows = [release(store_checked_at='2026-10-14T00:00:00Z', store_url='https://play.google.com'), release('other')]
        def gate(*args):
            if args[1] == 'stage-site':
                dest = self.site / 'public/release-artwork/app.json'
                dest.parent.mkdir(parents=True)
                dest.write_text(json.dumps(expected()[0]))
        with patch.object(stage, 'eligible_releases', return_value=rows), patch.object(stage, 'checkout', side_effect=lambda repo, work: self.repo if repo == 'onnellab/app' else badrepo), patch.object(stage, 'run_gate', side_effect=gate):
            report = stage.stage_all(Path('releases'), Path('stores'), self.site, Path('gate'), self.root / 'work')
        self.assertEqual([app['status'] for app in report['apps']], ['staged_not_published', 'blocked'])

    def test_git_stages_only_exact_verified_paths(self):
        subprocess.run(['git', 'init', '-q', str(self.site)], check=True)
        paths = ['public/release-artwork/app.json', 'src/content/apps/app/assets/screenshots/en/01.png']
        for name in paths + ['src/content/apps/app/assets/originals/home.png']:
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        stage.stage_git(self.site, {'apps': [{'app_slug': 'app', 'status': 'staged_not_published', 'staged_paths': paths}]})
        actual = subprocess.check_output(['git', '-C', str(self.site), 'diff', '--cached', '--name-only'], text=True).splitlines()
        self.assertEqual(actual, sorted(paths))

    def test_git_staging_rejects_unrelated_home_originals(self):
        report = {'apps': [{'app_slug': 'app', 'status': 'staged_not_published',
                           'staged_paths': ['src/content/apps/app/assets/originals/home.png']}]}
        with self.assertRaises(ValueError):
            stage.stage_git(self.site, report)


class LiveVerification(unittest.TestCase):
    def setUp(self):
        self.value, self.raw = expected()
        self.fetch = public_fixture(self.value, self.raw)
        self.base = 'https://onnellab.com'

    def test_full_manifest_page_gallery_image_bytes_verified(self):
        result = live.verify_app(self.value, self.base, self.fetch)
        self.assertEqual(result['status'], 'deployed_verified')
        self.assertEqual(len(result['pages']), 2)
        self.assertEqual(len(result['assets']), 2)

    def test_all_nine_locales_and_multiple_ordered_images(self):
        value, raw = expected(locales=tuple(sorted(live.LOCALES)))
        originals = list(value['assets'])
        for asset in originals:
            value['assets'].append(dict(asset, index=2, site_path=asset['locale'] + '/02.png'))
        value['assets'].sort(key=lambda item: (item['locale'], item['index']))
        result = live.verify_app(value, self.base, public_fixture(value, raw))
        self.assertEqual(len(result['pages']), 9)
        self.assertEqual(len(result['assets']), 18)

    def test_wrong_gallery_order_blocks(self):
        self.value['assets'].insert(1, dict(self.value['assets'][0], index=2, site_path='en/02.png'))
        normal = public_fixture(self.value, self.raw)
        def fetch(url):
            data = normal(url)
            if '/apps/' in url:
                data = data.replace(b'en/01.png', b'en/temp.png').replace(b'en/02.png', b'en/01.png').replace(b'en/temp.png', b'en/02.png')
            return data
        with self.assertRaisesRegex(ValueError, 'gallery'):
            live.verify_app(self.value, self.base, fetch)

    def test_stale_public_receipt_blocks(self):
        def fetch(url):
            return b'{}' if '/release-artwork/' in url else self.fetch(url)
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            live.verify_app(self.value, self.base, fetch)

    def test_correct_receipt_but_wrong_image_hash_blocks(self):
        def fetch(url):
            return b'old bytes' if '/app-assets/' in url else self.fetch(url)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            live.verify_app(self.value, self.base, fetch)

    def test_unversioned_or_missing_gallery_does_not_count(self):
        for replacement in ('', '?v=old'):
            def fetch(url):
                data = self.fetch(url)
                if '/apps/' in url:
                    data = data.replace(('?v=' + self.value['assets'][0]['sha256']).encode(), replacement.encode())
                return data
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, 'gallery'):
                live.verify_app(self.value, self.base, fetch)

    def test_html_dimensions_must_match_reviewed_image_dimensions(self):
        for replacement in (b'height="2168"', b'', b'height="2160px"'):
            def fetch(url):
                data = self.fetch(url)
                return data.replace(b'height="2160"', replacement) if '/apps/' in url else data
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, 'HTML screenshot dimensions'):
                live.verify_app(self.value, self.base, fetch)

    def test_extra_gallery_image_blocks(self):
        def fetch(url):
            data = self.fetch(url)
            if '/apps/' in url:
                data = data.replace(b'</figure>', b'<img src="/unexpected.png"></figure>')
            return data
        with self.assertRaisesRegex(ValueError, 'gallery'):
            live.verify_app(self.value, self.base, fetch)

    def test_cross_origin_image_blocks(self):
        def fetch(url):
            data = self.fetch(url)
            if '/apps/' in url:
                data = data.replace(b'src="/app-assets/', b'src="https://untrusted.example/app-assets/')
            return data
        with self.assertRaisesRegex(ValueError, 'origin'):
            live.verify_app(self.value, self.base, fetch)

    def test_push_is_not_completion_and_blocked_apps_fail_whole_receipt(self):
        staging = {'apps': [{'app_slug': 'app', 'status': 'staged_not_published', 'expected': self.value},
                            {'app_slug': 'other', 'status': 'blocked', 'reason': 'Missing review'}]}
        result = live.verify_report(staging, self.base, 1, 1, self.fetch)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual({app['status'] for app in result['apps']}, {'blocked', 'deployed_verified'})

    def test_deployment_wait_retries_then_finishes_on_actual_bytes(self):
        staging = {'apps': [{'app_slug': 'app', 'status': 'staged_not_published', 'expected': self.value}]}
        count = [0]
        def fetch(url):
            if count[0] == 0:
                count[0] += 1
                return b'{}'
            return self.fetch(url)
        with patch.object(live.time, 'sleep') as sleep:
            result = live.verify_report(staging, self.base, 10, 1, fetch, sleep=sleep)
        self.assertEqual(result['status'], 'deployed_verified')
        sleep.assert_called_once()

    def test_deadline_is_checked_inside_large_gallery_pass(self):
        staging = {'apps': [{'app_slug': 'app', 'status': 'staged_not_published', 'expected': self.value}]}
        now = [0]
        calls = []
        def fetch(url):
            calls.append(url)
            now[0] += 2
            return self.fetch(url)
        result = live.verify_report(staging, self.base, 3, 1, fetch, monotonic=lambda: now[0])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(calls), 2)
        self.assertIn('deadline elapsed', result['apps'][0]['reason'])

    def test_timeout_records_unverified_and_never_claims_published(self):
        staging = {'apps': [{'app_slug': 'app', 'status': 'staged_not_published', 'expected': self.value}]}
        result = live.verify_report(staging, self.base, 0, 1, lambda url: b'{}')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['apps'][0]['status'], 'deployment_unverified')


class WorkflowContract(unittest.TestCase):
    def test_existing_publisher_has_no_new_schedule_and_live_gate_is_mandatory(self):
        text = (Path(__file__).resolve().parents[1] / '.github/workflows/publish-ready-app-releases.yml').read_text()
        self.assertNotIn('schedule:', text)
        self.assertEqual(text.count('push origin HEAD:main'), 2)
        self.assertIn('sync_homepage_release_artwork.py stage', text)
        self.assertIn('verify_homepage_release_artwork.py', text)
        self.assertNotIn('continue-on-error', text)
        self.assertIn('artwork-deployment-receipt.json', text)
        self.assertIn('if: always()', text)


if __name__ == '__main__':
    unittest.main()
