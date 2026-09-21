"""One-host, one-shot orchestration; no background scheduling or repository updates."""
from pathlib import Path
import shutil
import signal
from contextlib import contextmanager

from short_video_pipeline import ROOT, VideoError, atomic_json, due_time, load_json
from short_video_youtube import Uploader, YouTube, check_config, timestamp

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
    return {'assets': asset_checks, 'dependencies': deps, 'credentials': check_config(),
            'asset_root_exists': queue.assets.is_dir(), 'queued_jobs': len(jobs),
            'production_jobs': sum(not j['brief']['test_only'] for j in jobs),
            'footage_approval_required': True, 'fonts_require_local_review': True,
            'network_verified': False, 'timers_managed_by_engine': False,
            'external_scheduler_status': 'not_checked'}


def worker(queue, *, upload=False, execute=False, dry_run=False, inbox=None, api_factory=YouTube, renderer=None):
    if dry_run or (upload and not execute):
        return {'dry_run': True, 'jobs': queue.status(),
                'inbox': enqueue_dir(queue, inbox, dry_run=True) if inbox else None}
    # Import uses the same queue lock for each atomic enqueue. No lock is held between
    # import and selection; idempotency and the subsequent worker lock prevent duplicates.
    if inbox:
        enqueue_dir(queue, inbox)
    with queue.lock():
        state = queue._read()
        api = None
        if upload:
            try:
                api = api_factory()
                api.verify()  # Config/auth stops this invocation before render or upload.
            except Exception as exc:
                from short_video_youtube import UploadError
                return {'status': 'blocked', 'error': str(exc) if isinstance(exc, UploadError) else 'youtube_check_failed'}
        for job in state['jobs'].values():
            if job['status'] == 'rendering':
                job.update(status='blocked', error='interrupted_render_requires_retry')
                atomic_json(queue.state_path, state)
        jobs = sorted(state['jobs'].values(), key=lambda j: (due_time(j['brief']), j['id']))
        for job in jobs:
            if upload and (job.get('upload') or job['status'] in {'accepted', 'processing'}):
                if job['status'] == 'scheduled' and timestamp(job['approval']['choices']['publish_at']) > queue.clock():
                    continue
                if job['status'] in {'published', 'uploaded_private', 'uploaded_unlisted', 'forced_private', 'rejected'}:
                    continue
                return Uploader(queue, api_factory).run_locked(state, job, reconcile=True, api=api)
        for job in jobs:
            if due_time(job['brief']) > queue.clock():
                continue
            if job['status'] == 'queued':
                queue._render(state, job, renderer)
                if not upload:
                    return job
                if not job.get('approval'):
                    return {'status': 'blocked', 'error': 'upload_approval_required', 'job_id': job['id']}
            if upload and job['status'] in {'rendered', 'blocked'} and not job.get('upload') and job.get('approval'):
                return Uploader(queue, api_factory).run_locked(state, job, api=api)
        pending = [j for j in jobs if j['status'] == 'rendered' and not j.get('approval')]
        if upload and pending:
            return {'status': 'blocked', 'error': 'upload_approval_required', 'job_id': pending[0]['id']}
        return {'status': 'idle'}
