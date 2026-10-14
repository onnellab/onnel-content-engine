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


def public_fixture(value, raw, *, featured=True):
    def fetch(url):
        if '/release-artwork/' in url:
            return json.dumps(value).encode()
        if '/app-assets/' in url:
            return raw
        is_detail = '/apps/' in url
        segment = (url.split('/apps/' + value['app_slug'] + '/')[1] if is_detail else
                   url.split('://', 1)[1].split('/', 1)[1]).split('/')[0].split('?')[0]
        locale = next((locale for locale in live.LOCALES if locale.lower() == segment), 'en')
        images = []
        for asset in value['assets']:
            if asset['locale'] != locale:
                continue
            src = f"/app-assets/{value['app_slug']}/assets/screenshots/{asset['site_path']}?v={asset['sha256']}"
            marker = ('' if is_detail else f'data-home-artwork-source="reviewed" '
                      f'data-home-artwork-slug="{value["app_slug"]}" data-home-artwork-locale="{locale}" '
                      f'data-home-artwork-index="{asset["index"]}"')
            images.append(f'<figure><a data-screenshot-link><img {marker} src="{src}" width="{asset["size"][0]}" height="{asset["size"][1]}"></a></figure>')
        if not is_detail:
            content = (f'<section data-home-featured-slug="{value["app_slug"]}" data-home-featured-locale="{locale}">'
                       + ''.join(images) + '</section>') if featured else ''
            return (f'<main data-home-artwork-contract="1" data-home-locale="{locale}">'
                    + content + '</main>').encode()
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
            report = stage.stage_all(Path('releases'), Path('stores'), self.site, None, self.root / 'work')
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
            return stage.stage_all(Path('releases'), Path('stores'), self.site, None, self.root / 'work')

    def test_stale_review_blocks_without_staging(self):
        calls = []
        def gate(*args):
            calls.append(args[1])
            raise ValueError('Stale candidate source commit')
        report = self.report(gate)
        self.assertEqual(calls, ['verify-site'])
        self.assertEqual(report['apps'][0]['status'], 'blocked')
        self.assertEqual(list(self.site.iterdir()), [])

    def test_nonpublic_current_candidate_blocks_without_staging(self):
        calls = []
        report = self.report(lambda *args: calls.append(args[1]), version='1.2.2')
        self.assertEqual(calls, ['verify-site'])
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
            report = stage.stage_all(Path('releases'), Path('stores'), self.site, None, self.root / 'work')
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
        self.assertEqual(len(result['homepages']), 2)
        self.assertEqual([page['featured_container_count'] for page in result['homepages']], [1, 1])
        self.assertEqual(result['selected_source_kind'], 'android')

    def test_all_nine_locales_and_multiple_ordered_images(self):
        value, raw = expected(locales=tuple(sorted(live.LOCALES)))
        originals = list(value['assets'])
        for asset in originals:
            value['assets'].append(dict(asset, index=2, site_path=asset['locale'] + '/02.png'))
        value['assets'].sort(key=lambda item: (item['locale'], item['index']))
        result = live.verify_app(value, self.base, public_fixture(value, raw))
        self.assertEqual(len(result['pages']), 9)
        self.assertEqual(len(result['assets']), 18)
        self.assertEqual(len(result['homepages']), 9)

    def test_explicit_android_and_iphone_medium_source_selection(self):
        for kind, reason in live.SOURCE_REASONS.items():
            with self.subTest(kind=kind):
                value, raw = expected()
                for asset in value['assets']:
                    asset['kind'] = kind
                value['source_selection'] = dict(policy='android-edited-then-iphone-edited', kind=kind, reason=reason)
                result = live.verify_app(value, self.base, public_fixture(value, raw))
                self.assertEqual(result['selected_source_kind'], kind)

    def test_invalid_selection_or_undeclared_iphone_fallback_blocks(self):
        for selection in (None, {}, dict(policy='other', kind='iphone_medium', reason='android_edited_absent'),
                          dict(policy='android-edited-then-iphone-edited', kind='iphone_medium', reason='android_edited_available'),
                          dict(policy='android-edited-then-iphone-edited', kind='android', reason='android_edited_available')):
            with self.subTest(selection=selection):
                value, raw = expected()
                for asset in value['assets']:
                    asset['kind'] = 'iphone_medium'
                if selection is not None:
                    value['source_selection'] = selection
                with self.assertRaisesRegex(ValueError, 'source_selection'):
                    live.verify_app(value, self.base, public_fixture(value, raw))

    def test_mixed_sources_and_incomplete_locale_index_sets_block(self):
        self.value['assets'][1]['kind'] = 'iphone_medium'
        with self.assertRaisesRegex(ValueError, 'uniform'):
            live.verify_app(self.value, self.base, self.fetch)
        self.value['assets'][1]['kind'] = 'android'
        self.value['assets'].append(dict(self.value['assets'][0], index=2, site_path='en/02.png'))
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            live.verify_app(self.value, self.base, self.fetch)

    def test_invalid_or_mixed_version_source_and_dimensions_block(self):
        for field, wrong in (('version', '1.2.2+4'), ('source_commit', 'c' * 40), ('size', [True, 2160]),
                             ('size', [0, 2160]), ('index', True), ('index', '1'), ('kind', 'iphone_large')):
            with self.subTest(field=field, wrong=wrong):
                value, raw = expected()
                value['assets'][0][field] = wrong
                with self.assertRaisesRegex(ValueError, 'mapping'):
                    live.verify_app(value, self.base, public_fixture(value, raw))
        for field, wrong in (('version', '1.2.3'), ('source_commit', 'not-a-commit')):
            with self.subTest(field=field):
                value, raw = expected()
                value[field] = wrong
                with self.assertRaisesRegex(ValueError, 'version/build/source'):
                    live.verify_app(value, self.base, public_fixture(value, raw))

    def test_duplicate_paths_and_noncontiguous_indices_block(self):
        for index in (1, 3):
            with self.subTest(index=index):
                value, raw = expected()
                value['assets'].append(dict(value['assets'][0], index=index, site_path='en/02.png'))
                with self.assertRaisesRegex(ValueError, 'Non-contiguous'):
                    live.verify_app(value, self.base, public_fixture(value, raw))
        self.value['assets'].append(dict(self.value['assets'][0], index=2))
        with self.assertRaisesRegex(ValueError, 'mapping'):
            live.verify_app(self.value, self.base, self.fetch)

    def home_fetch(self, transform):
        def fetch(url):
            raw = self.fetch(url)
            return transform(raw) if url in (self.base + '/', self.base + '/ko/') else raw
        return fetch

    def test_homepage_nonfeatured_app_is_explicitly_reported(self):
        result = live.verify_app(self.value, self.base, public_fixture(self.value, self.raw, featured=False))
        self.assertEqual([page['featured_container_count'] for page in result['homepages']], [0, 0])
        self.assertEqual([page['images'] for page in result['homepages']], [[], []])

    def test_old_homepage_without_contract_or_wrong_locale_blocks(self):
        for old, new in ((b'data-home-artwork-contract="1"', b''), (b'data-home-locale="en"', b'data-home-locale="ko"')):
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, 'contract'):
                live.verify_app(self.value, self.base, self.home_fetch(lambda data: data.replace(old, new)))

    def test_homepage_raw_originals_and_empty_featured_container_block(self):
        for old, new in ((b'data-home-artwork-source="reviewed"', b'data-home-artwork-source="legacy"'),
                         (b'data-home-artwork-source="reviewed"', b''),
                         (b'<img ', b'<span ')):
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, 'homepage featured'):
                live.verify_app(self.value, self.base, self.home_fetch(lambda data: data.replace(old, new)))

    def test_homepage_marked_product_icon_does_not_count_as_artwork(self):
        icon = b'<img data-home-artwork-icon="true" src="/home-assets/app-icons/app-96.webp">'
        fetch = self.home_fetch(lambda data: data.replace(b'</section>', icon + b'</section>'))
        result = live.verify_app(self.value, self.base, fetch)
        self.assertEqual([len(page['images']) for page in result['homepages']], [1, 1])
        spoofed = b'<img data-home-artwork-icon="true" src="/app-assets/app/assets/originals/en/01.png">'
        with self.assertRaisesRegex(ValueError, 'identity'):
            live.verify_app(self.value, self.base, self.home_fetch(
                lambda data: data.replace(b'</section>', spoofed + b'</section>')))

    def test_homepage_existing_responsive_icon_pair_is_preserved(self):
        icon = (b'<img data-home-artwork-icon="true" src="/home-assets/app-icons/app-96.webp" '
                b'srcset="/home-assets/app-icons/app-96.webp 96w, /home-assets/app-icons/app-192.webp 192w" '
                b'sizes="56px" width="96" height="96">')
        result = live.verify_app(self.value, self.base, self.home_fetch(
            lambda data: data.replace(b'</section>', icon + b'</section>')))
        self.assertEqual([len(page['images']) for page in result['homepages']], [1, 1])
        self.assertEqual([page['featured_container_count'] for page in result['homepages']], [1, 1])

    def test_homepage_icon_srcset_exemption_rejects_unknown_urls_or_variants(self):
        pairs = (
            '/home-assets/app-icons/app-96.webp 96w, /app-assets/app/assets/originals/en/01.png 192w',
            '/home-assets/app-icons/app-96.webp 96w, /home-assets/app-icons/other-192.webp 192w',
            '/home-assets/app-icons/app-96.webp 96w, https://example.com/app-192.webp 192w',
            '/home-assets/app-icons/app-96.webp 96w, /home-assets/app-icons/app-192.webp 192w, /extra.webp 384w',
            '/home-assets/app-icons/app-96.webp 1x, /home-assets/app-icons/app-192.webp 2x',
            '/home-assets/app-icons/app-96.webp 96w',
        )
        for srcset in pairs:
            icon = (f'<img data-home-artwork-icon="true" src="/home-assets/app-icons/app-96.webp" '
                    f'srcset="{srcset}">').encode()
            with self.subTest(srcset=srcset), self.assertRaisesRegex(ValueError, 'identity'):
                live.verify_app(self.value, self.base, self.home_fetch(
                    lambda data: data.replace(b'</section>', icon + b'</section>')))

    def test_homepage_picture_or_source_cannot_override_reviewed_img(self):
        transforms = (
            lambda data: data.replace(b'<img ', b'<picture><source srcset="/unreviewed.webp"><img ').replace(
                b'</figure>', b'</picture></figure>'),
            lambda data: data.replace(b'<img ', b'<source srcset="/unreviewed.webp"><img '),
            # Ancestor picture starts outside the marked featured container.
            lambda data: data.replace(b'<section ', b'<picture><source srcset="/unreviewed.webp"><section ').replace(
                b'</section>', b'</section></picture>'),
        )
        for transform in transforms:
            with self.subTest(transform=transform), self.assertRaisesRegex(ValueError, 'picture/source'):
                live.verify_app(self.value, self.base, self.home_fetch(transform))

    def test_homepage_duplicate_attributes_fail_before_browser_parser_disagreement(self):
        variants = (
            (b'<img ', b'<img src="/unreviewed.png" '),
            (b'<img ', b'<img width="999" '),
            (b'<section ', b'<section data-home-featured-slug="other" '),
            (b'<main ', b'<main data-home-locale="other" '),
            (b'data-home-artwork-slug="app"', b'data-home-artwork-slug="app" data-home-artwork-slug="other"'),
        )
        for old, new in variants:
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, 'Duplicate HTML attributes'):
                live.verify_app(self.value, self.base, self.home_fetch(lambda data: data.replace(old, new)))

    def test_gallery_picture_source_and_duplicate_attributes_fail_closed(self):
        transforms = (
            lambda data: data.replace(b'<img ', b'<picture><source srcset="/unreviewed.webp"><img ').replace(
                b'</figure>', b'</picture></figure>'),
            lambda data: data.replace(b'<img ', b'<source srcset="/unreviewed.webp"><img '),
            lambda data: data.replace(b'<div data-screenshot-row>', b'<picture><source srcset="/unreviewed.webp"><div data-screenshot-row>').replace(
                b'</div>', b'</div></picture>'),
            lambda data: data.replace(b'<img ', b'<img src="/unreviewed.png" '),
            lambda data: data.replace(b'<img ', b'<img width="999" '),
            lambda data: data.replace(b'<main ', b'<main data-product-slug="other" '),
        )
        for transform in transforms:
            def fetch(url):
                raw = self.fetch(url)
                return transform(raw) if '/apps/' in url else raw
            with self.subTest(transform=transform), self.assertRaisesRegex(ValueError, 'picture/source|Duplicate HTML attributes'):
                live.verify_app(self.value, self.base, fetch)

    def test_homepage_index_locale_hash_route_and_dimensions_must_match(self):
        variants = ((b'data-home-artwork-index="1"', b'data-home-artwork-index="2"', 'index'),
                    (b'data-home-artwork-locale="en"', b'data-home-artwork-locale="ko"', 'identity'),
                    (b'data-home-featured-locale="en"', b'data-home-featured-locale="ko"', 'locale'),
                    (b'?v=' + self.value['assets'][0]['sha256'].encode(), b'?v=old', 'image/hash'),
                    (b'/screenshots/en/01.png', b'/originals/en/01.png', 'image/hash'),
                    (b'height="2160"', b'height="2168"', 'dimensions'),
                    (b'height="2160"', b'', 'dimensions'),
                    (b'src="/app-assets/', b'src="https://untrusted.example/app-assets/', 'origin'),
                    (b'src="/app-assets/', b'src="app-assets/', 'image/hash'),
                    (b'<img ', b'<img srcset="/different.png 2x" ', 'transformed'))
        for old, new, error in variants:
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, error):
                live.verify_app(self.value, self.base, self.home_fetch(lambda data: data.replace(old, new)))

    def test_homepage_image_bytes_are_fetched_and_verified_independently(self):
        seen = set()
        def fetch(url):
            raw = self.fetch(url)
            if '/app-assets/' in url:
                if url in seen:
                    return b'wrong featured bytes'
                seen.add(url)
            return raw
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            live.verify_app(self.value, self.base, fetch)

    def test_actual_png_dimensions_must_match_even_if_manifest_hash_matches(self):
        bad_raw = self.raw[:16] + struct.pack('>II', 1080, 2168) + self.raw[24:]
        for asset in self.value['assets']:
            asset['sha256'] = hashlib.sha256(bad_raw).hexdigest()
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            live.verify_app(self.value, self.base, public_fixture(self.value, bad_raw))

    def test_wrong_gallery_order_blocks(self):
        self.value['assets'].extend(dict(asset, index=2, site_path=asset['locale'] + '/02.png')
                                    for asset in list(self.value['assets']))
        normal = public_fixture(self.value, self.raw)
        def fetch(url):
            data = normal(url)
            if '/apps/' in url:
                data = data.replace(b'en/01.png', b'en/temp.png').replace(b'en/02.png', b'en/01.png').replace(b'en/temp.png', b'en/02.png')
            return data
        with self.assertRaisesRegex(ValueError, 'app-detail gallery'):
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
