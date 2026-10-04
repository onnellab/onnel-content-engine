"""Offline 28-day measurement ledger; never posts, authenticates, or reschedules."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from distribution_policy import channel_excluded
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from publication_history import publication_history, publication_key, preserve_publication, specific_permalink
from video_product_eligibility import public_video_platforms

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = {'x', 'linkedin', 'bluesky', 'medium', 'devto', 'youtube'}
METRICS = {
    'channel_export': {'impressions', 'link_clicks'},
    'google_play_export': {'listing_visitors', 'listing_button_click_users', 'listing_acquisitions'},
    'app_store_connect_export': {'unique_impressions', 'unique_product_page_views',
                               'total_downloads', 'preorders', 'first_time_downloads'},
}
LIMIT = 8 * 1024 * 1024


class MeasurementError(ValueError):
    pass


def read_json(path):
    path = Path(path)
    if path.stat().st_size > LIMIT:
        raise MeasurementError('Input exceeds 8 MiB')
    return json.loads(path.read_text(encoding='utf-8'))


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as exc:
        raise MeasurementError('Expected ISO timestamp with timezone') from exc
    if result.tzinfo is None:
        raise MeasurementError('Timestamp requires timezone')
    return result.astimezone(timezone.utc)


def campaign_token(app_id, material_id, channel, start):
    if channel not in CHANNELS:
        raise MeasurementError('Unsupported channel')
    identity = json.dumps([app_id, material_id, channel, timestamp(start).isoformat()])
    return 'on-' + hashlib.sha256(identity.encode()).hexdigest()[:24]


def tracking_link(url, store, source, campaign, provider_token=None):
    """Produce a proposed link only; never replace a historical publication URL."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment or parsed.port:
        raise MeasurementError('Expected a clean official HTTPS store URL')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', campaign):
        raise MeasurementError('Campaign must be 1-30 safe non-personal characters')
    if source not in CHANNELS:
        raise MeasurementError('Unsupported channel')
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise MeasurementError('Duplicate URL query keys')
    if store == 'google_play':
        if parsed.hostname != 'play.google.com' or parsed.path != '/store/apps/details' or not dict(pairs).get('id'):
            raise MeasurementError('Expected Google Play app detail URL')
        added = {'utm_source': source, 'utm_campaign': campaign}
        if 'referrer' in keys:
            raise MeasurementError('Existing referrer attribution must not be replaced')
    elif store == 'app_store':
        if parsed.hostname != 'apps.apple.com' or not re.search(r'/id[0-9]+$', parsed.path):
            raise MeasurementError('Expected Apple App Store app URL')
        if not provider_token or not re.fullmatch(r'[0-9]+', provider_token):
            raise MeasurementError('Supply the existing App Store Connect provider token; do not invent one')
        added = {'pt': provider_token, 'ct': campaign, 'mt': '8'}
    else:
        raise MeasurementError('Unsupported store')
    if set(added) & set(keys):
        raise MeasurementError('Existing campaign parameters must not be overwritten')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs + list(added.items())), ''))


def metric_rates(source, metrics):
    if source not in METRICS or not isinstance(metrics, dict) or set(metrics) - METRICS[source]:
        raise MeasurementError('Unknown source or metric; keep source definitions separate')
    for value in metrics.values():
        if value is not None and (type(value) is not int or value < 0):
            raise MeasurementError('Metrics must be nonnegative integer counts or null')
    def ratio(numerator, denominator):
        if numerator is None or denominator in (None, 0):
            return None
        return numerator / denominator
    if source == 'channel_export':
        return {'link_click_rate': ratio(metrics.get('link_clicks'), metrics.get('impressions'))}
    if source == 'google_play_export':
        return {'listing_click_through_rate': ratio(metrics.get('listing_button_click_users'), metrics.get('listing_visitors'))}
    downloads, preorders = metrics.get('total_downloads'), metrics.get('preorders')
    numerator = downloads + preorders if downloads is not None and preorders is not None else None
    return {'app_store_conversion_rate': ratio(numerator, metrics.get('unique_impressions'))}


