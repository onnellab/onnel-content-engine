#!/usr/bin/env python3
"""One bounded M/W/F Shorts slot. Dry-run never writes or contacts providers."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform as host_platform
import shutil
import subprocess
import uuid
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from short_video_pipeline import ROOT, Queue, VideoError, atomic_json, brief_shape, digest, load_json
from short_video_portability import exclusive_file_lock
from short_video_private_permissions import private_path_permissions
from short_video_policy import automatic_choices, load_policy, policy_digest
from short_video_recorder import ensure_recording, load_scenarios, require_promotable_app
from short_video_youtube import Uploader, YouTube, check_config

TEMPLATES = ROOT / 'data/video_script_templates.json'
MIN_FREE = 10 * 1024 ** 3


def templates():
    data = load_json(TEMPLATES)
    if data.get('schema_version') != 1 or not isinstance(data.get('templates'), dict):
        raise VideoError('script_templates_invalid')
    return data['templates']


def eligible_scenarios(recording_platform):
    result = []
    copy = templates()
    for row in load_scenarios().values():
        if row['scenario_id'] not in copy or not row.get('production_eligible'):
            continue
        if recording_platform not in row['platforms']:
            continue
        try:
            require_promotable_app(row, recording_platform)
        except VideoError:
            continue
        result.append({'app_id': row['app_id'], 'scenario_id': row['scenario_id']})
    return sorted(result, key=lambda row: row['app_id'])


def identity(slot, selected):
    payload = {'slot': slot, **selected, 'copy': templates()[selected['scenario_id']]}
    key = 'shorts-slot-' + digest({'slot': slot})[:32]
    return digest(payload), key, hashlib.sha256(key.encode()).hexdigest()[:32]


def make_brief(slot, selected, recording):
    copy = templates()[selected['scenario_id']]
    scenario = load_scenarios()[selected['scenario_id']]
    _, key, _ = identity(slot, selected)
    brief = {'schema_version': 1, 'app_id': selected['app_id'],
             'topic_id': scenario['topics'][0], 'locale': 'en', 'template': 'quick_demo',
             'duration_seconds': 15, 'due_at': slot, 'timezone': 'Asia/Seoul',
             'idempotency_key': key, 'test_only': False, 'recording': recording,
             'title': copy['title'], 'hook': copy['hook'],
             'description': copy['title'] + '. A recorded app workflow. #Shorts',
             'cta': 'Review the result before using it',
             'captions': [{'start': i * 5, 'end': (i + 1) * 5, 'text': text}
                          for i, text in enumerate(copy['steps'])]}
    brief_shape(brief)
    return brief


def _existing_parent(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path


def preflight(config, selected, *, assets, state, projects, browser, recording_platform):
    """Local read-only checks; no installs, render, emulator startup or OAuth."""
    blockers = []
    try:
        ZoneInfo('Asia/Seoul')
    except ZoneInfoNotFoundError:
        blockers.append('iana_timezone_data_missing_install_runtime_requirements')
    if config.get('enabled') is not True:
        blockers.append('scheduled_worker_disabled')
    fence = config.get('legacy_writer_fencing', {})
    if fence.get('confirmed') is not True or not fence.get('evidence'):
        blockers.append('legacy_writer_not_fenced')
    history = config.get('published_history_migration', {})
    if history.get('verified') is not True or not history.get('evidence'):
        blockers.append('existing_publication_history_not_reconciled')
    if not check_config().get('configured'):
        blockers.append('existing_onnellab_youtube_credentials_unavailable')
    if recording_platform != 'android_emulator' or host_platform.system() != 'Windows':
        blockers.append('worker_requires_native_windows_android')
    for path in (state, assets):
        if not private_path_permissions(Path(path)):
            blockers.append('private_runtime_permissions_required')
    if os.environ.get('ONNELLAB_VIDEO_ANDROID_SERIAL'):
        blockers.append('external_emulator_serial_forbidden')
    for name in ('node', 'npm', 'ffmpeg', 'ffprobe', 'flutter', 'adb', 'emulator'):
        if not shutil.which(name):
            blockers.append('dependency_missing:' + name)
    if not (ROOT / 'video/node_modules/@remotion/renderer').is_dir():
        blockers.append('renderer_packages_missing')
    if not browser or not Path(browser).is_file():
        blockers.append('renderer_browser_missing')
    for path in (ROOT, assets, state, projects, Path(os.environ.get('TEMP', '.'))):
        if shutil.disk_usage(_existing_parent(path)).free < MIN_FREE:
            blockers.append('disk_free_below_10gib')
    if config.get('heavy_work_authorized') is not True:
        blockers.append('desktop_resource_coordination_required')
    if selected:
        scenario = load_scenarios()[selected['scenario_id']]
        require_promotable_app(scenario, recording_platform)
        repo = Path(projects) / scenario['repository']
        if not (repo / '.git').exists():
            blockers.append('app_source_repository_missing')
        project = repo / scenario.get('project_subdir', '')
        if not (project / scenario['test_target']).is_file():
            blockers.append('real_recording_test_target_missing')
        if scenario.get('android_avd') != 'ONNELLAB_Video_API36':
            blockers.append('dedicated_android_avd_required')
        avd_root = Path(os.environ.get('ANDROID_AVD_HOME', str(Path.home() / '.android/avd')))
        if not (avd_root / (scenario['android_avd'] + '.ini')).is_file():
            blockers.append('dedicated_android_avd_missing')
    return sorted(set(blockers))


def check_idle_avd():
    # An idle host is required; never attach to or terminate another owner's emulator.
    result = subprocess.run(['adb', 'devices'], capture_output=True, text=True,
                            timeout=15, check=True)
    if any(line.startswith('emulator-') for line in result.stdout.splitlines()):
        raise VideoError('android_emulator_owned_elsewhere')


def public_receipt(api, job, now, *, fetch=urlopen):
    video_id = job.get('upload', {}).get('video_id')
    if job.get('status') != 'published' or not video_id:
        raise VideoError('provider_publication_not_confirmed')
    video = api.video(video_id)
    status, processing = video.get('status', {}), video.get('processingDetails', {})
    if (status.get('privacyStatus') != 'public' or status.get('uploadStatus') != 'processed'
            or processing.get('processingStatus') != 'succeeded'
            or video.get('snippet', {}).get('channelId') != api.channel):
        raise VideoError('provider_publication_not_confirmed')
    url = 'https://www.youtube.com/shorts/' + video_id
    with fetch('https://www.youtube.com/oembed?' + urlencode({'url': url, 'format': 'json'}), timeout=30) as response:
        if response.status != 200:
            raise VideoError('public_url_not_confirmed')
        body = json.loads(response.read(65537))
    if body.get('title') != job['brief']['title'] or not body.get('author_url'):
        raise VideoError('public_url_identity_mismatch')
    return {'video_id': video_id, 'posted_url': url, 'channel_id': api.channel,
            'privacy_status': 'public', 'upload_status': 'processed',
            'processing_status': 'succeeded', 'verified_at': now.isoformat(),
            'published_at': video['snippet'].get('publishedAt', now.isoformat())}


def execute_slot(coordinator, config, slot, selected, *, queue, projects,
                 recording_platform='android_emulator', reconcile=False,
                 api_factory=YouTube, recorder=ensure_recording, receipt_reader=public_receipt):
    """Claim before recording; persist upload intent before any videos.insert."""
    payload_hash, _, job_id = identity(slot, selected)
    api = api_factory()
    if api.channel != config['channel_id']:
        raise VideoError('configured_channel_mismatch')
    api.verify()
    if reconcile:
        job = queue.status(job_id)
        if job['brief']['app_id'] != selected['app_id'] or job['brief']['due_at'] != slot:
            raise VideoError('reconcile_job_identity_mismatch')
        if not job.get('upload', {}).get('video_id'):
            raise VideoError('ambiguous_upload_requires_manual_identity_reconciliation')
    else:
        check_idle_avd()
        coordinator.claim(slot, selected, payload_hash)
        recording = recorder(selected['scenario_id'], projects_root=projects,
                             asset_root=queue.assets, platform=recording_platform)
        job = queue.enqueue(make_brief(slot, selected, recording['path'].replace('\\', '/')))
        job = queue.render(job['id'])
        policy = load_policy()
        choices = automatic_choices(job, policy, asset_root=queue.assets)
        uploader = Uploader(queue, lambda: api)
        with queue.lock():
            state = queue._read()
            uploader.bind_approval_locked(state, state['jobs'][job_id], choices,
                mode='automatic_fail_closed', policy_hash=policy_digest(policy))
        coordinator.mark_upload_started(slot, payload_hash)
    try:
        job = Uploader(queue, lambda: api).run(job_id, execute=True, reconcile=reconcile)
        receipt = receipt_reader(api, job, datetime.now(timezone.utc))
        coordinator.complete(slot, payload_hash, receipt)
        return {'status': 'published', 'job_id': job_id, 'receipt': receipt}
    except Exception:
        coordinator.mark_reconcile_required(slot, payload_hash)
        raise VideoError('slot_requires_reconciliation_no_new_upload') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    parser.add_argument('--config', type=Path, default=ROOT / 'data/video_rotation.json')
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--projects-root', type=Path, required=True)
    parser.add_argument('--browser')
    parser.add_argument('--reconcile-slot', help='Existing specific slot; never creates an upload')
    args = parser.parse_args()
    try:
        return run_cli(args)
    except Exception as exc:
        error = str(exc) if isinstance(exc, VideoError) else 'scheduled_worker_operation_failed'
        print(json.dumps({'status': 'blocked', 'error': error}))
        return 2


def run_cli(args):
    from short_video_coordinator import Coordinator, GitHubLedger, config_blockers, plan, slot_key
    config = load_json(args.config)
    apps = eligible_scenarios('android_emulator')
    # Dry-run uses no shared-state reads: GitHub reads require explicit execution too.
    ledger = {'schema_version': 1, 'slots': {}}
    store = None
    if args.execute and not config_blockers(config):
        store = GitHubLedger(config)
        ledger, _ = store.read()
    proposed = plan(config, ledger, apps, datetime.now(timezone.utc))
    selected = proposed.get('selected_app')
    current = ledger['slots'].get(slot_key(config['channel_id'], proposed['slot'])) if store else None
    if not args.reconcile_slot and current and current['status'] == 'claimed' and current['owner_id'] == config['owner_id']:
        selected = {key: current[key] for key in ('app_id', 'scenario_id')}
        if selected not in apps or identity(proposed['slot'], selected)[0] != current['payload_sha256']:
            raise VideoError('claimed_slot_identity_changed')
        proposed['selected_app'] = selected
        proposed['blockers'] = [b for b in proposed['blockers'] if b != 'channel_has_unresolved_slot']
    blockers = []
    if args.reconcile_slot and args.execute and store:
        row = ledger['slots'].get(slot_key(config['channel_id'], args.reconcile_slot))
        if not row or row['owner_id'] != config['owner_id'] or row['status'] not in {'uploading', 'reconcile_required'}:
            raise VideoError('reconcile_shared_slot_missing_or_ineligible')
        selected = {key: row[key] for key in ('app_id', 'scenario_id')}
        if identity(args.reconcile_slot, selected)[0] != row['payload_sha256']:
            raise VideoError('reconcile_template_changed')
        # Reconciliation reads an existing video; it needs no capture/render hardware.
        blockers = config_blockers(config)
        if not check_config().get('configured'):
            blockers.append('existing_onnellab_youtube_credentials_unavailable')
    else:
        blockers = preflight(config, selected, assets=args.asset_root, state=args.state_root,
                             projects=args.projects_root, browser=args.browser,
                             recording_platform='android_emulator')
        blockers.extend(proposed.get('blockers', []))
    if not args.execute or blockers:
        print(json.dumps({'status': 'blocked' if blockers else 'dry_run', 'dry_run': not args.execute,
                          'plan': proposed, 'blockers': sorted(set(blockers)),
                          'shared_receipts_checked': store is not None}))
        return 2 if args.execute and blockers else 0
    queue = Queue(args.state_root, args.asset_root, browser=args.browser)
    # The token belongs to this durable private queue, never copied from another
    # machine's shared record. Hold a separate lock across the entire operation.
    queue.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive_file_lock(queue.root / 'scheduled-worker.lock'):
        token_path = queue.root / 'scheduled-worker-identity.json'
        if token_path.is_symlink():
            raise VideoError('worker_identity_symlink')
        if not token_path.exists():
            if args.reconcile_slot or current:
                raise VideoError('local_claim_identity_missing')
            atomic_json(token_path, {'claim_token': uuid.uuid4().hex})
        token = load_json(token_path)['claim_token']
        coordinator = Coordinator(store, config, claim_token=token)
        if not args.reconcile_slot and current and current.get('claim_token') != token:
            raise VideoError('slot_owned_by_other_local_queue')
        if args.reconcile_slot and row.get('claim_token') != token:
            raise VideoError('slot_owned_by_other_local_queue')
        result = execute_slot(coordinator, config, args.reconcile_slot or proposed['slot'], selected,
                              queue=queue, projects=args.projects_root,
                              reconcile=bool(args.reconcile_slot))
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
