#!/usr/bin/env python3
"""Prepare public-history evidence, never a slot completion or upload receipt.

Default is offline stdout only. --check-public performs unauthenticated oEmbed
GETs; --output saves a proposal explicitly. No coordinator/queue/credential use.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = 'UCXyRedrldRBl9Y35nyWoTLg'


def public_observation(video_id, *, fetch=urlopen, now=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('invalid_video_id')
    url = 'https://www.youtube.com/watch?v=' + video_id
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    endpoint = 'https://www.youtube.com/oembed?' + urlencode({'url': url, 'format': 'json'})
    try:
        with fetch(endpoint, timeout=25) as response:
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                raise ValueError('invalid_public_response')
            body = json.loads(raw)
        author = urlsplit(body.get('author_url', ''))
        if (author.scheme != 'https' or author.hostname not in {'youtube.com', 'www.youtube.com'}
                or author.username or author.password
                or author.path.rstrip('/').casefold() not in {'/@onnellab', '/channel/' + CHANNEL.casefold()}
                or body.get('author_name', '').casefold() != 'onnellab'
                or not isinstance(body.get('title'), str) or not body['title']):
            raise ValueError('public_author_identity_mismatch')
        return {'status': 'observed', 'checked_at': stamp, 'source_url': endpoint,
                'http_status': 200, 'title': body['title'], 'author_name': body['author_name'],
                'author_url': body['author_url']}
    except Exception:
        # Public lookup failure is unknown, never proof of deletion or a failed upload.
        return {'status': 'unverified', 'checked_at': stamp, 'source_url': endpoint,
                'reason': 'public_lookup_unavailable_or_identity_mismatch'}


def build_proposal(snapshot, mapping, *, observations=None, snapshot_sha256='', now=None):
    profile = snapshot.get('profiles', {}).get('onnellab', {})
    if profile.get('channel', {}).get('id') != CHANNEL or mapping.get('channel_id') != CHANNEL:
        raise ValueError('onnellab_channel_mismatch')
    if mapping.get('schema_version') != 1:
        raise ValueError('mapping_schema_invalid')
    videos = profile.get('videos', [])
    if not isinstance(videos, list) or len(videos) > 1000:
        raise ValueError('snapshot_videos_invalid')
    rows, seen = [], set()
    for video in videos:
        video_id = video.get('video', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id) or video_id in seen:
            raise ValueError('invalid_or_duplicate_video_id')
        seen.add(video_id)
        app = mapping.get('mappings', {}).get(video_id)
        if app and (not re.fullmatch(r'APP-\d{4}', app.get('app_id', '')) or not app.get('basis')):
            raise ValueError('invalid_app_mapping')
        observation = (observations or {}).get(video_id, {'status': 'not_checked'})
        match = observation.get('status') == 'observed' and observation.get('title') == video.get('title')
        rows.append({'video_id': video_id, 'video_url': 'https://www.youtube.com/watch?v=' + video_id,
                     'snapshot_title': video.get('title'), 'proposed_app_mapping': app,
                     'public_oembed_observation': observation, 'snapshot_title_matches_public': bool(match),
                     'published_at': None, 'published_at_evidence': None,
                     'provider_channel_identity_verified': False,
                     'provider_privacy_status': 'unknown', 'upload_receipt_available': False})
    return {'schema_version': 1, 'kind': 'public_video_history_proposal',
            'channel_id': CHANNEL, 'generated_at': (now or datetime.now(timezone.utc)).isoformat(),
            'snapshot_generated_at': snapshot.get('generated_at'), 'snapshot_sha256': snapshot_sha256,
            'snapshot_video_count': profile.get('statistics', {}).get('videoCount'),
            'scope': 'Videos in the supplied analytics snapshot; not a complete channel inventory.',
            'import_ready': False, 'claim_slots': [], 'videos': rows,
            'blockers': ['published_at_evidence_missing', 'provider_identity_and_visibility_not_verified',
                         'full_channel_inventory_not_reconciled', 'history_import_schema_not_implemented'],
            'constraints': ['Never mark a coordination slot completed from this proposal.',
                            'Public oEmbed does not distinguish public from unlisted visibility.',
                            'Snapshot generation/report dates are not video publication dates.',
                            'Keep eventual verified history separate from upload/slot receipts.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'data/youtube_ops_snapshot.json')
    parser.add_argument('--mapping', type=Path, default=ROOT / 'data/video_history_app_mapping.json')
    parser.add_argument('--check-public', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    snapshot = json.loads(raw)
    mapping = json.loads(args.mapping.read_text(encoding='utf-8'))
    proposal = build_proposal(snapshot, mapping, snapshot_sha256=hashlib.sha256(raw).hexdigest())
    if args.check_public:
        observations = {row['video_id']: public_observation(row['video_id']) for row in proposal['videos']}
        proposal = build_proposal(snapshot, mapping, observations=observations,
                                  snapshot_sha256=hashlib.sha256(raw).hexdigest())
    text = json.dumps(proposal, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        # New files only: cannot replace an existing receipt/history accidentally.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