def specific_post_permalink(channel, url):
    if specific_permalink(channel, url):
        return True
    try:
        parsed = urlsplit(url or '')
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
            return False
        if channel == 'bluesky':
            return parsed.hostname == 'bsky.app' and bool(re.fullmatch(r'/profile/[^/]+/post/[^/]+', parsed.path))
        if channel == 'devto':
            return parsed.hostname == 'dev.to' and bool(re.fullmatch(r'/[^/]+/[^/]+', parsed.path))
        if channel == 'youtube':
            return (parsed.hostname in {'www.youtube.com', 'youtube.com'}
                    and (bool(re.fullmatch(r'/shorts/[A-Za-z0-9_-]{11}', parsed.path))
                         or parsed.path == '/watch' and bool(re.fullmatch(r'[A-Za-z0-9_-]{11}', dict(parse_qsl(parsed.query)).get('v', '')))))
    except ValueError:
        pass
    return False


def store_identity(url, platform):
    """Compare app identities without treating campaign parameters as identity."""
    try:
        parsed = urlsplit(url or '')
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
            return None
        pairs = parse_qsl(parsed.query)
        if len(pairs) != len({key for key, _ in pairs}):
            return None
        if platform == 'ios' and parsed.hostname == 'apps.apple.com':
            match = re.search(r'/id([0-9]+)$', parsed.path)
            return match.group(1) if match else None
        if platform == 'android' and parsed.hostname == 'play.google.com' and parsed.path == '/store/apps/details':
            return dict(pairs).get('id') or None
    except ValueError:
        pass
    return None


