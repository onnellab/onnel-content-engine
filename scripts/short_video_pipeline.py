"""Private local short-video queue and renderer; provider adapter is separate."""
from __future__ import annotations

from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
MAX_BRIEF = 65536
MAX_ASSET = 256 * 1024 * 1024
MAX_STATE = 16 * 1024 * 1024
QUEUE_SCHEMA = 2
VIDEO_LOCALE = 'en'
MAX_COPY_CHARS = 80
MAX_RECORDING_TAIL_FREEZE_SECONDS = 10
ALLOWED_VIDEO_PLATFORMS = ('ios', 'android')
STATES = {'queued', 'rendering', 'rendered', 'uploading', 'uploaded_private',
          'scheduled', 'published', 'blocked', 'failed', 'accepted', 'processing',
          'uploaded_unlisted', 'forced_private', 'reconcile_required', 'rejected'}
# Provider states are observations; retries never return to a new insert.
UPLOAD_TRANSITIONS = {
    'rendered': {'uploading'},
    'uploading': {'accepted', 'reconcile_required'},
    'accepted': {'processing', 'uploaded_private', 'uploaded_unlisted', 'scheduled',
                 'published', 'forced_private', 'rejected', 'reconcile_required'},
}



class VideoError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path, limit=MAX_BRIEF):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise VideoError('Duplicate JSON key')
            obj[key] = value
        return obj
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise VideoError('JSON size limit exceeded')
        obj = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(VideoError('Non-finite JSON')))
        if not isinstance(obj, dict):
            raise VideoError('Expected JSON object')
        return obj
    except (OSError, ValueError, RecursionError) as exc:
        raise VideoError('Invalid or unreadable JSON') from exc


