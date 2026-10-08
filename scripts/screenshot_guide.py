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

def validate(manifest, asset_root):
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

def render(manifest, asset_root, output):
    from PIL import Image, ImageDraw, ImageFont
    evidence = validate(manifest, asset_root)
    output = Path(output)
    if output.exists():
        raise GuideError('output_exists_preserve_prior_artifact')
    output.mkdir(parents=True)
    font_root = Path('/usr/share/fonts/truetype/dejavu')
    regular = lambda size: ImageFont.truetype(str(font_root / 'DejaVuSans.ttf'), size)
    bold = lambda size: ImageFont.truetype(str(font_root / 'DejaVuSans-Bold.ttf'), size)
    frames = []
    for index, slide in enumerate(manifest['slides']):
        canvas = Image.new('RGB', (1080, 1920), '#fbfaf7')
        draw = ImageDraw.Draw(canvas)
        def center(text, y, font, color='#353041'):
            box = draw.textbbox((0,0), text, font=font)
            width = box[2] - box[0]
            if width > 960:
                raise GuideError('text_exceeds_safe_width')
            draw.text(((1080-width)/2,y), text, font=font, fill=color)
        draw.rounded_rectangle((64,64,1016,126), radius=25, fill='#eae4f5')
        center('QUIVRA · SCREENSHOT GUIDE', 77, bold(30))
        center(slide['heading'], 166, bold(48))
        center(slide['caption'], 235, regular(32), '#645c74')
        source = Image.open(Path(asset_root) / slide['asset']).convert('RGB')
        if source.size != (1080,1920):
            raise GuideError('source_geometry_changed')
        # Entire screenshot, uniformly scaled. No crop, synthetic taps or UI edits.
        source = source.resize((756,1344), Image.Resampling.LANCZOS)
        canvas.paste(source,(162,320))
        draw.rounded_rectangle((159,317,921,1667), radius=3, outline='#d8cdeb', width=3)
        center(DISCLOSURE, 1721, regular(31), '#645c74')
        center('App Store & Google Play links in the description', 1783, regular(29))
        center('ONNELLAB', 1841, bold(26), '#8c839e')
        frame = output / f'slide-{index+1}.png'
        canvas.save(frame)
        frames.append(frame)
    concat = output / 'frames.txt'
    concat.write_text(''.join(f"file '{p.name}'\nduration 5\n" for p in frames) + f"file '{frames[-1].name}'\n")
    video = output / (manifest['guide_id'] + '.mp4')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i',str(concat),
                    '-t','15','-r','30','-an','-c:v','libx264','-preset','medium',
                    '-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],
                   check=True, timeout=180)
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format',
                                               '-of','json',str(video)],timeout=30))
    streams = probe['streams']
    s = streams[0]
    if len(streams)!=1 or (s['codec_name'],s['width'],s['height'],s['r_frame_rate']) != ('h264',1080,1920,'30/1'):
        raise GuideError('render_geometry_or_audio')
    if abs(float(probe['format']['duration'])-15)>0.05:
        raise GuideError('render_duration')
    evidence.update(video_file=video.name, video_sha256=sha256(video),
                    seconds=15, width=1080, height=1920, fps=30, audio=False,
                    slide_sha256={p.name:sha256(p) for p in frames})
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