def metric_samples(rows, start, end, known, root):
    result, seen, scopes = [], {}, set()
    fields = {'sample_id', 'manual_key', 'app_id', 'source', 'period_start', 'period_end',
              'dimensions', 'metrics', 'evidence_path', 'evidence_sha256'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise MeasurementError('Metric sample schema mismatch')
        sample_id = row['sample_id']
        if not isinstance(sample_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', sample_id):
            raise MeasurementError('Invalid sample identity')
        if sample_id in seen:
            if row != seen[sample_id]:
                raise MeasurementError('Conflicting duplicate metric sample')
            continue
        seen[sample_id] = row
        item = known.get(row['manual_key'])
        if item is None or row['app_id'] not in item['app_ids']:
            raise MeasurementError('Metric sample must reference an exact known publication and app')
        left, right = timestamp(row['period_start']), timestamp(row['period_end'])
        if not start <= left < right <= end:
            raise MeasurementError('Metric sample period must lie within the 28-day window')
        if not isinstance(row['dimensions'], dict) or any(
            key not in {'country', 'store_platform', 'campaign', 'source_type', 'device'}
            or not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value)
            for key, value in row['dimensions'].items()
        ):
            raise MeasurementError('Use only aggregate, non-personal dimensions')
        if row['source'] in {'google_play_export', 'app_store_connect_export'}:
            platform = 'android' if row['source'] == 'google_play_export' else 'ios'
            campaign = row['dimensions'].get('campaign')
            if (not campaign or row['dimensions'].get('store_platform') != platform
                    or campaign not in item['tracking_campaigns'].get(row['app_id'], {}).get(platform, [])
                    or not item['publication_permalink_recorded']):
                raise MeasurementError('Store attribution requires a matching published campaign link and store platform')
            matches = [candidate for candidate in known.values()
                       if row['app_id'] in candidate['app_ids']
                       and campaign in candidate['tracking_campaigns'].get(row['app_id'], {}).get(platform, [])]
            if len(matches) != 1:
                raise MeasurementError('Shared campaign cannot be attributed to one material; retain it as store-level data')
        # Samples must be exact exports, never summed across overlapping unique-user cohorts.
        scope = (row['manual_key'], row['app_id'], row['source'], json.dumps(row['dimensions'], sort_keys=True))
        for old_scope, old_left, old_right in scopes:
            if scope == old_scope and left < old_right and old_left < right:
                raise MeasurementError('Overlapping metric samples would double-count a cohort')
        scopes.add((scope, left, right))
        path = Path(row['evidence_path'])
        if not path.is_absolute():
            path = root / path
        if not re.fullmatch(r'[a-f0-9]{64}', row['evidence_sha256']) or path.stat().st_size > LIMIT:
            raise MeasurementError('Invalid metric evidence')
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['evidence_sha256']:
            raise MeasurementError('Metric evidence hash mismatch')
        result.append({**row, 'rates': metric_rates(row['source'], row['metrics'])})
    return result


def report(root, config, start, as_of):
    root = Path(root)
    start, as_of = timestamp(start), timestamp(as_of)
    end = start + timedelta(days=28)
    if as_of < start:
        raise MeasurementError('as_of precedes experiment start')
    if (config.get('schema_version') != 1 or config.get('window_days') != 28
            or config.get('baseline_weight') != 1 or set(config.get('channels', [])) != CHANNELS):
        raise MeasurementError('Use the 28-day equal-baseline configuration and existing channels')
    with (root / 'data/apps_registry.csv').open(encoding='utf-8', newline='') as handle:
        apps = list(csv.DictReader(handle))
    with (root / 'data/topics.csv').open(encoding='utf-8', newline='') as handle:
        topics = {row['id']: row for row in csv.DictReader(handle)}
    app_names = {row['app_name']: row['app_id'] for row in apps}
    apps_by_id = {row['app_id']: row for row in apps}
    baseline = [{'app_id': row['app_id'], 'app_name': row['app_name'], 'weight': 1,
                 'public_platforms': public_video_platforms(row, root / 'data/store_versions.csv')}
                for row in apps if row['status'] == 'released' and row['content_eligible'] == 'true']
    history = publication_history(root)
    schedule_path = root / 'data/manual_publish_schedule.json'
    schedule = {row['manual_key']: row['publish_at'] for row in read_json(schedule_path).get('backlog', [])} if schedule_path.exists() else {}
    all_rows = []
    for relative, collection, kind in [('generated/social/manifest.json', 'posts', 'social'),
                                       ('generated/syndication/manifest.json', 'drafts', 'article')]:
        path = root / relative
        if path.exists():
            all_rows += [(row, kind) for row in read_json(path).get(collection, [])]
    for row in config.get('extra_publications', []):
        if not isinstance(row, dict) or row.get('platform') != 'youtube':
            raise MeasurementError('Extra publication inputs are existing YouTube records only')
        all_rows.append((row, 'short_video'))
    records, duplicates = {}, 0
    for raw, kind in all_rows:
        channel = raw.get('platform')
        if channel not in CHANNELS or raw.get('is_variant'):
            continue
        template = 'markdown' if kind == 'article' else raw.get('template_id', '')
        key = publication_key(raw, template)
        if len(key.split('::')) != 4 or not all(key.split('::')):
            raise MeasurementError('Publication identity is incomplete')
        item = preserve_publication(raw, history, template)
        topic = topics.get(str(item.get('topic_id')), {})
        app_ids = [app_names[name] for name in topic.get('related_apps', '').split('|') if name in app_names]
        published = item.get('posted_at') or history.get(key, {}).get('published_at') or history.get(key, {}).get('marked_at')
        base = topic.get('published_at') or topic.get('scheduled_at')
        delay = {'x': 0, 'linkedin': 1, 'bluesky': 1, 'devto': 2, 'medium': 4, 'youtube': 0}[channel]
        due = schedule.get(key) or ((timestamp(base) + timedelta(days=delay)).isoformat() if base else None)
        event_at = published or item.get('last_attempt_at') or due
        week = None
        if event_at and start <= timestamp(event_at) < min(end, as_of):
            week = (timestamp(event_at) - start).days // 7 + 1
        recorded = bool(item.get('_publication_recorded') or item.get('status') == 'posted')
        if channel_excluded(channel) and not recorded:
            continue  # Excluded unpublished backlog is not future distribution demand.
        campaigns = {app_id: {'ios': [], 'android': []} for app_id in app_ids}
        for url in str(item.get('destination_urls') or item.get('target_url') or '').split('|'):
            parsed = urlsplit(url)
            query = dict(parse_qsl(parsed.query))
            for platform, field, token in [('ios', 'app_store_url', 'ct'), ('android', 'play_store_url', 'utm_campaign')]:
                identity = store_identity(url, platform)
                if not identity or not query.get(token) or platform == 'ios' and not query.get('pt'):
                    continue
                for app_id in app_ids:
                    if store_identity(apps_by_id[app_id].get(field), platform) == identity:
                        campaigns[app_id][platform].append(query[token])
        record = {'manual_key': key, 'material_id': item.get('topic_id'), 'material_kind': kind,
                  'app_ids': app_ids, 'channel': channel, 'week': week, 'event_at': event_at,
                  'in_observed_window': week is not None, 'due_at': due,
                  'publication_recorded': recorded, 'posted_url': item.get('posted_url') or None,
                  'publication_permalink_recorded': specific_post_permalink(channel, item.get('posted_url')),
                  'tracking_campaigns': campaigns,
                  'source_status': raw.get('status'), 'historical_error_present': bool(raw.get('error')),
                  'error_type': raw.get('error_type') or None, 'last_attempt_at': raw.get('last_attempt_at') or None,
                  'retry_count_snapshot': raw.get('retry_count'), 'metrics': None}
        if key in records:
            if record != records[key]:
                raise MeasurementError('Conflicting duplicate publication identity')
            duplicates += 1
        records[key] = record
    samples = metric_samples(config.get('metric_samples', []), start, min(end, as_of), records, root)
    for sample in samples:
        record = records[sample['manual_key']]
        if record['metrics'] is None:
            record['metrics'] = []
        record['metrics'].append(sample)
    observed = [record for record in records.values() if record['in_observed_window']]
    return {'schema_version': 1, 'start': start.isoformat(), 'end_exclusive': end.isoformat(),
            'as_of': as_of.isoformat(), 'baseline': baseline, 'records': sorted(records.values(), key=lambda row: row['manual_key']),
            'summary': {'observed_records': len(observed), 'publication_recorded': sum(row['publication_recorded'] for row in observed),
                        'duplicate_input_rows_ignored': duplicates, 'metric_samples': len(samples)},
            'notes': config.get('notes', []),
            'experiment_proposals': [{'app_id': app['app_id'], 'weight_change': None,
                'proposal': 'Keep equal baseline; collect a comparable aggregate export before proposing extra exposure.'}
                for app in baseline]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    ledger = commands.add_parser('report')
    ledger.add_argument('--root', type=Path, default=ROOT)
    ledger.add_argument('--config', type=Path, default=ROOT / 'data/marketing_measurement.json')
    ledger.add_argument('--start', required=True)
    ledger.add_argument('--as-of', required=True)
    link = commands.add_parser('tracking-link')
    link.add_argument('--url', required=True)
    link.add_argument('--store', choices=['google_play', 'app_store'], required=True)
    link.add_argument('--channel', choices=sorted(CHANNELS), required=True)
    link.add_argument('--campaign', required=True)
    link.add_argument('--provider-token')
    args = parser.parse_args()
    try:
        if args.command == 'report':
            payload = report(args.root, read_json(args.config), args.start, args.as_of)
        else:
            payload = {'proposed_url': tracking_link(args.url, args.store, args.channel, args.campaign, args.provider_token)}
        print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (MeasurementError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Measurement failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
