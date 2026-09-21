"""Brand isolation and offline workspace tests; no production tokens or network."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_pipeline import VideoError
from short_video_credentials import resolve_credentials, credential_status, validate_bundle, SETUP_SCOPES
from short_video_oauth import Connection
from youtube_profiles import profile_id, content_profile, require_content_profile, environment_names
from youtube_workspace_panel import youtube_workspace_panel
from aether_planner import read_catalog, inspect_candidate, plan, timeline
from test_short_video_credentials import BUNDLE, MemoryStore, FakeGoogle, CLIENT, CHANNEL, REDIRECT

class ProfileIsolationTests(unittest.TestCase):
    def bundle(self, profile):
        return {**copy.deepcopy(BUNDLE), 'schema_version': 2, 'profile': profile}

    def test_legacy_bundle_only_works_for_onellab(self):
        self.assertEqual(CHANNEL, resolve_credentials(store=MemoryStore(BUNDLE), environ={})['YOUTUBE_CHANNEL_ID'])
        with self.assertRaisesRegex(VideoError, 'profile_mismatch'):
            resolve_credentials(store=MemoryStore(BUNDLE), environ={}, profile='aether_inn')

    def test_modern_bundle_cannot_cross_profiles(self):
        for profile, other in [('onnellab', 'aether_inn'), ('aether_inn', 'onnellab')]:
            store = MemoryStore(self.bundle(profile))
            self.assertEqual(CHANNEL, resolve_credentials(store=store, environ={}, profile=profile)['YOUTUBE_CHANNEL_ID'])
            with self.assertRaisesRegex(VideoError, 'profile_mismatch'):
                resolve_credentials(store=store, environ={}, profile=other)

    def test_keychain_item_name_is_explicit(self):
        with patch('short_video_credentials.MacKeychain', return_value=MemoryStore(self.bundle('aether_inn'))) as factory:
            resolve_credentials(environ={}, profile='aether_inn')
        factory.assert_called_once_with(account='aether_inn')

    def test_aether_has_no_legacy_environment_fallback(self):
        env = {'ONNELLAB_YOUTUBE_CREDENTIAL_SOURCE': 'environment'}
        env.update(dict(zip(environment_names('onnellab'), ['example', 'fixture', 'fixture', CHANNEL])))
        with self.assertRaisesRegex(VideoError, 'missing_youtube_credentials'):
            resolve_credentials(environ=env, profile='aether_inn', store=MemoryStore())
        env['AETHER_INN_YOUTUBE_CREDENTIAL_SOURCE'] = 'environment'
        with self.assertRaisesRegex(VideoError, 'missing_youtube_credentials'):
            resolve_credentials(environ=env, profile='aether_inn')

    def test_readiness_does_not_load_credentials(self):
        store = MemoryStore(self.bundle('aether_inn'))
        result = credential_status(store=store, environ={}, profile='aether_inn')
        self.assertEqual(0, store.loads)
        self.assertEqual('aether_inn', result['profile'])
        self.assertTrue(all(x.startswith('AETHER_INN_') for x in result['required']))
        self.assertFalse(result['network_verified'])

    def test_invalid_profile_and_route_rejected(self):
        for value in ['', '../onnellab', None, 'default']:
            with self.assertRaises(VideoError):
                profile_id(value)
        self.assertEqual('onnellab', content_profile({}))
        self.assertEqual('aether_inn', content_profile({'content_kind': 'aether_single'}))
        with self.assertRaises(VideoError):
            require_content_profile({'content_kind': 'aether_single'}, 'onnellab')

    def test_oauth_library_binds_profile_with_analytics_scope(self):
        store, google = MemoryStore(), FakeGoogle()
        google.scope = ' '.join(SETUP_SCOPES)
        flow = Connection(store, send=google, profile='aether_inn', scopes=SETUP_SCOPES)
        url = flow.begin(CLIENT, CHANNEL, REDIRECT)
        state = parse_qs(urlsplit(url).query)['state'][0]
        result = flow.complete(urlencode({'code': 'TEST-CODE', 'state': state}))
        self.assertEqual('aether_inn', store.value['profile'])
        self.assertEqual(2, store.value['schema_version'])
        self.assertTrue(result['analytics_scope'])
        self.assertEqual('aether_inn', result['profile'])
        self.assertNotIn('DO-NOT-PRINT', json.dumps(result))

class OfflineMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.songs = read_catalog()

    def test_source_count_is_65(self):
        self.assertEqual(65, len(self.songs))
        self.assertEqual(65, len({x['id'] for x in self.songs}))

    def test_exact_title_and_style_duplicate(self):
        first = self.songs[0]
        result = inspect_candidate(first['title'].upper(), first['style'], self.songs)
        self.assertTrue(result['title_duplicate'])
        self.assertTrue(result['style_duplicate'])
        self.assertEqual('not_evaluated', result['audio_originality'])
        self.assertFalse(result['publishable'])

    def test_unique_text_never_certifies_audio(self):
        result = inspect_candidate('Letters at the Amber Observatory', 'Mellow viola with soft six-eight motion', self.songs)
        self.assertEqual('requires_audio_review', result['metadata_gate'])
        self.assertFalse(result['publishable'])

    def test_crossfade_chapters(self):
        rows = [{'id': str(i), 'title': str(i), 'duration_seconds': x} for i, x in enumerate([120,150,180])]
        chapters, duration = timeline(rows)
        self.assertEqual([0,118,266], [x['start_seconds'] for x in chapters])
        self.assertEqual(446, duration)

    def test_coherent_whole_track_plan(self):
        result = plan(self.songs)
        self.assertEqual(1800, result['estimated_duration_seconds'])
        self.assertEqual(len(result['track_ids']), len(set(result['track_ids'])))
        self.assertFalse(result['audio_measured'])
        self.assertFalse(result['publishable'])
        self.assertEqual(sum(x['duration_seconds'] for x in result['tracks']) - 2 * (len(result['tracks'])-1), result['estimated_duration_seconds'])

    def test_insufficient_tracks_do_not_loop_or_fill(self):
        with self.assertRaisesRegex(VideoError, 'insufficient_coherent_tracks'):
            plan(self.songs, history=[{'track_ids': [x['id'] for x in self.songs]}])
        with self.assertRaises(VideoError):
            plan(self.songs, theme='battle')

    def test_historical_source_typo_is_not_silently_changed(self):
        self.assertIn('The Last Light Over Seren Fields Style:', [x['title'] for x in self.songs])

class WorkspaceTests(unittest.TestCase):
    def test_brand_tabs_catalog_and_pending_not_fake_success(self):
        html = youtube_workspace_panel()
        self.assertEqual(65, html.count('class="ytw-song"'))
        for expected in ['role="tablist"', 'data-brand="aether_inn"', 'ytw-report-file', 'ytw-song-search', '아직 미구현', '연결 화면 · 구현 대기']:
            self.assertIn(expected, html)
        self.assertNotIn('__TRACK_COUNT__', html)
        self.assertNotIn('__CATALOG_ROWS__', html)

    def test_no_network_storage_or_untrusted_html_injection(self):
        html = youtube_workspace_panel()
        for forbidden in ['fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage', 'indexedDB', '.innerHTML', 'YOUTUBE_REFRESH_TOKEN']:
            self.assertNotIn(forbidden, html)
        self.assertIn('textContent', html)
        self.assertIn('expires_at', html)
        self.assertIn('current!==generation', html)

if __name__ == '__main__':
    unittest.main()
