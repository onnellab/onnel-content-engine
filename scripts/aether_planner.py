#!/usr/bin/env python3
"""Offline metadata planning. No music generation, audio-quality claim or upload."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from short_video_pipeline import VideoError, load_json

CATALOG = Path(__file__).resolve().parents[1] / 'data/aether_catalog.json'
THEMES = {
    'open_roads': ('Roads Between Distant Kingdoms', {'road','roads','path','fields','field','meadow','meadows','hill','hills','valley','travel','travelers','journey','bridge','highlands','ridge','grassland','grasslands'}),
    'lantern_towns': ('An Evening Among Lantern Towns', {'town','village','harbor','tavern','inn','lantern','lanterns','city','library'}),
    'starlit_rest': ('Rest Beneath the Wandering Stars', {'night','starlight','stars','moon','moonlight','moonlit','campfire','fireflies','aurora','auroras','starlit'}),
    'woodland_water': ('Where Woodland Waters Wander', {'forest','woodland','pines','brook','river','creek','lake','garden','orchard','rain'}),
}

def normalized(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', value).casefold()))

def tokens(value):
    return set(normalized(value).split())

def identifier(title):
    return hashlib.sha256(title.encode()).hexdigest()[:16]

def read_catalog(path=CATALOG):
    data = load_json(path, limit=2 * 1024 * 1024)
    rows = data.get('songs')
    if data.get('schema_version') != 1 or not isinstance(rows, list) or len(rows) != data.get('declared_count') or not 1 <= len(rows) <= 10000:
        raise VideoError('invalid_aether_catalog')
    out = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'title','style','duration_seconds'}:
            raise VideoError('invalid_aether_catalog_row')
        if any(not isinstance(row[k], str) or not row[k].strip() or len(row[k]) > 5000 for k in ('title','style')):
            raise VideoError('invalid_aether_catalog_text')
        duration = row['duration_seconds']
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 10 <= duration <= 900:
            raise VideoError('invalid_aether_catalog_duration')
        out.append({**row, 'id': identifier(row['title'])})
    if len({x['id'] for x in out}) != len(out):
        raise VideoError('duplicate_catalog_title')
    return out

def inspect_candidate(title, style, songs):
    if not all(isinstance(x, str) and x.strip() and len(x) <= 5000 for x in (title, style)):
        raise VideoError('candidate_title_and_style_required')
    incoming = tokens(style)
    ranked = []
    for row in songs:
        other = tokens(row['style'])
        ranked.append({'id': row['id'], 'title': row['title'],
            'metadata_token_overlap': round(len(incoming & other) / max(1, len(incoming | other)), 4)})
    exact_title = any(normalized(title) == normalized(row['title']) for row in songs)
    exact_style = any(normalized(style) == normalized(row['style']) for row in songs)
    return {'title_duplicate': exact_title, 'style_duplicate': exact_style,
        'nearest_metadata': sorted(ranked, key=lambda x: (-x['metadata_token_overlap'], x['id']))[:3],
        'metadata_gate': 'rejected' if exact_title or exact_style else 'requires_audio_review',
        'audio_originality': 'not_evaluated', 'publishable': False}

def timeline(rows, fade=2):
    if not rows or type(fade) not in (int, float) or not math.isfinite(fade) or not 0 <= fade <= 3:
        raise VideoError('invalid_compilation_crossfade')
    chapters = []
    cursor = 0.0
    for index, row in enumerate(rows):
        duration = row['duration_seconds']
        if type(duration) not in (int,float) or not math.isfinite(duration) or duration < max(10, 2 * fade):
            raise VideoError('invalid_compilation_duration')
        chapters.append({'id': row['id'], 'title': row['title'], 'start_seconds': round(cursor, 3),
            'timestamp': f'{int(cursor)//60:02d}:{int(cursor)%60:02d}'})
        cursor += duration - (fade if index < len(rows)-1 else 0)
    return chapters, round(cursor, 3)

def plan(songs, theme='open_roads', *, history=(), target=1800, tolerance=60, fade=2):
    if theme not in THEMES or type(target) is not int or not 60 <= target <= 3600 or type(tolerance) is not int or not 0 <= tolerance <= 120 or type(fade) is not int or not 0 <= fade <= 3:
        raise VideoError('invalid_compilation_plan_options')
    used = {track for entry in history[-2:] for track in entry.get('track_ids', [])}
    previous_sets = {frozenset(entry.get('track_ids', [])) for entry in history}
    title, keywords = THEMES[theme]
    eligible = [(row, len(tokens(row['title'] + ' ' + row['style']) & keywords)) for row in songs if row['id'] not in used]
    # Whole-track subset selection. Every state retains one best thematic match.
    states = {(0, 0): (0, ())}
    for row, relevance in sorted(eligible, key=lambda x: x[0]['id']):
        if not relevance:
            continue
        cost = round(row['duration_seconds'] - fade)
        update = dict(states)
        for (seconds, count), (score, picked) in states.items():
            key = seconds + cost, count + 1
            if key[0] > target + tolerance - fade or key[1] > 20:
                continue
            candidate = score + relevance, picked + (row['id'],)
            if key not in update or candidate[0] > update[key][0]:
                update[key] = candidate
        states = update
    by_id = {x['id']: x for x in songs}
    options = []
    for (seconds, count), (score, picked) in states.items():
        if count < 3 or frozenset(picked) in previous_sets:
            continue
        rows = [by_id[key] for key in picked]
        chapters, actual = timeline(rows, fade)
        if abs(actual - target) <= tolerance:
            options.append((abs(actual - target), -score, picked))
    if not options:
        raise VideoError('insufficient_coherent_tracks_for_target')
    picked = min(options)[2]
    rows = [by_id[key] for key in picked]
    # Title cues are only an editorial ordering heuristic, not measured energy.
    def order(row):
        title_tokens = tokens(row['title'])
        return (2 if title_tokens & {'home','last','evening'} else 0 if title_tokens & {'morning','dawn','first','gate'} else 1, row['id'])
    rows.sort(key=order)
    chapters, duration = timeline(rows, fade)
    track_ids = [x['id'] for x in rows]
    return {'schema_version': 1, 'profile': 'aether_inn', 'content_type': 'aether_compilation',
        'theme': theme, 'title': title, 'track_ids': track_ids, 'tracks': rows, 'crossfade_seconds': fade,
        'target_seconds': target, 'tolerance_seconds': tolerance, 'estimated_duration_seconds': duration,
        'chapters': chapters, 'audio_measured': False, 'publishable': False,
        'set_fingerprint': hashlib.sha256('\n'.join(sorted(track_ids)).encode()).hexdigest()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('compilation'); p.add_argument('--theme', choices=THEMES, default='open_roads')
    p.add_argument('--history', type=Path)
    p = sub.add_parser('candidate'); p.add_argument('brief', type=Path)
    sub.add_parser('catalog')
    args = parser.parse_args()
    try:
        songs = read_catalog(args.catalog)
        if args.command == 'compilation':
            history = load_json(args.history).get('compilations', []) if args.history else []
            result = plan(songs, args.theme, history=history)
        elif args.command == 'candidate':
            brief = load_json(args.brief); result = inspect_candidate(brief.get('title'), brief.get('style'), songs)
        else:
            result = {'count': len(songs), 'audio_measured': False, 'songs': songs}
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (VideoError, TypeError, KeyError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, VideoError) else 'invalid_planner_input'
        print(json.dumps({'status': 'blocked', 'error': reason})); return 2

if __name__ == '__main__':
    raise SystemExit(main())
