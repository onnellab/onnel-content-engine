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


def validate(manifest, asset_root):
    """Dispatch only independently reviewed per-app still-screen contracts."""
    if isinstance(manifest, dict) and manifest.get('app_id') in ('APP-0007', 'APP-0005'):
        clipnest = manifest['app_id'] == 'APP-0005'
        contract = CLIPNEST_CONTRACT if clipnest else MELIVRA_CONTRACT
        if canonical(manifest) != canonical(contract):
            raise GuideError('clipnest_manifest_requires_review' if clipnest else 'melivra_manifest_requires_review')
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
    melivra = manifest['app_id'] == 'APP-0007'
    clipnest = manifest['app_id'] == 'APP-0005'
    output = Path(output)
    if output.exists():
        raise GuideError('output_exists_preserve_prior_artifact')
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise GuideError('pillow_render_dependency_missing') from None
    output.mkdir(parents=True)
    font_root = Path('/usr/share/fonts/truetype/dejavu')
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
        center('CLIPNEST · SCREENSHOT GUIDE' if clipnest else 'MELIVRA · SCREENSHOT GUIDE' if melivra else 'QUIVRA · SCREENSHOT GUIDE', 77, bold(30))
        center(slide['heading'], 166, bold(48))
        center(slide['caption'], 235, regular(32), '#645c74')
        source = Image.open(Path(asset_root) / slide['asset']).convert('RGB')
        if source.size != ((1206,2622) if clipnest else (1080,2400) if melivra else (1080,1920)):
            raise GuideError('source_geometry_changed')
        # Entire screenshot, uniformly scaled. No crop, synthetic taps or UI edits.
        size = (603,1311) if clipnest else (621,1380) if melivra else (756,1344)
        x, y = (238,330) if clipnest else (229,300) if melivra else (162,320)
        source = source.resize(size, Image.Resampling.LANCZOS)
        canvas.paste(source,(x,y))
        draw.rounded_rectangle((x-3,y-3,x+size[0]+3,y+size[1]+3), radius=3, outline='#d8cdeb', width=3)
        center(manifest['metadata']['format_disclosure'], 1721, regular(31), '#645c74')
        center(manifest['metadata']['cta'] if clipnest else 'Melivra for Android · Link in description' if melivra else 'App Store & Google Play links in the description', 1783, regular(29))
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


