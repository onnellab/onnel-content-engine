"""Bounded YouTube adapter. No SDK, login, scheduler, or secret-bearing diagnostics."""
from datetime import datetime, timezone
import json
import os
import re
import time
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from short_video_pipeline import VideoError, atomic_json, canonical, digest, file_hash, load_json, MAX_ASSET
from short_video_credentials import CredentialError, resolve_credentials, credential_status
from youtube_profiles import profile_id, require_content_profile, content_profile

NAMES = ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_CHANNEL_ID')
API = 'https://www.googleapis.com/youtube/v3/'
INSERT = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'
CHUNK = 1024 * 1024  # Multiple of Google's 256 KiB requirement.


class UploadError(VideoError):
    pass


def check_config(env=None):
    if env is None:
        return credential_status()
    return {'required': list(NAMES), 'missing': [n for n in NAMES if not env.get(n)]}


def session_url(url):
    try:
        p = urlsplit(url)
        query = parse_qs(p.query, strict_parsing=True)
        if (p.scheme != 'https' or p.netloc != 'www.googleapis.com' or
                p.path != '/upload/youtube/v3/videos' or p.fragment or
                query.get('uploadType') != ['resumable'] or len(query.get('upload_id', [])) != 1 or
                not query['upload_id'][0] or len(url) > 8192 or any(ord(c) <= 32 for c in url)):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise UploadError('invalid_session_url') from None
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transport(method, url, headers, body):
    """Never forward credentials through redirects; never expose response bodies/errors."""
    try:
        req = Request(url, data=body, headers=headers, method=method)
        try:
            response = build_opener(NoRedirect).open(req, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise UploadError('provider_response_too_large')
            return response.code, dict(response.headers.items()), raw
    except (OSError, URLError, ValueError):
        raise UploadError('network_uncertain') from None


class YouTube:
    def __init__(self, *, env=None, send=transport, sleep=time.sleep, profile="onnellab"):
        self.profile = profile_id(profile)
        if env is None:
            try:
                env = resolve_credentials(profile=self.profile)
            except CredentialError as exc:
                raise UploadError(str(exc)) from None
        if check_config(env)['missing']:
            raise UploadError('missing_youtube_credentials')
        self.channel = env['YOUTUBE_CHANNEL_ID']
        if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', self.channel):
            raise UploadError('invalid_expected_channel')
        self.env, self.send, self.sleep, self.token = env, send, sleep, None

    def request(self, method, url, body=None, headers=None, retry=False):
        for attempt in range(3 if retry else 1):
            try:
                code, hs, raw = self.send(method, url, headers or {}, body)
            except Exception:
                raise UploadError('network_uncertain') from None
            hs = {k.lower(): v for k, v in hs.items()}
            if code == 308 and url.startswith('https://www.googleapis.com/upload/'):
                if 'location' in hs:
                    raise UploadError('redirect_rejected')
                return code, hs, {}
            if 300 <= code < 400:
                raise UploadError('redirect_rejected')
            if code in (429, 500, 502, 503, 504) and retry and attempt < 2:
                self.pause(hs, 2 ** attempt)
                continue
            if code >= 400:
                detail = None
                try:
                    error_doc = json.loads(raw) if raw else {}
                    errors = error_doc.get('error', {}).get('errors', []) if isinstance(error_doc, dict) else []
                    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                        detail = errors[0].get('reason')
                except (ValueError, TypeError, AttributeError):
                    detail = None
                if detail == 'insufficientPermissions':
                    raise UploadError('insufficient_permissions')
                if detail == 'commentsDisabled':
                    raise UploadError('comments_disabled')
                reasons = {401: 'auth_required', 403: 'permission_or_quota_denied',
                           404: 'session_or_video_missing', 410: 'session_expired', 429: 'rate_limited'}
                raise UploadError(reasons.get(code, 'provider_unavailable' if code >= 500 else 'provider_rejected'))
            try:
                data = json.loads(raw) if raw else {}
                if not isinstance(data, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                raise UploadError('invalid_provider_response') from None
            return code, hs, data
        raise UploadError('provider_unavailable')

    def pause(self, headers, fallback=0):
        value = headers.get('retry-after')
        if value is not None and (not value.isdigit() or int(value) > 30):
            raise UploadError('retry_later')
        delay = max(fallback, int(value or 0))
        if delay:
            self.sleep(delay)

    def verify(self):
        _, _, token = self.request('POST', 'https://oauth2.googleapis.com/token',
            urlencode({'client_id': self.env['YOUTUBE_CLIENT_ID'], 'client_secret': self.env['YOUTUBE_CLIENT_SECRET'],
                       'refresh_token': self.env['YOUTUBE_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode(),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        self.token = token.get('access_token')
        if not isinstance(self.token, str) or not self.token or '\n' in self.token or '\r' in self.token:
            raise UploadError('auth_required')
        _, _, data = self.request('GET', API + 'channels?part=id&mine=true', headers=self.headers(), retry=True)
        if [i.get('id') for i in data.get('items', [])] != [self.channel]:
            raise UploadError('foreign_channel')
        return {'channel_verified': True}

    def headers(self, **extra):
        return {'Authorization': 'Bearer ' + self.token, **extra}

    def initiate(self, metadata, size):
        _, headers, _ = self.request('POST', INSERT, canonical(metadata), self.headers(**{
            'Content-Type': 'application/json; charset=UTF-8', 'X-Upload-Content-Type': 'video/mp4',
            'X-Upload-Content-Length': str(size)}))
        return session_url(headers.get('location'))

    def probe(self, url, size):
        return self.request('PUT', session_url(url), b'', self.headers(**{
            'Content-Length': '0', 'Content-Range': f'bytes */{size}'}), retry=True)

    def chunk(self, url, data, start, total):
        return self.request('PUT', session_url(url), data, self.headers(**{
            'Content-Type': 'video/mp4', 'Content-Length': str(len(data)),
            'Content-Range': f'bytes {start}-{start + len(data) - 1}/{total}'}))

    def video(self, video_id):
        _, _, data = self.request('GET', API + 'videos?' + urlencode({
            'part': 'snippet,status,processingDetails', 'id': video_id}), headers=self.headers(), retry=True)
        items = data.get('items', [])
        if len(items) != 1 or items[0].get('id') != video_id or items[0].get('snippet', {}).get('channelId') != self.channel:
            raise UploadError('video_missing_or_foreign_channel')
        return items[0]


def timestamp(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
            raise ValueError()
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise UploadError('invalid_publish_at') from None


def provider_timestamp(value):
    """Normalize provider RFC 3339 timestamps; caller scheduling remains strict UTC."""
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)", value):
            raise ValueError()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        raise UploadError("invalid_provider_publish_at") from None


def metadata(job, choices, now, *, executing=True):
    if type(choices.get('made_for_kids')) is not bool or type(choices.get('synthetic_media')) is not bool:
        raise UploadError('explicit_disclosures_required')
    privacy = choices.get('privacy', 'private')
    if privacy not in ('private', 'unlisted', 'public'):
        raise UploadError('invalid_privacy')
    publish = choices.get('publish_at')
    if (privacy != 'private' or publish) and choices.get('publish_approved') is not True:
        raise UploadError('publish_approval_required')
    if publish and (privacy != 'private' or (executing and timestamp(publish) <= now)):
        raise UploadError('stale_or_nonprivate_schedule')
    brief = job['brief']
    title, description = brief['title'], brief['description']
    if not title.strip() or len(title) > 100 or len(description.encode()) > 5000 or any(c in title + description for c in '<>'):
        raise UploadError('invalid_metadata_byte_limits')
    status = {'privacyStatus': privacy, 'selfDeclaredMadeForKids': choices['made_for_kids'],
              'containsSyntheticMedia': choices['synthetic_media']}
    if publish:
        timestamp(publish)
        status['publishAt'] = publish
    return {'snippet': {'title': title, 'description': description, 'defaultLanguage': brief['locale'], 'categoryId': '10' if content_profile(brief)=='aether_inn' else '27'}, 'status': status}


class Uploader:
    def __init__(self, queue, api_factory=YouTube):
        self.q, self.api_factory = queue, api_factory

    def artifact(self, job):
        if job['brief']['test_only'] or not job.get('result') or not job['upload_eligible']:
            raise UploadError('production_render_required')
        folder = self.q.root / 'jobs' / job['id']
        result = job['result']
        if (result.get('job_id') != job['id'] or result.get('test_only') is not False or
                result.get('upload_eligible') is not True):
            raise UploadError('production_render_required')
        path = folder / 'video.mp4'
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_ASSET or file_hash(path) != result['sha256']['video.mp4']:
            raise UploadError('render_integrity')
        return path

    def bind_approval_locked(self, state, job, choices, *, mode='manual', policy_hash=None):
        if job['status'] not in {'rendered', 'blocked'} or job.get('upload'):
            raise UploadError('approval_requires_unuploaded_render')
        self.artifact(job)
        self.q._render(state, job, None)
        body = metadata(job, choices, self.q.clock())
        approval = {'render_hash': job['result']['sha256']['video.mp4'],
                    'payload_hash': job['payload_hash'], 'choices': choices,
                    'metadata_hash': digest(body), 'approved_at': self.q.clock().isoformat(),
                    'mode': mode}
        if policy_hash is not None:
            if not re.fullmatch(r'[0-9a-f]{64}', policy_hash):
                raise UploadError('invalid_automatic_policy_hash')
            approval['policy_hash'] = policy_hash
        job['approval'] = approval
        job['error'] = None
        atomic_json(self.q.state_path, state)
        return job

    def approve(self, job_id, choices, *, execute=False):
        if not execute:
            return {'dry_run': True, 'action': 'approve', 'job_id': job_id}
        with self.q.lock():
            state = self.q._read()
            return self.bind_approval_locked(state, self.job(state, job_id), choices)

    @staticmethod
    def job(state, job_id):
        if job_id not in state['jobs']:
            raise UploadError('unknown_job')
        return state['jobs'][job_id]

    def run(self, job_id, *, execute=False, reconcile=False):
        if not execute:
            return {'dry_run': True, 'action': 'reconcile' if reconcile else 'upload', 'job_id': job_id}
        with self.q.lock():
            state = self.q._read()
            return self.run_locked(state, self.job(state, job_id), reconcile=reconcile)

    def run_locked(self, state, job, *, reconcile=False, api=None):
        session_path = self.q.root / 'jobs' / job['id'] / 'youtube-session.json'
        save = lambda: atomic_json(self.q.state_path, state)
        started = time.monotonic()
        try:
            path = self.artifact(job)
            approval = job.get('approval', {})
            if approval.get('render_hash') != job['result']['sha256']['video.mp4'] or approval.get('payload_hash') != job['payload_hash']:
                raise UploadError('upload_approval_required')
            if approval.get('mode') not in {'manual', 'automatic_fail_closed'}:
                raise UploadError('approval_mode_invalid')
            if approval.get('mode') == 'automatic_fail_closed' and not re.fullmatch(r'[0-9a-f]{64}', approval.get('policy_hash', '')):
                raise UploadError('automatic_policy_hash_missing')
            upload = job.get('upload')
            # After durable ID, only observe it. A past schedule must not prevent observation.
            body = metadata(job, approval['choices'], self.q.clock(), executing=not bool(upload))
            if digest(body) != approval['metadata_hash']:
                raise UploadError('approval_metadata_changed')
            if not upload and job['status'] not in {'rendered', 'blocked'}:
                raise UploadError('complete_render_required')
            api = api or self.api_factory()
            require_content_profile(job['brief'], getattr(api, 'profile', 'onnellab'))
            if not api.token:
                api.verify()
            if upload and upload.get('channel_id') != api.channel:
                raise UploadError('expected_channel_changed')
            if upload and upload.get('video_id'):
                return self.observe(job, api, save)
            if not upload:
                if reconcile or session_path.exists():
                    raise UploadError('manual_reconcile_required')
                # Persist intent BEFORE POST. Lost initiation ACK cannot create a second insert.
                upload = job['upload'] = {'phase': 'initiating', 'channel_id': api.channel,
                    'size': path.stat().st_size, 'sha256': file_hash(path)}
                job.update(status='uploading', error=None)
                save()
                url = api.initiate(body, upload['size'])
                atomic_json(session_path, {'url': url})  # 0600 + fsync before any bytes
                upload['phase'] = 'session_ready'
                save()
            if session_path.is_symlink() or not session_path.is_file():
                raise UploadError('manual_reconcile_required')
            if session_path.stat().st_mode & 0o077:
                raise UploadError('unsafe_session_permissions')
            url = session_url(load_json(session_path)['url'])
            if path.stat().st_size != upload['size'] or file_hash(path) != upload['sha256']:
                raise UploadError('render_integrity')
            response = api.probe(url, upload['size'])  # Always probe on restart, never trust offset.
            budget = (upload['size'] + CHUNK - 1) // CHUNK + 4
            failures = 0
            while True:
                code, headers, data = response
                if code in (200, 201):
                    video_id = data.get('id')
                    if not isinstance(video_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                        raise UploadError('manual_reconcile_required')
                    upload.update(video_id=video_id, phase='accepted')
                    job.update(status='accepted', error=None)
                    save()  # Durable ID before videos.list; no path back to insert.
                    return self.observe(job, api, save)
                if code != 308:
                    raise UploadError('unexpected_upload_response')
                if time.monotonic() - started >= 900:
                    raise UploadError('transfer_time_budget_exhausted')
                match = re.fullmatch(r'bytes=0-(\d+)', headers.get('range', ''))
                if 'range' in headers and not match:
                    raise UploadError('invalid_upload_range')
                api.pause(headers)
                offset = int(match[1]) + 1 if match else 0
                if not 0 <= offset < upload['size'] or budget <= 0:
                    raise UploadError('manual_reconcile_required')
                # A stale schedule may be probed/reconciled, but never sent again.
                metadata(job, approval['choices'], self.q.clock(), executing=True)
                upload.update(phase='sending', confirmed_bytes=offset)
                job.update(status='uploading', error=None)
                save()
                self.artifact(job)  # Recheck complete hash and size before each send.
                if path.stat().st_size != upload['size']:
                    raise UploadError('render_integrity')
                with path.open('rb') as stream:
                    stream.seek(offset)
                    chunk = stream.read(CHUNK)
                budget -= 1
                try:
                    response = api.chunk(url, chunk, offset, upload['size'])
                except UploadError as exc:
                    if str(exc) not in {'network_uncertain', 'rate_limited', 'provider_unavailable'} or failures >= 2:
                        raise
                    failures += 1
                    api.sleep(2 ** (failures - 1))
                    response = api.probe(url, upload['size'])
        except (Exception, KeyboardInterrupt) as exc:
            code = str(exc) if isinstance(exc, UploadError) else 'operation_interrupted_or_storage_error'
            job.update(status='reconcile_required' if job.get('upload') or session_path.exists() else 'blocked', error=code)
            save()
            return job

    def observe(self, job, api, save):
        upload = job['upload']
        video = api.video(upload['video_id'])
        status = video.get('status', {})
        processing = video.get('processingDetails', {}).get('processingStatus')
        provider_upload = status.get('uploadStatus')
        privacy = status.get('privacyStatus')
        publish = status.get('publishAt')
        # Store only allowlisted facts, never raw provider bodies.
        upload['observed'] = {'upload_status': provider_upload if provider_upload in {'uploaded', 'processed', 'failed', 'rejected', 'deleted'} else 'unknown',
            'processing_status': processing if processing in {'processing', 'succeeded', 'failed', 'terminated'} else 'unknown',
            'privacy': privacy if privacy in {'private', 'public', 'unlisted'} else 'unknown'}
        if provider_upload in {'failed', 'rejected', 'deleted'} or processing in {'failed', 'terminated'}:
            job['status'] = 'rejected'
        elif provider_upload != 'processed' or processing != 'succeeded':
            job['status'] = 'processing'
        elif privacy == 'public':
            job['status'] = 'published'
        elif privacy == 'unlisted':
            job['status'] = 'uploaded_unlisted'
        elif privacy == 'private':
            choices = job['approval']['choices']
            if publish and choices.get('publish_at') and provider_timestamp(publish) > self.q.clock() and provider_timestamp(publish) == timestamp(choices['publish_at']):
                job['status'] = 'scheduled'
                upload['observed']['publish_at'] = choices['publish_at']
            elif choices.get('privacy', 'private') != 'private' or choices.get('publish_at'):
                job['status'] = 'forced_private'
            else:
                job['status'] = 'uploaded_private'
        else:
            raise UploadError('unknown_provider_status')
        job['error'] = None
        upload['phase'] = 'accepted'
        save()
        return job
