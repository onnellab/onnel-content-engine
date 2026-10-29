#!/usr/bin/env python3
"""Bounded, offline screenshot guide. Never records UI or uploads to a provider.

Separate from the managed-recording Short pipeline: a screenshot is not a
recording attestation. Input is a reviewed, repository-tracked guide manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

CHANNEL = 'UCXyRedrldRBl9Y35nyWoTLg'
SOURCE_REPO = 'onnellab/quivra'
SOURCE_COMMIT = 'd3b7ad5e5dcd0412daae55caee657431c6237f5b'
APPROVED_ASSETS = {
    '01.png': '73b9d33f4f5b02ad42cb20a8b0ea2df6f4c89e0e798f7c125791a34171642e4b',
    '02.png': '7555f68068c274842b2a079fb80c79cedf42d1bba956ca1bf1f96b78fb363699',
}
DISCLOSURE = 'Still screenshots · no conversion shown'
TITLE = 'How to Choose Files in Quivra | Media Converter Screenshot Guide'
COPY = [
    ('Choose files for conversion', 'Start at the Library screen.', '01.png'),
    ('Review your file list', 'Check the names before you continue.', '02.png'),
    ('Find the Convert button', 'Quivra · local media converter', '02.png'),
]

# Reviewed Melivra contract. Any change requires new source/copy review and tests.
MELIVRA_CONTRACT = {'schema_version': 1,
 'kind': 'screenshot_guide',
 'guide_id': 'melivra-favorites-20261012',
 'app_id': 'APP-0007',
 'locale': 'en',
 'channel_id': 'UCXyRedrldRBl9Y35nyWoTLg',
 'source': {'repository': 'onnellab/melivra',
            'commit': '6314b685a41c690e8ccd9a080c095078ebb0db10',
            'git_tree_sha': '261cb0863ce683df5eaeb9dfc6e9afac2b6f8b62',
            'capture_manifest_path': 'assets/store_promo/raw/android/en/capture.json',
            'capture_manifest_git_blob_sha': '2baea9bd221db9f086718ee37d6da5fd51130d04',
            'capture_id': '20261010T010826Z-23651146',
            'captured_at': '2026-10-10T01:12:07.756029+00:00',
            'capture_device_kind': 'Android emulator',
            'capture_source_commit': '1341678a676ce9a2dc34888f271f1e4809182851',
            'capture_source_version': '1.0.6+142',
            'reviewed_source_version': '1.0.7+144',
            'recorded_source_digest': '2f8f7372fd4fe10f8f1ba473a8ef2ec736d7e173861263d788d165959bb0d224',
            'recorded_source_digest_independently_recomputed': False,
            'capture_test': 'integration_test/store_promo_capture_test.dart',
            'capture_test_git_blob_sha': '7e4b720db19a88d97371f363a6c23f695f527610',
            'capture_type': 'real_app_ui_with_repository_demonstration_library',
            'source_parity': 'Recursive source comparison found all lib files and the screenshot '
                             'harness identical between capture revision and reviewed commit '
                             'except version/build constants in lib/core/config/app_env.dart.',
            'capture_version_note': "Actual Android emulator screenshots. The capture manifest's "
                                    'real-device label does not override its emulator device_id. '
                                    'No exact signed-release-build capture attestation is claimed.',
            'runtime_playback_verified': False,
            'limitations': ['Favorites, ratings, playlists, listening history and silent WAV files '
                            'are seeded repository demonstration data.',
                            'Pixels do not prove successful import, playback, audio quality, save, '
                            'conversion, performance or user results.',
                            'Claims are limited to actual visible screen labels, not off-screen '
                            'labels in the capture manifest.'],
            'public_version_observed': '1.0.7',
            'public_version_source': 'https://play.google.com/store/apps/details?id=com.onnellab.melivra',
            'public_version_checked_at': '2026-10-11T09:54:29Z'},
 'assets': [{'local_name': '1.png',
             'source_path': 'assets/store_promo/raw/android/en/1.png',
             'sha256': 'fdb884bb6996709110dc17b08a3a43c0a2a9b87ebf96640daf5ad944dc3e03cb'},
            {'local_name': '4.png',
             'source_path': 'assets/store_promo/raw/android/en/4.png',
             'sha256': '7c99e94b38b901d5be486a958138fd2719462fd6ab161ad27d4443320acb6ec9'}],
 'slides': [{'heading': 'Find your favorite songs',
             'caption': 'Open Lists in Melivra.',
             'asset': '1.png',
             'seconds': 5},
            {'heading': 'Choose Favorite Songs',
             'caption': 'Look under Smart Playlists.',
             'asset': '4.png',
             'seconds': 5},
            {'heading': 'Browse by rating, too',
             'caption': 'Find 5-Star and 4-5 Star Songs.',
             'asset': '4.png',
             'seconds': 5}],
 'metadata': {'title': 'How to Find Favorite Songs in Melivra | Android Screenshot Guide',
              'description': 'To find favorite songs in Melivra, open Lists and look under Smart '
                             'Playlists for Favorite Songs. The same screen includes 5-Star Songs '
                             'and 4-5 Star Songs.\n'
                             '\n'
                             'Still-screen guide using real Android app screenshots with an '
                             'original demonstration library. No taps, playback, file import, save '
                             'result, or speed demonstration is shown.\n'
                             '\n'
                             'Explore Melivra for Android:\n'
                             'Google Play: '
                             'https://play.google.com/store/apps/details?id=com.onnellab.melivra\n'
                             '\n'
                             '#Melivra #OfflineMusicPlayer #Shorts',
              'format_disclosure': 'Still-screen guide · Demo library',
              'audio': 'none',
              'made_for_kids': False,
              'synthetic_media': False,
              'category': 'Education',
              'cta': 'Melivra for Android · Link in description',
              'target_publish_at': '2026-10-12T09:00:00+09:00',
              'timezone': 'Asia/Seoul'},
 'authorization': {'format_approved_on': '2026-10-08',
                   'rights_basis': 'ONNELLAB-owned app UI and repository-owned demonstration data',
                   'scope': 'English screenshot-based app guide on ONNELLAB YouTube; no simulated '
                            'interaction; existing recording gate unchanged',
                   'execution_scope': 'Owner-authorized free dot-cloud Melivra production and test '
                                      'commands; no separate Work/Codex or paid service.'}}

# Independently reviewed ClipNest contract; does not broaden existing apps.
CLIPNEST_CONTRACT = {'schema_version': 1,
 'kind': 'screenshot_guide',
 'guide_id': 'clipnest-search-20261014',
 'app_id': 'APP-0005',
 'locale': 'en',
 'channel_id': 'UCXyRedrldRBl9Y35nyWoTLg',
 'source': {'repository': 'onnellab/clipnest',
            'commit': '5db2441e1cff466012a020717c856aa357ba6cc7',
            'capture_added_commit': '33baceb79cc19d090d09f5d6c298da6cd1474afb',
            'capture_commit_source_version': '1.0.4+97',
            'reviewed_source_version': '1.0.5+98',
            'public_version_observed': '1.0.5',
            'public_version_source': 'https://apps.apple.com/us/app/clipnest-clipboard-history/id6779928552',
            'public_version_checked_at': '2026-10-13T09:14:19Z',
            'capture_type': 'real_iphone_simulator_ui_with_repository_demonstration_text',
            'provenance': 'Real iPhone simulator captures using production HomeScreen/search '
                          'presentation with FakeClipsStore, seeded original demonstration text, '
                          'fake purchase and keyboard bridges. Not an exact signed-release capture '
                          'or evidence of real storage/clipboard/paste actions.',
            'rights': 'User-owned ONNELLAB app UI and repository-authored six English sample '
                      'clips. No user clipboard data, stock imagery, narration or music.',
            'source_parity': 'Capture commit and current main have identical home/search UI files '
                             'and unchanged selected PNGs. Five lib files differ only in '
                             'formatting/trailing commas or added scanner comments; capture '
                             'harness unchanged between capture-added commit and current main. '
                             'Capture build version is not independently attested.',
            'runtime_clipboard_or_paste_verified': False,
            'signed_release_capture_attested': False,
            'excluded_assets': 'Archived July root raw/en files and keyboard/settings/paywall '
                               'captures are not used.'},
 'assets': [{'local_name': '01.png',
             'source_path': 'assets/store_promo/raw/en/iphone_medium/01.png',
             'sha256': '61284871127de8f3d54a4c37adc688400f03b158d09358466449bc33853361fc',
             'dimensions': [1206, 2622]},
            {'local_name': '02.png',
             'source_path': 'assets/store_promo/raw/en/iphone_medium/02.png',
             'sha256': '45b5dffa18771f5c5cd185e75fb1463781d68a0a6a71b2233cd78482bdc84de5',
             'dimensions': [1206, 2622]}],
 'slides': [{'heading': 'Find a saved text clip',
             'caption': 'Open search in ClipNest.',
             'asset': '01.png',
             'seconds': 5},
            {'heading': 'Search a word you remember',
             'caption': 'Example: Project',
             'asset': '02.png',
             'seconds': 5},
            {'heading': 'Review the matching text',
             'caption': 'ClipNest for iPhone and iPad',
             'asset': '02.png',
             'seconds': 5}],
 'metadata': {'title': 'How to Find Saved Text in ClipNest | iPhone Screenshot Guide',
              'description': 'To find saved text in ClipNest, open search in the main app and '
                             'enter a word you remember. The example shows a search for Project '
                             'and the matching Project brief clip.\n'
                             '\n'
                             'Still-screen guide using real iPhone simulator screenshots with '
                             'original demonstration text. No typing, clipboard capture, paste '
                             'action, save result, or speed demonstration is shown.\n'
                             '\n'
                             'Explore ClipNest for iPhone and iPad:\n'
                             'https://apps.apple.com/us/app/clipnest-clipboard-history/id6779928552\n'
                             '\n'
                             '#ClipNest #ClipboardHistory #Shorts',
              'format_disclosure': 'Still-screen guide · Demo text',
              'audio': 'none',
              'made_for_kids': False,
              'synthetic_media': False,
              'category': 'Education',
              'cta': 'ClipNest for iPhone and iPad · Link in description',
              'target_publish_at': '2026-10-14T09:00:00+09:00',
              'timezone': 'Asia/Seoul'},
 'authorization': {'format_approved_on': '2026-10-08',
                   'execution_approved_on': '2026-10-13',
                   'rights_basis': 'ONNELLAB-owned app UI and repository-owned demonstration data',
                   'scope': 'English screenshot-based app guide on ONNELLAB YouTube; no simulated '
                            'interaction; existing recording gate unchanged',
                   'execution_scope': 'Owner-authorized free dot-cloud ClipNest '
                                      'Python/ffmpeg/ffprobe production and tests; no separate '
                                      'Work/Codex, paid service or user computer.'}}

class GuideError(ValueError):
    pass

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise GuideError('duplicate_json_key')
            result[key] = value
        return result
    raw = Path(path).read_bytes()
    if len(raw) > 65536:
        raise GuideError('manifest_too_large')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(GuideError('nonfinite_json')))

def _validate_quivra(manifest, asset_root):
    """Pilot allowlist is intentionally narrow; do not infer new asset rights."""
    root = Path(asset_root).resolve()
    expected = {'schema_version', 'kind', 'guide_id', 'app_id', 'locale',
                'channel_id', 'source', 'assets', 'slides', 'metadata', 'authorization'}
    if set(manifest) != expected or manifest['schema_version'] != 1:
        raise GuideError('manifest_schema')
    if (manifest['kind'], manifest['app_id'], manifest['locale'], manifest['channel_id']) != (
            'screenshot_guide', 'APP-0001', 'en', CHANNEL):
        raise GuideError('guide_scope')
    if not re.fullmatch(r'quivra-file-list-[a-z0-9-]{1,40}', manifest['guide_id']):
        raise GuideError('guide_identity')
    source = manifest['source']
    if (source.get('repository'), source.get('commit')) != (SOURCE_REPO, SOURCE_COMMIT):
        raise GuideError('unapproved_source_revision')
    if source.get('source_version') != '1.0.10+85' or source.get('public_version_observed') != '1.0.10':
        raise GuideError('source_version_evidence')
    if source.get('capture_type') != 'real_app_ui_with_demonstration_files':
        raise GuideError('capture_provenance')
    if source.get('runtime_conversion_verified') is not False:
        raise GuideError('not_a_runtime_conversion_proof')
    auth = manifest['authorization']
    if auth.get('format_approved_on') != '2026-10-08' or auth.get('rights_basis') != 'ONNELLAB-owned app UI and repository-owned demonstration data':
        raise GuideError('authorization_missing')
    assets = manifest['assets']
    if not isinstance(assets, list) or len(assets) != 2:
        raise GuideError('asset_scope')
    seen = set()
    for asset in assets:
        name = asset.get('local_name')
        if name not in APPROVED_ASSETS or name in seen:
            raise GuideError('asset_not_allowlisted')
        seen.add(name)
        if asset.get('sha256') != APPROVED_ASSETS[name]:
            raise GuideError('unapproved_asset_hash')
        if asset.get('source_path') != 'assets/store_promo/raw/en/' + name:
            raise GuideError('source_path_mismatch')
        path = root / name
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise GuideError('unsafe_asset_path')
        if sha256(path) != APPROVED_ASSETS[name]:
            raise GuideError('asset_integrity')
    expected_slides = [{'heading': h, 'caption': c, 'asset': a, 'seconds': 5} for h,c,a in COPY]
    if manifest['slides'] != expected_slides:
        raise GuideError('copy_requires_review')
    m = manifest['metadata']
    if m.get('title') != TITLE or m.get('made_for_kids') is not False or m.get('synthetic_media') is not False:
        raise GuideError('metadata_scope')
    if m.get('format_disclosure') != DISCLOSURE or m.get('audio') != 'none':
        raise GuideError('disclosure_required')
    desc = m.get('description', '')
    if not isinstance(desc, str) or len(desc.encode()) > 5000 or not desc.startswith('To prepare files in Quivra,'):
        raise GuideError('description_invalid')
    if 'Static screenshots with demonstration filenames; no live conversion, completed output, or speed demonstration is shown.' not in desc:
        raise GuideError('description_disclosure_required')
    links = re.findall(r'https?://\S+', desc)
    if links != ['https://apps.apple.com/app/id6759565093',
                 'https://play.google.com/store/apps/details?id=com.onnellab.quivra2']:
        raise GuideError('unapproved_links')
    if re.search(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]', desc):
        raise GuideError('english_only')
    for term in ('guaranteed', 'fastest', '100%', 'free forever', 'perfect', 'converted successfully'):
        if term in desc.lower():
            raise GuideError('unsupported_claim')
    return {'manifest_sha256': hashlib.sha256(canonical(manifest)).hexdigest(),
            'asset_hashes': dict(APPROVED_ASSETS), 'kind': 'screenshot_guide',
            'runtime_recording_attestation': False, 'upload_authorized_by_cli': False}


ALIGNA_CONTRACT = {'schema_version': 1,
 'kind': 'screenshot_guide',
 'guide_id': 'aligna-conflicts-20261016',
 'app_id': 'APP-0006',
 'locale': 'en',
 'channel_id': 'UCXyRedrldRBl9Y35nyWoTLg',
 'source': {'repository': 'onnellab/aligna',
            'commit': '2b72a1555d0be76df91064751db240cb218ba0e3',
            'capture_manifest_path': 'assets/store_promo/evidence/capture_android.json',
            'capture_source_commit': '427f7d94dcc1c165774efa27996f691f4b3b55a7',
            'capture_source_version': '1.0.7+23',
            'reviewed_source_version': '1.1.0+26',
            'public_version_observed': '1.1.0',
            'public_version_source': 'https://play.google.com/store/apps/details?id=com.onnellab.aligna',
            'public_version_checked_at': '2026-10-15T10:07:31Z',
            'capture_type': 'real_android_emulator_ui_with_repository_demonstration_filenames',
            'provenance': 'Android emulator adb screencap, profile build, ALIGNA_SCREENSHOT_MODE '
                          'fixture. Capture 2026-10-10. Whole frame retained; not a signed-release '
                          'capture.',
            'rights': 'ONNELLAB-owned app UI and repository-authored demonstration filenames. No '
                      'user files, stock imagery, narration or music.',
            'source_parity': 'The selected conflict option and preview widgets remain '
                             'byte-identical from capture source to reviewed main. Other runtime '
                             'files changed; no claim of complete source or exact signed-release '
                             'visual parity. Public Play listing explicitly describes skipping '
                             'conflicting files.',
            'limitations': ['Screenshot is a seeded preview, not an actual rename or collision '
                            'outcome.',
                            'Capture version 1.0.7+23 predates public 1.1.0; only the '
                            'still-present setting and visible demo preview are described.'],
            'runtime_rename_verified': False,
            'signed_release_capture_attested': False},
 'assets': [{'local_name': '04.png',
             'source_path': 'assets/store_promo/raw/android/en/04.png',
             'sha256': '810c45d061b8c75434ac63bc35f96c7aa5fd80a6dd5b1534aa8d74d102781bf0',
             'dimensions': [1080, 2160]}],
 'slides': [{'heading': 'Handle matching file names',
             'caption': 'Find Skip conflicting files in Aligna.',
             'asset': '04.png',
             'seconds': 5},
            {'heading': 'Choose to skip conflicts',
             'caption': 'The switch is on in this example.',
             'asset': '04.png',
             'seconds': 5},
            {'heading': 'Review before you apply',
             'caption': 'This is a preview, not a rename result.',
             'asset': '04.png',
             'seconds': 5}],
 'metadata': {'title': 'How to Skip Conflicting File Names in Aligna | Screenshot Guide',
              'description': 'To skip files whose new names already exist, turn on Skip '
                             'conflicting files in Aligna. Review the proposed names before using '
                             'Apply.\n'
                             '\n'
                             'Still-screen guide using a real Android emulator screenshot with '
                             'repository demonstration filenames. The switch is already on in the '
                             'example. No taps, actual conflict, rename result, or speed '
                             'demonstration is shown.\n'
                             '\n'
                             'Explore Aligna for Android:\n'
                             'https://play.google.com/store/apps/details?id=com.onnellab.aligna\n'
                             '\n'
                             '#Aligna #FileRenamer #Shorts',
              'format_disclosure': 'Still-screen guide · Demo filenames',
              'audio': 'none',
              'made_for_kids': False,
              'synthetic_media': False,
              'category': 'Education',
              'cta': 'Aligna for Android · Link in description',
              'target_publish_at': '2026-10-16T09:00:00+09:00',
              'timezone': 'Asia/Seoul'},
 'authorization': {'format_approved_on': '2026-10-08',
                   'rights_basis': 'ONNELLAB-owned app UI and repository-owned demonstration data',
                   'scope': 'English screenshot-based app guide on ONNELLAB YouTube; no simulated '
                            'interaction; existing recording gate unchanged',
                   'execution_scope': 'User-requested free dot-cloud app Shorts production, '
                                      'verification, and browser scheduling; no separate '
                                      'Work/Codex or paid service.'}}

# Independently reviewed album guide; original Favorites contract remains immutable.
MELIVRA_ALBUMS_CONTRACT = {'schema_version': 1,
 'kind': 'screenshot_guide',
 'guide_id': 'melivra-albums-20261021',
 'app_id': 'APP-0007',
 'locale': 'en',
 'channel_id': 'UCXyRedrldRBl9Y35nyWoTLg',
 'source': {'repository': 'onnellab/melivra',
            'commit': '6314b685a41c690e8ccd9a080c095078ebb0db10',
            'git_tree_sha': '261cb0863ce683df5eaeb9dfc6e9afac2b6f8b62',
            'capture_manifest_path': 'assets/store_promo/raw/android/en/capture.json',
            'capture_manifest_git_blob_sha': '2baea9bd221db9f086718ee37d6da5fd51130d04',
            'capture_id': '20261010T010826Z-23651146',
            'captured_at': '2026-10-10T01:12:07.756029+00:00',
            'capture_device_kind': 'Android emulator',
            'capture_source_commit': '1341678a676ce9a2dc34888f271f1e4809182851',
            'capture_source_version': '1.0.6+142',
            'reviewed_source_version': '1.0.7+144',
            'recorded_source_digest': '2f8f7372fd4fe10f8f1ba473a8ef2ec736d7e173861263d788d165959bb0d224',
            'recorded_source_digest_independently_recomputed': False,
            'capture_test': 'integration_test/store_promo_capture_test.dart',
            'capture_test_git_blob_sha': '7e4b720db19a88d97371f363a6c23f695f527610',
            'capture_type': 'real_app_ui_with_repository_demonstration_library',
            'source_parity': 'Independently compared all lib blob SHAs at capture revision '
                             '1341678a676ce9a2dc34888f271f1e4809182851 and reviewed release source '
                             '6314b685a41c690e8ccd9a080c095078ebb0db10. Only app_env.dart differs, '
                             'solely version/build default constants (1.0.6+142 to 1.0.7+144). '
                             'Capture harness blob is unchanged. This is not signed-binary '
                             'attestation.',
            'capture_version_note': "Actual Android emulator screenshots. The capture manifest's "
                                    'real-device label does not override its emulator device_id. '
                                    'No exact signed-release-build capture attestation is claimed.',
            'runtime_playback_verified': False,
            'limitations': ['Favorites, ratings, playlists, listening history and silent WAV files '
                            'are seeded repository demonstration data.',
                            'Pixels do not prove successful import, playback, audio quality, save, '
                            'conversion, performance or user results.',
                            'Claims are limited to actual visible screen labels, not off-screen '
                            'labels in the capture manifest.'],
            'public_version_observed': '1.0.7',
            'public_version_source': 'https://play.google.com/store/apps/details?id=com.onnellab.melivra',
            'public_version_checked_at': '2026-10-19T00:06:29Z',
            'public_version_check_method': 'Live Google Play About this app dialog in dot cloud '
                                           'browser; version 1.0.7, updated October 10.',
            'rights_review': 'Capture harness drawCover creates original flat-color circles and '
                             'horizon paths; writeSilentWav creates zero-filled PCM. Titles are '
                             'repository-authored demonstration metadata. No third-party album art '
                             'or recorded music is used.'},
 'assets': [{'local_name': '2.png',
             'source_path': 'assets/store_promo/raw/android/en/2.png',
             'sha256': 'a8a160863108d27bd6b4971889b7e9584954b10d3a2551a9ef2202972322e605',
             'dimensions': [1080, 2400]}],
 'slides': [{'heading': 'Browse your music by album',
             'caption': 'Use the Albums view in Library.',
             'asset': '2.png',
             'seconds': 5},
            {'heading': 'Recognize the album',
             'caption': 'Match the title with its cover.',
             'asset': '2.png',
             'seconds': 5},
            {'heading': 'Check what is inside',
             'caption': 'See the track count and total length.',
             'asset': '2.png',
             'seconds': 5}],
 'metadata': {'title': 'How to Browse Albums in Melivra | Android Screenshot Guide',
              'description': 'To browse your music by album in Melivra, use the Albums view in '
                             'Library. Identify an album by its title and cover, then check the '
                             'track count and total duration shown below it.\n'
                             '\n'
                             'Still-screen guide using a real Android emulator screenshot with '
                             'original demonstration titles, procedural cover art and silent audio '
                             'fixtures. The screen remains stationary; no taps, playback, import, '
                             'save result, or speed demonstration is shown. Displayed times belong '
                             'to the demo library.\n'
                             '\n'
                             'Explore Melivra for Android:\n'
                             'https://play.google.com/store/apps/details?id=com.onnellab.melivra\n'
                             '\n'
                             '#Melivra #OfflineMusicPlayer #MusicLibrary #Shorts',
              'format_disclosure': 'Still-screen guide · Demo library',
              'audio': 'none',
              'made_for_kids': False,
              'synthetic_media': False,
              'category': 'Education',
              'cta': 'Melivra for Android · Link in description',
              'target_publish_at': '2026-10-21T09:00:00+09:00',
              'timezone': 'Asia/Seoul'},
 'authorization': {'format_approved_on': '2026-10-08',
                   'rights_basis': 'ONNELLAB-owned app UI and repository-owned demonstration data',
                   'scope': 'English screenshot-based app guide on ONNELLAB YouTube; no simulated '
                            'interaction; existing recording gate unchanged',
                   'execution_scope': 'Owner-authorized free dot-cloud app Shorts '
                                      'Python/ffmpeg/ffprobe production and tests, expanded to all '
                                      'apps; no separate Work/Codex, paid service or user '
                                      'computer.'}}

# Independently reviewed Papira home-screen contract.
PAPIRA_CONTRACT = {'schema_version': 1,
 'kind': 'screenshot_guide',
 'guide_id': 'papira-start-20261023',
 'app_id': 'APP-0008',
 'locale': 'en',
 'channel_id': 'UCXyRedrldRBl9Y35nyWoTLg',
 'source': {'repository': 'onnellab/papira',
            'commit': 'dcfd66693b4bc283356907574c59f90026dacbe7',
            'capture_source_commit': 'f347cefeb75f83752d0d449d039912a5d7479984',
            'capture_source_version': '2.0.3+10',
            'capture_manifest_path': 'release/capture-provenance-20261014.json',
            'capture_test': 'integration_test/store_promo_screenshot_test.dart',
            'capture_type': 'real_android_emulator_app_ui',
            'source_parity': 'GitHub compare from capture source to reviewed commit contains no '
                             'lib runtime or selected Android raw image changes. Release identity '
                             'identifies capture source and version 2.0.3+10.',
            'public_version_recorded': '2.0.3',
            'public_version_record_source': 'onnellab/onnel-content-engine data/store_versions.csv '
                                            'checked 2026-10-20T12:25:37+09:00',
            'public_listing_source': 'https://play.google.com/store/apps/details?id=com.onnellab.papira',
            'public_listing_checked_at': '2026-10-20',
            'public_listing_observation': 'Live browser confirms ONNELLAB purchase listing, '
                                          'October 16 update and current features; version number '
                                          'not exposed in inspected UI. Version 2.0.3 is '
                                          'repository store snapshot evidence, not independently '
                                          'read live.',
            'rights': 'ONNELLAB-owned app UI. Home screen captured before sample-project '
                      'injection; no manuscript, photo, third-party art, user data or audio.',
            'signed_release_capture_attested': False,
            'runtime_conversion_verified_by_video': False,
            'limitations': ['Still home screenshot only; no taps, conversion, saved result or '
                            'speed demonstration.',
                            'Android only; iOS public version remains 2.0.1.']},
 'assets': [{'local_name': '01.png',
             'source_path': 'assets/store_promo/raw/android/en/01.png',
             'sha256': '497e31dc4f2ed3db0295b79da8bddbe42616babb1f112e3a039c313bdc04fa7a',
             'dimensions': [1080, 2400]}],
 'slides': [{'heading': 'Choose how to start',
             'caption': 'Two paths from Papira’s home screen.',
             'asset': '01.png',
             'seconds': 5},
            {'heading': 'Create a book',
             'caption': 'Add a cover and table of contents.',
             'asset': '01.png',
             'seconds': 5},
            {'heading': 'Convert TXT',
             'caption': 'No cover or publishing details.',
             'asset': '01.png',
             'seconds': 5}],
 'metadata': {'title': 'How to Choose a Starting Option in Papira | Android Screenshot Guide',
              'description': 'In Papira, choose Create a book for an EPUB with a cover and table '
                             'of contents, or Convert TXT for an EPUB without a cover or '
                             'publishing details. Start with a finished TXT manuscript.\n'
                             '\n'
                             'Still-screen guide using a real Android emulator screenshot of the '
                             'app home screen. No taps, conversion, saved result, or speed '
                             'demonstration is shown. Papira is an EPUB maker, not a manuscript '
                             'editor or EPUB reader.\n'
                             '\n'
                             'Explore Papira for Android:\n'
                             'https://play.google.com/store/apps/details?id=com.onnellab.papira\n'
                             '\n'
                             '#Papira #TXTtoEPUB #EPUBMaker #Shorts',
              'format_disclosure': 'Still-screen guide · No conversion shown',
              'audio': 'none',
              'made_for_kids': False,
              'synthetic_media': False,
              'category': 'Education',
              'cta': 'Papira for Android · Link in description',
              'target_publish_at': '2026-10-23T09:00:00+09:00',
              'timezone': 'Asia/Seoul'},
 'authorization': {'format_approved_on': '2026-10-08',
                   'rights_basis': 'ONNELLAB-owned app UI',
                   'scope': 'English screenshot-based app guide on ONNELLAB YouTube; no simulated '
                            'interaction; existing recording gate unchanged',
                   'execution_scope': 'Owner-authorized free dot-cloud app Shorts '
                                      'Python/ffmpeg/ffprobe production and tests; no separate '
                                      'Work/Codex, paid service or user computer.'}}


TAGWEAVER_CONTRACT = json.loads("{\"schema_version\":1,\"kind\":\"screenshot_guide\",\"guide_id\":\"tagweaver-extra-tags-20261026\",\"app_id\":\"APP-0002\",\"locale\":\"en\",\"channel_id\":\"UCXyRedrldRBl9Y35nyWoTLg\",\"source\":{\"repository\":\"onnellab/tagweaver\",\"commit\":\"8e813af546731dbcf893b4ca1d7f0b4c47faeff6\",\"capture_source_commit\":\"826031a5d36044ba38b96c1a69807257682c5281\",\"capture_source_version\":\"2.5.4+98\",\"capture_manifest_path\":\"assets/store_promo/raw/en/android/04.capture.json\",\"capture_type\":\"real_android_emulator_app_ui\",\"source_parity\":\"Exact raw hash and native capture receipt retained. Independent reuse review for product source 0592417612d222306d37e374136e51706444fd46 version 2.5.6+100 confirms unchanged selected-screen design, context, dependencies and claims. Current main adds release evidence, not new product lib changes.\",\"public_version_recorded\":\"2.5.6\",\"public_listing_source\":\"https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2\",\"public_listing_checked_at\":\"2026-10-25\",\"public_listing_observation\":\"Live Google Play About UI showed ONNELLAB, public installation, version 2.5.6 and October 23 update.\",\"rights\":\"ONNELLAB-owned app UI and repository-authored demonstration metadata. Demo ISRC, publisher and copyright fields are fixture values, not evidence of music rights. No audio, artwork or user files used.\",\"signed_release_capture_attested\":false,\"runtime_action_verified_by_video\":false,\"limitations\":[\"Still Extra Tags destination only; no navigation, edits, deletion, save result or speed demonstration.\"]},\"assets\":[{\"local_name\":\"tagweaver-04.png\",\"source_path\":\"assets/store_promo/raw/en/android/04.png\",\"sha256\":\"5f4896d41baedcda7fac31082f9256c7617c51c3b35c90876665f5976a2b26b6\",\"dimensions\":[1080,2400]}],\"slides\":[{\"heading\":\"Review extra tags\",\"caption\":\"Read each field name and value.\",\"asset\":\"tagweaver-04.png\",\"seconds\":5},{\"heading\":\"Check the example values\",\"caption\":\"BPM 124 · Demo comment\",\"asset\":\"tagweaver-04.png\",\"seconds\":5},{\"heading\":\"A still-screen reference\",\"caption\":\"No edits or saving are shown.\",\"asset\":\"tagweaver-04.png\",\"seconds\":5}],\"metadata\":{\"title\":\"How to Review Extra Tags in TagWeaver | Android Screenshot Guide\",\"description\":\"In TagWeaver’s Extra Tags screen, review a field name and its value, such as BPM or Comment.\\n\\nStill-screen guide using a real Android emulator screenshot with repository-authored demonstration metadata. No navigation, taps, edits, deletion, saved result, or speed demonstration is shown. The example ISRC and copyright fields are demo values, not evidence of rights to a music recording.\\n\\nExplore TagWeaver for Android:\\nhttps://play.google.com/store/apps/details?id=com.onnellab.tagweaver2\\n\\n#TagWeaver #AudioTags #Shorts\",\"format_disclosure\":\"Still-screen guide · Demo metadata\",\"audio\":\"none\",\"made_for_kids\":false,\"synthetic_media\":false,\"category\":\"Education\",\"cta\":\"TagWeaver for Android · Link in description\",\"target_publish_at\":\"2026-10-26T09:00:00+09:00\",\"timezone\":\"Asia/Seoul\"},\"authorization\":{\"format_approved_on\":\"2026-10-08\",\"rights_basis\":\"ONNELLAB-owned app UI\",\"scope\":\"English screenshot-based app guide on ONNELLAB YouTube; no simulated interaction; existing recording gate unchanged\",\"execution_scope\":\"Owner approved free existing dot-cloud Python/Pillow/ffmpeg/ffprobe for October 26 and 28 Shorts source checks, tests, render, frame QA and Library only; no installs, paid services, separate Work/Codex or user computer. User message Sentinel_2ca0f146562c8191a2858e59b878ebdf.\"}}")
VAULTXT_CONTRACT = json.loads("{\"schema_version\":1,\"kind\":\"screenshot_guide\",\"guide_id\":\"vaultxt-snapshot-dates-20261028\",\"app_id\":\"APP-0003\",\"locale\":\"en\",\"channel_id\":\"UCXyRedrldRBl9Y35nyWoTLg\",\"source\":{\"repository\":\"onnellab/onnellab-text\",\"commit\":\"e5909c0f81eb6072a6aa419d4d8c52f0938b20d4\",\"capture_source_commit\":\"f17646a0a9452a3dd16510e42b1498db49e80a41\",\"capture_source_version\":\"2.0.2+68\",\"capture_manifest_path\":\"vaultxt/assets/store_promo/raw/en/android/04.capture.json\",\"capture_type\":\"real_android_emulator_app_ui\",\"source_parity\":\"Capture to reviewed main: all 128 vaultxt/lib files, Android runtime, pubspec.lock and capture test unchanged. Pubspec changes build 68 to 69. Shared paragraph_selection_chrome changes context-menu actions and positioning, not the displayed SnapshotListSheet (blob d3cbb51fdb919427c1425593afbb3e5def31e0a9); no context toolbar is shown. Screen-specific source parity only.\",\"public_version_recorded\":\"2.0.2\",\"public_listing_source\":\"https://play.google.com/store/apps/details?id=com.onnellab.vaultxt\",\"public_listing_checked_at\":\"2026-10-25\",\"public_listing_observation\":\"Live Google Play About UI showed ONNELLAB, public installation, version 2.0.2 and October 17 update; snapshot functionality is described.\",\"rights\":\"ONNELLAB-owned app UI and in-repository English Weekend Trip Plan sample. Capture harness seeds the actual document repository and two snapshots. No user document, third-party art or audio used.\",\"signed_release_capture_attested\":false,\"runtime_action_verified_by_video\":false,\"limitations\":[\"Still snapshot-list metadata only, not preview of an older document or restore success.\",\"Capture uses synthetic input; native IME unverified. Original green capture border retained.\"]},\"assets\":[{\"local_name\":\"vaultxt-04.png\",\"source_path\":\"vaultxt/assets/store_promo/raw/en/android/04.png\",\"sha256\":\"59c0136bb3affd8f0f62cca64f81d73498bed3b41924ebfee0afbcaa905699bf\",\"dimensions\":[1080,2400]}],\"slides\":[{\"heading\":\"Check snapshot dates\",\"caption\":\"Look for Created at.\",\"asset\":\"vaultxt-04.png\",\"seconds\":5},{\"heading\":\"Compare the listed times\",\"caption\":\"Dates belong to this demo document.\",\"asset\":\"vaultxt-04.png\",\"seconds\":5},{\"heading\":\"Before choosing Restore\",\"caption\":\"No restoration is shown.\",\"asset\":\"vaultxt-04.png\",\"seconds\":5}],\"metadata\":{\"title\":\"How to Check Snapshot Dates in VaultXT | Android Screenshot Guide\",\"description\":\"In VaultXT’s Snapshots panel, check the creation date and time shown for each entry before choosing Restore.\\n\\nStill-screen guide using a real Android emulator screenshot with an original demonstration document and seeded snapshots. No taps, snapshot creation, preview of older document contents, restoration, or speed demonstration is shown. The green border is part of the original capture.\\n\\nExplore VaultXT for Android:\\nhttps://play.google.com/store/apps/details?id=com.onnellab.vaultxt\\n\\n#VaultXT #TextEditor #Shorts\",\"format_disclosure\":\"Still-screen guide · Demo document\",\"audio\":\"none\",\"made_for_kids\":false,\"synthetic_media\":false,\"category\":\"Education\",\"cta\":\"VaultXT for Android · Link in description\",\"target_publish_at\":\"2026-10-28T09:00:00+09:00\",\"timezone\":\"Asia/Seoul\"},\"authorization\":{\"format_approved_on\":\"2026-10-08\",\"rights_basis\":\"ONNELLAB-owned app UI\",\"scope\":\"English screenshot-based app guide on ONNELLAB YouTube; no simulated interaction; existing recording gate unchanged\",\"execution_scope\":\"Owner approved free existing dot-cloud Python/Pillow/ffmpeg/ffprobe for October 26 and 28 Shorts source checks, tests, render, frame QA and Library only; no installs, paid services, separate Work/Codex or user computer. User message Sentinel_2ca0f146562c8191a2858e59b878ebdf.\"}}")

SEGRA_CONTRACT = json.loads("{\"schema_version\":1,\"kind\":\"screenshot_guide\",\"guide_id\":\"segra-file-order-20261030\",\"app_id\":\"APP-0004\",\"locale\":\"en\",\"channel_id\":\"UCXyRedrldRBl9Y35nyWoTLg\",\"source\":{\"repository\":\"onnellab/segra\",\"commit\":\"e1fdc2367255478eccba4da1f0aaefc1367e5719\",\"capture_source_commit\":\"e62c96a3771f8f594414cc9839b5d81c745fdd27\",\"capture_source_version\":\"1.0.6+76\",\"capture_manifest_path\":\"assets/store_promo/native_campaign_20261020.json\",\"capture_type\":\"real_android_native_pixelcopy_app_ui\",\"source_parity\":\"{\\\"audio_merge_tree_sha\\\":\\\"290d6e1e88b2759ba05bbc93bfd7db25b906b251\\\",\\\"identical_between_capture_and_release\\\":[\\\"lib/features/audio_merge (complete subtree)\\\",\\\"lib/core/constants/app_copy.dart\\\",\\\"lib/core/l10n/l10n_x.dart\\\",\\\"lib/core/theme/segra_colors.dart\\\",\\\"lib/core/widgets/app_scaffold.dart\\\",\\\"lib/l10n/app_localizations_en.dart\\\",\\\"pubspec.lock\\\"],\\\"limits\\\":\\\"Screen-specific source evidence only. Native media and audio-video processing changes exist; no execution/output or signed-binary equivalence claim.\\\"}\",\"reviewed_release_commit\":\"601f5e895be63917b29d28aa844b9a52e5fc751e\",\"public_version_recorded\":\"1.0.7\",\"public_listing_source\":\"https://play.google.com/store/apps/details?id=com.onnellab.segra\",\"public_listing_checked_at\":\"2026-10-27T09:18:41Z\",\"public_listing_observation\":\"Live Play About showed public Android 1.0.7, ONNELLAB and October 23 update.\",\"rights\":\"ONNELLAB app UI and repository-authored merge_sample_01.mp3, merge_sample_02.wav, merge_sample_03.mp3 fixture names. Harness creates artificial repeated-byte files, not licensed music or valid audio playback evidence. No audio included.\",\"signed_release_capture_attested\":false,\"runtime_action_verified_by_video\":false,\"limitations\":[\"Native capture-only debug app, source 1.0.6+76; screen-specific source parity to release/1.0.7-77 only.\",\"Still numbered File order list; no selection, reorder, playback, merge, save or speed demonstration.\"]},\"assets\":[{\"local_name\":\"segra-merge.png\",\"source_path\":\"assets/store_promo/raw/en/android_phone/merge.png\",\"sha256\":\"967c8fbfddca79c12b5fa4aba2d7be3f477793b9a40b32545986d1ae35e409fa\",\"dimensions\":[1080,2400]}],\"slides\":[{\"seconds\":5,\"heading\":\"Check the file order\",\"caption\":\"Read the numbered list.\",\"asset\":\"segra-merge.png\"},{\"seconds\":5,\"heading\":\"Match each number to a file\",\"caption\":\"This example contains three demo files.\",\"asset\":\"segra-merge.png\"},{\"seconds\":5,\"heading\":\"Before merging\",\"caption\":\"No merge or saved result is shown.\",\"asset\":\"segra-merge.png\"}],\"metadata\":{\"title\":\"How to Check File Order in Segra | Android Screenshot Guide\",\"description\":\"In Segra’s Audio Merge screen, check the numbered File order list before choosing Merge and save.\\n\\nStill-screen guide using a real Android native capture with repository-authored demonstration filenames. No file selection, reordering, playback, merging, saved result, or speed demonstration is shown. The sample files are capture fixtures, not music recordings.\\n\\nExplore Segra for Android:\\nhttps://play.google.com/store/apps/details?id=com.onnellab.segra\\n\\n#Segra #AudioMerge #Shorts\",\"format_disclosure\":\"Still-screen guide · Demo filenames\",\"audio\":\"none\",\"made_for_kids\":false,\"synthetic_media\":false,\"category\":\"Education\",\"cta\":\"Segra for Android · Link in description\",\"target_publish_at\":\"2026-10-30T09:00:00+09:00\",\"timezone\":\"Asia/Seoul\"},\"authorization\":{\"format_approved_on\":\"2026-10-08\",\"rights_basis\":\"ONNELLAB-owned app UI\",\"scope\":\"English screenshot-based app guide on ONNELLAB YouTube; no simulated interaction; existing recording gate unchanged\",\"execution_scope\":\"One Segra file-order guide only: existing free dot-cloud Python/Pillow/ffmpeg/ffprobe, tests, render, QA and Library. User approval Sentinel_de168794344c8191a5249929568e2dd8 at 2026-10-27T09:50:40Z to specific request Sentinel_2f0ed59e4ea48191848bfb744feab0f0. No installs, paid services, separate Work/Codex or user computer.\"}}")

MELIVRA_EQUALIZER_CONTRACT = json.loads("{\"schema_version\":1,\"kind\":\"screenshot_guide\",\"guide_id\":\"melivra-equalizer-location-20261102\",\"app_id\":\"APP-0007\",\"locale\":\"en\",\"channel_id\":\"UCXyRedrldRBl9Y35nyWoTLg\",\"source\":{\"repository\":\"onnellab/melivra\",\"commit\":\"d2d1a281ecae94afd78e184c24419ac15bce6e2c\",\"capture_source_commit\":\"d110bb09dd31395f7c20447eaf29f6d270a90a5d\",\"capture_version\":\"1.0.8+145\",\"capture_variant\":\"integration-test-debug-production-id\",\"capture_receipt_path\":\"assets/store_promo/raw/en/android/05.capture.json\",\"capture_receipt_git_blob_sha\":\"c7bd52b968a8162232e14a90f8cd62d2faf92a8f\",\"capture_method\":\"adb native Android emulator capture\",\"device_id\":\"emulator-5570\",\"public_version_observed\":\"1.0.8\",\"public_version_checked_at\":\"2026-10-29T09:51:27Z\",\"public_version_source\":\"https://play.google.com/store/apps/details?id=com.onnellab.melivra\",\"rights_review\":\"Repository-authored demo metadata and original procedural cover art; silent WAV fixtures. No third-party music or artwork. No soundtrack in guide.\",\"limitations\":[\"Capture is integration-test debug production-ID build 1.0.8+145, not signed-public-binary attestation.\",\"Static setting location only; no taps, preset changes, playback, sound quality, purchases or performance demonstrated.\",\"Flat is the demonstration state, not a current user setting.\"]},\"assets\":[{\"local_name\":\"05.png\",\"source_path\":\"assets/store_promo/raw/en/android/05.png\",\"sha256\":\"27bf17b69677932ae8e758e2f67586cab50e560f4ecd8ca6557ca38724c3f62b\",\"dimensions\":[1080,2400]}],\"slides\":[{\"heading\":\"Find the equalizer setting\",\"caption\":\"In Settings, look under Playback.\",\"asset\":\"05.png\",\"seconds\":5},{\"heading\":\"Look for Equalizer Preset\",\"caption\":\"The example shows Flat beneath it.\",\"asset\":\"05.png\",\"seconds\":5},{\"heading\":\"Melivra for Android\",\"caption\":\"Find the app link in the description.\",\"asset\":\"05.png\",\"seconds\":5}],\"metadata\":{\"title\":\"Where Is the Equalizer in Melivra? | Android Screenshot Guide\",\"description\":\"In Melivra Settings, find Equalizer Preset under Playback. The still-screen example shows Flat beneath the setting.\\n\\nStill-screen guide using a real Android emulator capture of Melivra 1.0.8+145 with an original demonstration library. No taps, preset changes, playback, audio effect, purchase, or speed demonstration is shown. Flat is the captured example state, not a recommendation or a current user setting. The video has no audio.\\n\\nExplore Melivra for Android:\\nhttps://play.google.com/store/apps/details?id=com.onnellab.melivra\\n\\n#Melivra #Equalizer #OfflineMusicPlayer #Shorts\",\"format_disclosure\":\"Still-screen guide · Demo library\",\"audio\":\"none\",\"made_for_kids\":false,\"synthetic_media\":false,\"category\":\"Education\",\"cta\":\"Melivra for Android · Link in description\",\"target_publish_at\":\"2026-11-02T09:00:00+09:00\",\"timezone\":\"Asia/Seoul\"},\"authorization\":{\"format_approved_on\":\"2026-10-08\",\"rights_basis\":\"ONNELLAB-owned UI and repository-authored fixtures\",\"scope\":\"English still-screen guide on approved ONNELLAB channel only\",\"execution_scope\":\"Explicit Melivra-only free dot cloud Python/ffmpeg/ffprobe exception; no other app execution, paid service, Work/Codex, or user computer.\"}}")

def validate(manifest, asset_root):
    """Dispatch only independently reviewed per-app still-screen contracts."""
    if isinstance(manifest, dict) and manifest.get('app_id') in ('APP-0002', 'APP-0003', 'APP-0004'):
        contract = SEGRA_CONTRACT if manifest['app_id'] == 'APP-0004' else TAGWEAVER_CONTRACT if manifest['app_id'] == 'APP-0002' else VAULTXT_CONTRACT
        if canonical(manifest) != canonical(contract):
            raise GuideError('guide_scope_new_manifest_requires_review')
        root = Path(asset_root).resolve()
        hashes = {}
        for asset in contract['assets']:
            name = asset['local_name']
            path = root / name
            if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
                raise GuideError('unsafe_asset_path')
            if sha256(path) != asset['sha256']:
                raise GuideError('asset_integrity')
            hashes[name] = asset['sha256']
        return {'manifest_sha256': hashlib.sha256(canonical(manifest)).hexdigest(),
                'asset_hashes': hashes, 'kind': 'screenshot_guide',
                'runtime_recording_attestation': False, 'upload_authorized_by_cli': False}
    if isinstance(manifest, dict) and manifest.get('app_id') in ('APP-0007', 'APP-0005', 'APP-0006', 'APP-0008'):
        clipnest = manifest['app_id'] == 'APP-0005'
        contract = MELIVRA_EQUALIZER_CONTRACT if manifest.get('guide_id') == 'melivra-equalizer-location-20261102' else PAPIRA_CONTRACT if manifest['app_id'] == 'APP-0008' else MELIVRA_ALBUMS_CONTRACT if manifest.get('guide_id') == 'melivra-albums-20261021' else ALIGNA_CONTRACT if manifest['app_id'] == 'APP-0006' else CLIPNEST_CONTRACT if clipnest else MELIVRA_CONTRACT
        if canonical(manifest) != canonical(contract):
            raise GuideError('papira_manifest_requires_review' if manifest['app_id'] == 'APP-0008' else 'aligna_manifest_requires_review' if manifest['app_id'] == 'APP-0006' else 'clipnest_manifest_requires_review' if clipnest else 'melivra_manifest_requires_review')
        root = Path(asset_root).resolve()
        hashes = {}
        for asset in contract['assets']:
            name = asset['local_name']
            path = root / name
            if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
                raise GuideError('unsafe_asset_path')
            if sha256(path) != asset['sha256']:
                raise GuideError('asset_integrity')
            hashes[name] = asset['sha256']
        return {'manifest_sha256': hashlib.sha256(canonical(manifest)).hexdigest(),
                'asset_hashes': hashes, 'kind': 'screenshot_guide',
                'runtime_recording_attestation': False, 'upload_authorized_by_cli': False}
    return _validate_quivra(manifest, asset_root)


def render(manifest, asset_root, output):
    evidence = validate(manifest, asset_root)
    tagweaver = manifest['app_id'] == 'APP-0002'
    vaultxt = manifest['app_id'] == 'APP-0003'
    segra = manifest['app_id'] == 'APP-0004'
    new_guide = tagweaver or vaultxt or segra
    papira = manifest['app_id'] == 'APP-0008'
    aligna = manifest['app_id'] == 'APP-0006'
    melivra = manifest['app_id'] == 'APP-0007'
    clipnest = manifest['app_id'] == 'APP-0005'
    output = Path(output)
    if output.exists():
        raise GuideError('output_exists_preserve_prior_artifact')
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise GuideError('pillow_render_dependency_missing') from None
    # Source geometry is a read-only preflight: reject before allocating output,
    # loading host-specific fonts or invoking any renderer/encoder.
    expected_source_size = ((1080, 2160) if aligna else (1206, 2622) if clipnest
                            else (1080, 2400) if melivra or papira or new_guide
                            else (1080, 1920))
    for slide in manifest['slides']:
        try:
            with Image.open(Path(asset_root) / slide['asset']) as source:
                if source.size != expected_source_size:
                    raise GuideError('source_geometry_changed')
        except OSError as error:
            raise GuideError('source_image_unreadable') from error
    # Same approved DejaVu faces on Linux and macOS. Never silently use
    # arbitrary platform fonts: changed metrics could invalidate visual QA.
    font_locations = (
        Path('/usr/share/fonts/truetype/dejavu'),
        Path.home() / 'Library' / 'Fonts',
        Path('/Library/Fonts'),
    )
    font_root = next((root for root in font_locations
                      if (root / 'DejaVuSans.ttf').is_file()
                      and (root / 'DejaVuSans-Bold.ttf').is_file()), None)
    if font_root is None:
        raise GuideError('approved_dejavu_fonts_missing')
    output.mkdir(parents=True)
    regular = lambda size: ImageFont.truetype(str(font_root / 'DejaVuSans.ttf'), size)
    bold = lambda size: ImageFont.truetype(str(font_root / 'DejaVuSans-Bold.ttf'), size)
    frames = []
    text_bounds = []
    for index, slide in enumerate(manifest['slides']):
        canvas = Image.new('RGB', (1080, 1920), '#fbfaf7')
        draw = ImageDraw.Draw(canvas)
        def center(text, y, font, color='#353041'):
            box = draw.textbbox((0,0), text, font=font)
            width = box[2] - box[0]
            if width > 960:
                raise GuideError('text_exceeds_safe_width')
            position = ((1080-width)/2, y)
            bounds = draw.textbbox(position, text, font=font)
            if bounds[0] < 60 or bounds[2] > 1020 or bounds[1] < 64 or bounds[3] > 1880:
                raise GuideError('text_outside_safe_bounds')
            text_bounds.append({'slide': index+1, 'text': text, 'bbox': list(bounds)})
            draw.text(position, text, font=font, fill=color)
        draw.rounded_rectangle((64,64,1016,126), radius=25, fill='#eae4f5')
        center('SEGRA · SCREENSHOT GUIDE' if segra else 'TAGWEAVER · SCREENSHOT GUIDE' if tagweaver else 'VAULTXT · SCREENSHOT GUIDE' if vaultxt else 'PAPIRA · SCREENSHOT GUIDE' if papira else 'ALIGNA · SCREENSHOT GUIDE' if aligna else 'CLIPNEST · SCREENSHOT GUIDE' if clipnest else 'MELIVRA · SCREENSHOT GUIDE' if melivra else 'QUIVRA · SCREENSHOT GUIDE', 77, bold(30))
        center(slide['heading'], 166, bold(48))
        center(slide['caption'], 235, regular(32), '#645c74')
        source = Image.open(Path(asset_root) / slide['asset']).convert('RGB')
        if source.size != expected_source_size:
            raise GuideError('source_geometry_changed')
        # Entire screenshot, uniformly scaled. No crop, synthetic taps or UI edits.
        size = (675,1350) if aligna else (603,1311) if clipnest else (621,1380) if melivra or papira or new_guide else (756,1344)
        x, y = (202,320) if aligna else (238,330) if clipnest else (229,300) if melivra or papira or new_guide else (162,320)
        source = source.resize(size, Image.Resampling.LANCZOS)
        canvas.paste(source,(x,y))
        draw.rounded_rectangle((x-3,y-3,x+size[0]+3,y+size[1]+3), radius=3, outline='#d8cdeb', width=3)
        center(manifest['metadata']['format_disclosure'], 1721, regular(31), '#645c74')
        center(manifest['metadata']['cta'] if clipnest or aligna or papira or new_guide else 'Melivra for Android · Link in description' if melivra else 'App Store & Google Play links in the description', 1783, regular(29))
        center('ONNELLAB', 1841, bold(26), '#8c839e')
        frame = output / f'slide-{index+1}.png'
        canvas.save(frame)
        frames.append(frame)
    concat = output / 'frames.txt'
    concat.write_text(''.join(f"file '{p.name}'\nduration 5\n" for p in frames) + f"file '{frames[-1].name}'\n")
    video = output / (manifest['guide_id'] + '.mp4')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i',str(concat),
                    '-t','15','-vf','fps=30','-frames:v','450','-an','-c:v','libx264','-preset','medium',
                    '-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],
                   check=True, timeout=180)
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format',
                                               '-of','json',str(video)],timeout=30))
    streams = probe['streams']
    s = streams[0]
    if len(streams)!=1 or (s['codec_name'],s['width'],s['height'],s['r_frame_rate'],s.get('pix_fmt')) != ('h264',1080,1920,'30/1','yuv420p'):
        raise GuideError('render_geometry_or_audio')
    if abs(float(probe['format']['duration'])-15)>0.001 or int(s.get('nb_frames', 0)) != 450:
        raise GuideError('render_duration')
    evidence.update(video_file=video.name, video_sha256=sha256(video),
                    seconds=15, width=1080, height=1920, fps=30, audio=False,
                    slide_sha256={p.name:sha256(p) for p in frames},
                    text_bounds=text_bounds)
    (output/'render-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify','render'])
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        m=load(args.manifest)
        if args.command=='render' and args.output is None:
            raise GuideError('output_required')
        result=render(m,args.assets,args.output) if args.command=='render' else validate(m,args.assets)
        print(json.dumps(result,indent=2))
    except (GuideError,OSError,subprocess.SubprocessError,KeyError,TypeError,ValueError) as exc:
        print(json.dumps({'status':'blocked','error':str(exc) if isinstance(exc,GuideError) else 'guide_operation_failed'}))
        return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())





