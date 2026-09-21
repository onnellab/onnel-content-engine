"""One-host, one-shot orchestration; no background scheduling or repository updates."""
from pathlib import Path
import os
import shutil
import signal
from contextlib import contextmanager

from short_video_pipeline import ROOT, VideoError, atomic_json, due_time, load_json
from short_video_youtube import Uploader, YouTube, check_config, timestamp
from short_video_policy import (PolicyError, automatic_choices, load_policy,
                                policy_digest, policy_summary)
from short_video_recorder import RecordingError, load_scenarios

INBOX = ROOT / 'data/video_briefs'


@contextmanager
def graceful_signals():
    def stop(_signum, _frame):
        raise KeyboardInterrupt()
    previous = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)


def enqueue_dir(queue, directory=INBOX, *, dry_run=False):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise VideoError('inbox_missing_or_symlink')
    files = sorted(directory.glob('*.json'))
    if len(files) > 1000 or any(p.is_symlink() for p in files):
        raise VideoError('inbox_invalid')
    if dry_run:
        return {'dry_run': True, 'brief_count': len(files)}
    # Individual atomic idempotent enqueue; a later failure does not erase earlier jobs.
    return [queue.enqueue(load_json(p)) for p in files]


def readiness(queue):
    deps = {name: bool(shutil.which(name)) for name in ('node', 'npm', 'ffmpeg', 'ffprobe')}
    deps['video_packages'] = (ROOT / 'video/node_modules/@remotion/renderer').is_dir()
    deps['browser'] = bool(queue.browser and Path(queue.browser).is_file())
    jobs = queue.status()
    asset_checks = []
    for job in jobs:
        try:
            queue._check_assets(job)
            problem = None
        except (VideoError, OSError):
            problem = 'snapshot_missing_or_changed'
        asset_checks.append({'job_id': job['id'], 'error': problem, 'test_only': job['brief']['test_only']})
    try:
        automatic = policy_summary(load_policy())
        policy_error = None
    except (PolicyError, OSError):
        automatic, policy_error = None, 'automatic_policy_invalid_or_missing'
    try:
        scenario_count = len(load_scenarios())
        recording_error = None
    except (RecordingError, OSError):
        scenario_count, recording_error = 0, 'recording_scenarios_invalid_or_missing'
    recording = {
        'scenario_count': scenario_count,
        'scenario_error': recording_error,
        'flutter': bool(shutil.which('flutter')),
        'adb': bool(shutil.which('adb')),
        'xcrun': bool(shutil.which('xcrun')),
        'projects_root': os.environ.get('ONNELLAB_PROJECTS_ROOT', str(Path.home() / 'Projects')),
    }
    return {'assets': asset_checks, 'dependencies': deps, 'credentials': check_config(),
            'asset_root_exists': queue.assets.is_dir(), 'queued_jobs': len(jobs),
            'production_jobs': sum(not j['brief']['test_only'] for j in jobs),
            'automatic_publication': automatic, 'automatic_policy_error': policy_error,
            'recording_automation': recording,
            'human_review_required': False, 'semantic_uncertainty_action': 'blocked',
            'network_verified': False, 'timers_managed_by_engine': False,
            'external_scheduler_status': 'not_checked'}


def worker(queue, *, upload=False, execute=False, dry_run=False, inbox=None,
           api_factory=YouTube, renderer=None, policy=None):
    if dry_run or (upload and not execute):
        return {'dry_run': True, 'jobs': queue.status(),
                'inbox': enqueue_dir(queue, inbox, dry_run=True) if inbox else None}
    if inbox:
        enqueue_dir(queue, inbox)
    with queue.lock():
        state = queue._read()
        api = None
        if upload:
            try:
                api = api_factory()
                api.verify()
            except Exception as exc:
                from short_video_youtube import UploadError
                return {'status': 'blocked',
                        'error': str(exc) if isinstance(exc, UploadError) else 'youtube_check_failed'}

        for job in state['jobs'].values():
            if job['status'] == 'rendering':
                job.update(status='blocked', error='interrupted_render_requires_retry')
                atomic_json(queue.state_path, state)

        jobs = sorted(state['jobs'].values(), key=lambda j: (due_time(j['brief']), j['id']))
        uploader = Uploader(queue, api_factory)

        # Existing provider evidence is always reconciled before considering new publication.
        for job in jobs:
            if upload and (job.get('upload') or job['status'] in {'accepted', 'processing'}):
                if job['status'] == 'scheduled' and timestamp(job['approval']['choices']['publish_at']) > queue.clock():
                    continue
                if job['status'] in {'published', 'uploaded_private', 'uploaded_unlisted',
                                     'forced_private', 'rejected'}:
                    continue
                return uploader.run_locked(state, job, reconcile=True, api=api)

        if upload:
            try:
                policy = policy or load_policy()
                choices_probe = policy_summary(policy)
            except (PolicyError, OSError):
                return {'status': 'blocked', 'error': 'automatic_policy_invalid_or_missing'}
        else:
            choices_probe = None

        for job in jobs:
            if due_time(job['brief']) > queue.clock():
                continue
            if job['status'] == 'queued':
                queue._render(state, job, renderer)
                if not upload:
                    return job
            if upload and job['status'] in {'rendered', 'blocked'} and not job.get('upload'):
                try:
                    if not job.get('approval'):
                        choices = automatic_choices(job, policy, asset_root=queue.assets)
                        uploader.bind_approval_locked(
                            state, job, choices, mode='automatic_fail_closed',
                            policy_hash=policy_digest(policy))
                    return uploader.run_locked(state, job, api=api)
                except PolicyError as exc:
                    job.update(status='blocked', error=str(exc))
                    atomic_json(queue.state_path, state)
                    return {'status': 'blocked', 'error': str(exc), 'job_id': job['id'],
                            'automatic_publication': choices_probe}
        return {'status': 'idle'}