def atomic_json(path, value):
    data = canonical(value)
    if len(data) > MAX_STATE:
        raise VideoError('Queue capacity exceeded')
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        fsync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run_process(argv, timeout=60, env=None):
    """No shell, limited output, owned process group cleanup including descendants."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                env=env, start_new_session=True)
        try:
            proc.wait(timeout=timeout)
            if proc.returncode:
                raise VideoError(f'Local process failed (exit {proc.returncode})')
            out.seek(0)
            data = out.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise VideoError('Process output too large')
            return data
        except subprocess.TimeoutExpired as exc:
            raise VideoError('Local process timed out') from exc
        finally:
            # Only this invocation's session; never global browser/ffmpeg cleanup.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


def probe(path):
    try:
        return json.loads(run_process(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-format_whitelist', 'mov,matroska,webm,wav,mp3',
            '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,duration',
            '-of', 'json', str(path)]))
    except (OSError, ValueError) as exc:
        raise VideoError('ffprobe failed') from exc


def due_time(brief):
    try:
        value = brief['due_at']
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)', value):
            raise ValueError()
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        zone = ZoneInfo(brief['timezone'])
        if dt.utcoffset() != dt.astimezone(zone).utcoffset():
            raise ValueError()
        return dt
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise VideoError('due_at must have an offset matching a supported IANA timezone') from exc


def brief_shape(brief):
    required = {'schema_version', 'app_id', 'topic_id', 'locale', 'template', 'duration_seconds',
                'due_at', 'timezone', 'idempotency_key', 'test_only', 'recording', 'hook',
                'title', 'description', 'cta', 'captions'}
    if not isinstance(brief, dict) or set(brief) - required - {'narration'} or required - set(brief):
        raise VideoError('Unknown or missing brief fields')
    if len(canonical(brief)) > MAX_BRIEF:
        raise VideoError('Brief too large')
    if type(brief['schema_version']) is not int or brief['schema_version'] != 1:
        raise VideoError('Unsupported brief schema')
    if brief['locale'] != VIDEO_LOCALE or brief['template'] not in {'quick_demo', 'problem_solution'}:
        raise VideoError('Short videos are English-only; unsupported locale or template')
    duration = brief['duration_seconds']
    if type(duration) is not int or not 15 <= duration <= 30 or type(brief['test_only']) is not bool:
        raise VideoError('Invalid duration or test_only flag')
    for field, maximum in [('hook', MAX_COPY_CHARS), ('cta', MAX_COPY_CHARS), ('title', 120), ('description', 2000),
                           ('idempotency_key', 128), ('app_id', 30), ('topic_id', 30), ('timezone', 80)]:
        text = brief[field]
        if not isinstance(text, str) or not text.strip() or len(text) > maximum or any(ord(c) < 32 and c != '\n' for c in text):
            raise VideoError(f'Invalid {field}')
    for field in ['hook', 'cta']:
        caption_text(brief[field])
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', brief['idempotency_key']):
        raise VideoError('Invalid idempotency key')
    captions = brief['captions']
    if not isinstance(captions, list) or not 1 <= len(captions) <= 12:
        raise VideoError('Expected 1-12 captions')
    previous = 0
    for caption in captions:
        if not isinstance(caption, dict) or set(caption) != {'start', 'end', 'text'}:
            raise VideoError('Invalid caption')
        start, end = caption['start'], caption['end']
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in (start, end)):
            raise VideoError('Invalid caption timing')
        if start < previous or end - start < 1 or end > duration:
            raise VideoError('Captions must be ordered, nonoverlapping, at least 1s, within duration')
        caption_text(caption['text'])
        previous = end
    due_time(brief)


def caption_text(text):
    # Objective safety bounds only. The renderer measures actual typography and wraps to <=2 lines.
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_COPY_CHARS or len(text.split('\n')) > 2:
        raise VideoError('Video copy must be 1-2 short lines and at most 80 characters')
    for line in text.split('\n'):
        units = sum(2 if ord(c) > 127 else 1 for c in line)
        if units > MAX_COPY_CHARS or not line.strip() or any(ord(c) < 32 for c in line):
            raise VideoError('Video copy line is unreadably long or contains control characters')


def product_snapshot(app):
    try:
        if app['status'] != 'released' or app['content_eligible'] != 'true':
            raise VideoError('Only released, content-eligible apps may be promoted')
        name = app['app_name'].strip()
        if not name or len(name) > 24 or any(ord(c) < 32 for c in name):
            raise VideoError('Invalid app display name in registry')
        raw_platforms = [item for item in app['platforms'].split('|') if item]
        platforms = [item for item in ALLOWED_VIDEO_PLATFORMS if item in raw_platforms]
        if not platforms or set(raw_platforms) != set(platforms):
            raise VideoError('Unsupported app platform set in registry')
        return {'app_name': name, 'platforms': platforms}
    except KeyError as exc:
        raise VideoError('Incomplete app registry row') from exc


def validate_product_snapshot(product):
    if not isinstance(product, dict) or set(product) != {'app_name', 'platforms'}:
        raise VideoError('Invalid immutable product snapshot')
    name = product.get('app_name')
    platforms = product.get('platforms')
    if (not isinstance(name, str) or not name.strip() or len(name) > 24
            or any(ord(c) < 32 for c in name)
            or not isinstance(platforms, list) or not platforms
            or platforms != [item for item in ALLOWED_VIDEO_PLATFORMS if item in platforms]
            or len(set(platforms)) != len(platforms)):
        raise VideoError('Invalid immutable product snapshot')


class Queue:
    def __init__(self, root, asset_root, *, clock=None, browser=None, registry_root=None):
        original = Path(root).absolute()
        self.root = original.resolve()
        # Only .runtime inside this repo; other private locations may be used by tests/operators.
        if self.root.is_relative_to(ROOT) and not self.root.is_relative_to(ROOT / '.runtime'):
            raise VideoError('Runtime state must be private, outside public/tracked outputs')
        if original != self.root and original.is_symlink():
            raise VideoError('Runtime root must not be a symlink')
        self.assets = Path(asset_root).resolve()
        self.state_path = self.root / 'queue.json'
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.browser = browser
        self.registry = Path(registry_root) if registry_root else ROOT / "data"

    def asset(self, name, kind):
        if not isinstance(name, str) or len(name) > 240 or '\\' in name or ':' in name:
            raise VideoError('Asset must be a relative local path')
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise VideoError('Asset path traversal')
        target = (self.assets / path).resolve()
        suffixes = {'.mp4', '.mov', '.webm'} if kind == 'recording' else {'.wav', '.mp3', '.m4a'}
        if not target.is_relative_to(self.assets) or not target.is_file() or target.suffix.lower() not in suffixes:
            raise VideoError('Missing, escaping, or unsupported local asset')
        if not 0 < target.stat().st_size <= MAX_ASSET:
            raise VideoError('Asset size must be 1 byte to 256 MiB')
        return target

    def validate(self, brief):
        try:
            brief_shape(brief)
            with (self.registry / 'apps_registry.csv').open(newline='', encoding='utf-8') as stream:
                apps = {row['app_id']: row for row in csv.DictReader(stream)}
            with (self.registry / 'topics.csv').open(newline='', encoding='utf-8') as stream:
                topics = {row['id']: row for row in csv.DictReader(stream)}
            app, topic = apps.get(brief['app_id']), topics.get(brief['topic_id'])
            if not app or not topic:
                raise VideoError('Unknown app or source topic')
            product = product_snapshot(app)
            if topic['status'] == 'archived' or app['app_name'] not in topic['related_apps'].split('|'):
                raise VideoError('Source topic must be active and reference this app')
            assets = {}
            for kind in ['recording', 'narration']:
                if kind in brief:
                    path = self.asset(brief[kind], kind)
                    assets[kind] = {'sha256': file_hash(path), 'file': kind + path.suffix.lower()}
            return {'assets': assets, 'product': product}
        except (TypeError, KeyError, OSError, ValueError) as exc:
            if isinstance(exc, VideoError):
                raise
            raise VideoError('Malformed brief or asset') from exc

    def _private_structure(self):
        for path in [self.root / 'jobs', self.state_path, self.root / '.lock']:
            if path.is_symlink():
                raise VideoError('Symlinks in private state are forbidden')
        jobs = self.root / 'jobs'
        if jobs.exists() and (not jobs.is_dir() or any(p.is_symlink() for p in jobs.iterdir())):
            raise VideoError('Invalid private job directory')

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self._private_structure()
        path = self.root / '.lock'
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise VideoError('Another queue operation/worker is active') from exc
            yield
        finally:
            os.close(fd)

    def _read(self):
        self._private_structure()
        if not self.state_path.exists():
            # Assets without a state file can indicate interrupted creation or lost state.
            if (self.root / 'jobs').exists() and any((self.root / 'jobs').iterdir()):
                raise VideoError('Missing queue state with existing jobs; manual recovery required')
            return {'schema_version': QUEUE_SCHEMA, 'jobs': {}}
        try:
            if self.state_path.is_symlink():
                raise VideoError('Symlink state rejected')
            state = load_json(self.state_path, MAX_STATE)
            if set(state) != {'schema_version', 'jobs'} or type(state['schema_version']) is not int or state['schema_version'] != QUEUE_SCHEMA or not isinstance(state['jobs'], dict):
                raise VideoError('Unsupported/corrupt queue state; English-only video queue requires schema 2')
            seen = set()
            for key, job in state['jobs'].items():
                if not re.fullmatch(r'[0-9a-f]{32}', key) or job['id'] != key or job['status'] not in STATES:
                    raise VideoError('Invalid job state')
                brief_shape(job['brief'])
                assets = job['assets']
                product = job['product']
                validate_product_snapshot(product)
                if set(assets) != ({'recording', 'narration'} if 'narration' in job['brief'] else {'recording'}):
                    raise VideoError('Invalid asset manifest')
                for kind, item in assets.items():
                    if not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or not re.fullmatch(kind + r'\.(mp4|mov|webm|wav|mp3|m4a)', item['file']):
                        raise VideoError('Invalid asset manifest')
                if job['payload_hash'] != digest({'brief': job['brief'], 'assets': assets, 'product': product}):
                    raise VideoError('Immutable payload changed')
                idem = job['brief']['idempotency_key']
                if key != hashlib.sha256(idem.encode()).hexdigest()[:32] or idem in seen:
                    raise VideoError('Duplicate or corrupt job identity')
                seen.add(idem)
                if type(job['upload_eligible']) is not bool or job['upload_eligible'] != (not job['brief']['test_only']):
                    raise VideoError('Corrupt upload eligibility')
                if job['status'] == 'rendered':
                    result = job['result']
                    if not isinstance(result, dict) or result.get('job_id') != key or result.get('test_only') != job['brief']['test_only'] or result.get('upload_eligible') != job['upload_eligible']:
                        raise VideoError('Rendered state lacks a valid result')
                    if set(result.get('sha256', {})) != {'video.mp4', 'preview.png'} or any(not re.fullmatch(r'[0-9a-f]{64}', h) for h in result['sha256'].values()):
                        raise VideoError('Invalid output manifest')
                if 'upload' in job:
                    upload = job['upload']
                    if (not isinstance(upload, dict) or upload.get('phase') not in {'initiating', 'session_ready', 'sending', 'accepted'}
                            or not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', upload.get('channel_id', ''))
                            or type(upload.get('size')) is not int or not 0 < upload['size'] <= MAX_ASSET
                            or not re.fullmatch(r'[0-9a-f]{64}', upload.get('sha256', ''))
                            or ('video_id' in upload and not re.fullmatch(r'[A-Za-z0-9_-]{11}', upload['video_id']))):
                        raise VideoError('Invalid upload evidence; manual recovery required')
                if job['brief']['test_only'] and job['status'] in {'uploading', 'accepted', 'processing', 'uploaded_private', 'uploaded_unlisted', 'forced_private', 'scheduled', 'published', 'rejected'}:
                    raise VideoError('Test fixture cannot enter upload states')
            return state
        except (TypeError, KeyError, ValueError) as exc:
            raise VideoError('Queue state corrupt; refusing mutation') from exc

    def status(self, job_id=None):
        state = self._read()
        if job_id is None:
            return list(state['jobs'].values())
        if job_id not in state['jobs']:
            raise VideoError('Unknown job id')
        return state['jobs'][job_id]

    def enqueue(self, brief):
        validated = self.validate(brief)
        assets = validated['assets']
        product = validated['product']
        payload_hash = digest({'brief': brief, 'assets': assets, 'product': product})
        job_id = hashlib.sha256(brief['idempotency_key'].encode()).hexdigest()[:32]
        with self.lock():
            state = self._read()
            if job_id in state['jobs']:
                job = state['jobs'][job_id]
                if job['payload_hash'] != payload_hash:
                    raise VideoError('Idempotency conflict: brief or asset content differs')
                return job
            if len(state['jobs']) >= 1000:
                raise VideoError('Queue capacity reached')
            jobs = self.root / 'jobs'
            jobs.mkdir(mode=0o700, exist_ok=True)
            destination = jobs / job_id
            if destination.exists():
                raise VideoError('Orphan job directory; manual recovery required')
            with tempfile.TemporaryDirectory(prefix='.enqueue-', dir=self.root) as temp:
                staging = Path(temp) / 'job'
                staging.mkdir(mode=0o700)
                for kind, item in assets.items():
                    target = staging / item['file']
                    shutil.copyfile(self.asset(brief[kind], kind), target)
                    os.chmod(target, 0o600)
                    with target.open('rb') as stream:
                        os.fsync(stream.fileno())
                    if target.stat().st_size > MAX_ASSET or file_hash(target) != item['sha256']:
                        raise VideoError('Asset changed during enqueue')
                atomic_json(staging / 'brief.json', brief)
                fsync_dir(staging)
                os.rename(staging, destination)
                fsync_dir(jobs)
            job = dict(id=job_id, brief=brief, assets=assets, product=product, payload_hash=payload_hash,
                       status='queued', upload_eligible=not brief['test_only'],
                       created_at=self.clock().isoformat(), result=None, error=None)
            state['jobs'][job_id] = job
            atomic_json(self.state_path, state)
            return job

    def _check_assets(self, job):
        folder = self.root / 'jobs' / job['id']
        if folder.is_symlink() or (folder / 'brief.json').is_symlink() or digest(load_json(folder / 'brief.json')) != digest(job['brief']):
            raise VideoError('Immutable brief snapshot changed/missing')
        for item in job['assets'].values():
            path = folder / item['file']
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ASSET or file_hash(path) != item['sha256']:
                raise VideoError('Immutable asset snapshot changed/missing')

    def _probe_inputs(self, job):
        folder = self.root / 'jobs' / job['id']
        duration = job['brief']['duration_seconds']
        for kind, item in job['assets'].items():
            info = probe(folder / item['file'])
            seconds = float(info.get('format', {}).get('duration', 0))
            streams = info.get('streams', [])
            media = [s for s in streams if s.get('codec_type') == ('video' if kind == 'recording' else 'audio')]
            invalid_recording = (
                kind == 'recording'
                and (seconds < 3 or duration - seconds > MAX_RECORDING_TAIL_FREEZE_SECONDS)
            )
            if (not media or not math.isfinite(seconds) or seconds <= 0 or seconds > 120
                    or invalid_recording
                    or (kind == 'narration' and seconds > duration)):
                raise VideoError(
                    'Asset stream/duration invalid: recording may freeze its final '
                    'real frame for at most 10 seconds; narration must not exceed video'
                )
            if kind == 'recording' and (media[0].get('width', 0) < 240 or media[0].get('height', 0) < 240 or max(media[0]['width'], media[0]['height']) > 4096):
                raise VideoError('Recording geometry outside 240..4096 pixels')

    def _verify_output(self, job, folder):
        path = folder / 'video.mp4'
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_ASSET:
            raise VideoError('Output missing or too large')
        info = probe(path)
        videos = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
        if len(videos) != 1:
            raise VideoError('Expected one output video stream')
        video = videos[0]
        seconds = float(info.get('format', {}).get('duration', 0))
        if (video.get('width'), video.get('height'), video.get('avg_frame_rate'), video.get('codec_name')) != (1080, 1920, '30/1', 'h264') or not math.isfinite(seconds) or abs(seconds - job['brief']['duration_seconds']) > 0.1:
            raise VideoError('Output geometry, codec, fps, or duration mismatch')
        preview = folder / 'preview.png'
        if preview.is_symlink() or not preview.is_file() or not 0 < preview.stat().st_size < 20 * 1024 * 1024:
            raise VideoError('Preview missing or too large')

    def _node_render(self, job, target):
        if not self.browser or not Path(self.browser).is_file():
            raise VideoError('Configure an installed headless browser with --browser; runtime downloads disabled')
        folder = self.root / 'jobs' / job['id']
        recording_info = probe(folder / job['assets']['recording']['file'])
        recording_seconds = float(
            recording_info.get('format', {}).get('duration', 0)
        )
        request = {
            'brief': job['brief'],
            'product': job['product'],
            'media': {'recording_duration_seconds': recording_seconds},
            'assets': {
                kind: str(folder / item['file'])
                for kind, item in job['assets'].items()
            },
            'output': str(target),
            'browser': str(Path(self.browser).resolve()),
        }
        atomic_json(target / 'request.json', request)
        # No credentials, model settings or arbitrary host env forwarded to Node/browser.
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(target),
               'TMPDIR': str(target), 'LANG': 'en_US.UTF-8', 'NODE_ENV': 'production'}
        run_process(['node', str(ROOT / 'video/render.mjs'), str(target / 'request.json')], timeout=960, env=env)
        (target / 'request.json').unlink()

    def _render(self, state, job, renderer):
        if 'upload' in job or (self.root / 'jobs' / job['id'] / 'youtube-session.json').exists() or (self.root / 'jobs' / job['id'] / 'youtube-session.json').is_symlink():
            raise VideoError('Upload evidence exists; reconcile first, never re-render')
        if due_time(job['brief']) > self.clock():
            raise VideoError('Job is not due yet')
        folder = self.root / 'jobs' / job['id']
        if job['status'] == 'rendered':
            self._check_assets(job)
            result = job['result']
            if not result or result['render_key'] != self._render_key(job):
                raise VideoError('Renderer inputs changed; enqueue a new idempotency key')
            for name in ['video.mp4', 'preview.png']:
                if file_hash(folder / name) != result['sha256'][name]:
                    raise VideoError('Cached output changed; enqueue a new job')
            self._verify_output(job, folder)
            return job
        if job['status'] not in {'queued', 'failed', 'blocked'}:
            raise VideoError('Job cannot render from this state')
        try:
            self._check_assets(job)
        except VideoError:
            job.update(status='blocked', error='asset_integrity')
            atomic_json(self.state_path, state)
            raise
        render_key = self._render_key(job)
        job.update(status='rendering', error=None, result=None)
        atomic_json(self.state_path, state)
        try:
            self._probe_inputs(job)
            with tempfile.TemporaryDirectory(prefix='.render-', dir=self.root) as temp:
                target = Path(temp)
                (renderer or self._node_render)(job, target)
                self._verify_output(job, target)
                self._check_assets(job)
                if render_key != self._render_key(job):
                    raise VideoError('Renderer inputs changed during render')
                hashes = {name: file_hash(target / name) for name in ['video.mp4', 'preview.png']}
                result = dict(schema_version=1, job_id=job['id'], render_key=render_key,
                              sha256=hashes, width=1080, height=1920, fps=30,
                              duration_seconds=job['brief']['duration_seconds'],
                              test_only=job['brief']['test_only'], upload_eligible=job['upload_eligible'])
                for name in hashes:
                    with (target / name).open('rb') as stream:
                        os.fsync(stream.fileno())
                    os.replace(target / name, folder / name)
                atomic_json(folder / 'result.json', result)
                job.update(status='rendered', result=result, error=None)
                atomic_json(self.state_path, state)
                return job
        except Exception as exc:
            job.update(status='failed', result=None, error='render_failed')
            atomic_json(self.state_path, state)
            raise VideoError('Render failed; inspect local setup/media and retry this job') from exc

    def _render_key(self, job):
        files = [ROOT / 'video/package-lock.json', ROOT / 'video/render.mjs', ROOT / 'video/tsconfig.json', Path(__file__)]
        files += sorted((ROOT / 'video/src').rglob('*'))
        return digest({'payload': job['payload_hash'], 'renderer': {str(p.relative_to(ROOT)): file_hash(p) for p in files if p.is_file()}})

    def render(self, job_id, *, renderer=None):
        with self.lock():
            state = self._read()
            if job_id not in state['jobs']:
                raise VideoError('Unknown job id')
            return self._render(state, state['jobs'][job_id], renderer)

    def upload_candidate(self, job_id):
        """Phase-2 handoff only: verified metadata/artifacts, never a provider action."""
        with self.lock():
            state = self._read()
            job = state['jobs'].get(job_id)
            if not job or job['status'] != 'rendered' or job['brief']['test_only']:
                raise VideoError('Only a verified production render can be an upload candidate')
            self._render(state, job, None)  # Cached-only branch verifies result; cannot render here.
            brief = job['brief']
            return dict(schema_version=1, job_id=job_id, idempotency_key=brief['idempotency_key'],
                        render_key=job['result']['render_key'], test_only=False,
                        source={key: brief[key] for key in ['app_id', 'topic_id']},
                        product=job['product'],
                        metadata={key: brief[key] for key in ['title', 'description', 'locale', 'due_at', 'timezone']},
                        artifacts={name: {'path': str(self.root / 'jobs' / job_id / name), 'sha256': value}
                                   for name, value in job['result']['sha256'].items()})

    def worker(self, *, dry_run=False, renderer=None):
        def candidate(state):
            jobs = [j for j in state['jobs'].values() if j['status'] == 'queued' and due_time(j['brief']) <= self.clock()]
            return min(jobs, key=lambda j: (due_time(j['brief']), j['id']), default=None)
        if dry_run:
            return candidate(self._read())  # No lock creation, probes, subprocess, or network.
        with self.lock():
            state = self._read()
            interrupted = [j for j in state['jobs'].values() if j['status'] in {'rendering', 'uploading'}]
            for job in interrupted:
                job.update(status='blocked', error='interrupted_operation_requires_review')
            if interrupted:
                atomic_json(self.state_path, state)
            job = candidate(state)
            return self._render(state, job, renderer) if job else None
