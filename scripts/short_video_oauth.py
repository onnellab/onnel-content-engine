"""Desktop OAuth with PKCE; no secrets are returned to the browser."""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit, parse_qs
from short_video_credentials import CredentialError, SCOPES, strict_json, channel_id, validate_bundle
from short_video_youtube import transport
from youtube_profiles import profile_id, ANALYTICS_SCOPE

AUTH = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN = 'https://oauth2.googleapis.com/token'
CHANNELS = 'https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true'
TTL = 600

class OAuthError(CredentialError):
    pass

def _secret(value, name):
    if not isinstance(value, str) or not value or len(value) > 8192 or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise OAuthError(name)
    return value

def desktop_client(raw):
    document = strict_json(raw)
    if set(document) != {'installed'} or not isinstance(document['installed'], dict):
        raise OAuthError('desktop_oauth_json_required')
    client = document['installed']
    client_id = _secret(client.get('client_id'), 'invalid_oauth_client')
    secret = _secret(client.get('client_secret'), 'invalid_oauth_client')
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', client_id):
        raise OAuthError('invalid_oauth_client')
    if client.get('auth_uri') not in (None, AUTH, 'https://accounts.google.com/o/oauth2/auth') or client.get('token_uri') not in (None, TOKEN):
        raise OAuthError('untrusted_oauth_endpoint')
    return {'client_id': client_id, 'client_secret': secret}

def local_redirect(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
                or parsed.netloc != f'127.0.0.1:{parsed.port}' or parsed.path != '/oauth/callback'
                or parsed.query or parsed.fragment):
            raise ValueError()
    except (ValueError, TypeError):
        raise OAuthError('invalid_oauth_loopback') from None
    return value

def _request(send, method, url, *, body=None, token=None):
    if url not in (TOKEN, CHANNELS):
        raise OAuthError('untrusted_oauth_endpoint')
    headers = {'Content-Type': 'application/x-www-form-urlencoded'} if body is not None else {}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + _secret(token, 'invalid_access_token')
    try:
        code, _headers, raw = send(method, url, headers, urlencode(body).encode() if body is not None else None)
    except Exception:
        raise OAuthError('oauth_network_failed') from None
    if 300 <= code < 400: raise OAuthError('oauth_redirect_rejected')
    if code >= 400:
        raise OAuthError({400: 'oauth_reconnect_required', 401: 'oauth_reconnect_required',
                          403: 'youtube_api_disabled_or_permission_denied', 429: 'oauth_rate_limited'}.get(code, 'oauth_provider_failed'))
    try:
        return strict_json(raw)
    except CredentialError:
        raise OAuthError('oauth_provider_response_invalid') from None

def verify_channel(send, access_token, expected):
    data = _request(send, 'GET', CHANNELS, token=access_token)
    items = data.get('items')
    if (not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict)
            or items[0].get('id') != expected or data.get('nextPageToken')):
        raise OAuthError('youtube_channel_mismatch')
    snippet = items[0].get('snippet', {})
    title = snippet.get('title', '') if isinstance(snippet, dict) else ''
    if not isinstance(title, str) or len(title) > 256 or any(ord(c) < 32 for c in title):
        raise OAuthError('youtube_channel_metadata_invalid')
    return title

class Connection:
    """One user-started attempt, one callback, independent expected channel binding."""
    def __init__(self, store, *, send=transport, clock=time.monotonic, profile=None, scopes=SCOPES):
        self.store, self.send, self.clock = store, send, clock
        self.profile = profile_id(profile) if profile is not None else None
        self.scopes = tuple(scopes)
        self.pending = None

    def begin(self, raw_client, expected_channel, redirect):
        client = desktop_client(raw_client)
        expected = channel_id(expected_channel)
        redirect = local_redirect(redirect)
        verifier = secrets.token_urlsafe(48)
        state = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        self.pending = dict(client=client, expected=expected, redirect=redirect, verifier=verifier,
                            state=state, expires=self.clock() + TTL)
        return AUTH + '?' + urlencode({'client_id': client['client_id'], 'redirect_uri': redirect,
            'response_type': 'code', 'scope': ' '.join(self.scopes), 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256',
            'access_type': 'offline', 'prompt': 'consent select_account'})

    def complete(self, query):
        pending = self.pending
        if not pending: raise OAuthError('oauth_session_missing_or_used')
        try:
            if not isinstance(query, str) or len(query) > 16384: raise ValueError()
            fields = parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=20)
            if any(len(values) != 1 for values in fields.values()): raise ValueError()
        except ValueError:
            raise OAuthError('oauth_callback_invalid') from None
        given = fields.get('state', [''])[0]
        if not given.isascii() or not secrets.compare_digest(given, pending['state']):
            raise OAuthError('oauth_state_mismatch')
        self.pending = None
        if self.clock() >= pending['expires']: raise OAuthError('oauth_session_expired')
        if 'error' in fields: raise OAuthError('oauth_consent_denied')
        code = _secret(fields.get('code', [''])[0], 'oauth_code_missing')
        token = _request(self.send, 'POST', TOKEN, body={**pending['client'], 'code': code,
            'code_verifier': pending['verifier'], 'redirect_uri': pending['redirect'],
            'grant_type': 'authorization_code'})
        access = _secret(token.get('access_token'), 'invalid_access_token')
        refresh = _secret(token.get('refresh_token'), 'offline_access_missing_reconnect')
        if str(token.get('token_type', '')).lower() != 'bearer': raise OAuthError('oauth_token_type_invalid')
        granted = token.get('scope', '')
        if not isinstance(granted, str) or not set(self.scopes).issubset(granted.split()):
            raise OAuthError('youtube_scopes_missing')
        title = verify_channel(self.send, access, pending['expected'])
        bundle = dict(schema_version=1, **pending['client'], refresh_token=refresh,
            channel_id=pending['expected'], channel_title=title, scopes=sorted(set(granted.split())),
            verified_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        if self.profile is not None:
            bundle.update(schema_version=2, profile=self.profile)
        self.store.save(validate_bundle(bundle, profile=self.profile))
        return public_status(bundle)

    def check(self):
        bundle = validate_bundle(self.store.load(), profile=self.profile)
        if not set(self.scopes).issubset(bundle['scopes']):
            raise OAuthError('youtube_scopes_missing')
        token = _request(self.send, 'POST', TOKEN, body={
            'client_id': bundle['client_id'], 'client_secret': bundle['client_secret'],
            'refresh_token': bundle['refresh_token'], 'grant_type': 'refresh_token'})
        access = _secret(token.get('access_token'), 'invalid_access_token')
        if str(token.get('token_type', '')).lower() != 'bearer':
            raise OAuthError('oauth_token_type_invalid')
        # Google may omit scope on refresh. An explicit narrower grant is never
        # reported as if it still contained the original upload permission.
        granted = token.get('scope')
        if granted is not None and (not isinstance(granted, str)
                or not set(self.scopes).issubset(granted.split())):
            raise OAuthError('youtube_scopes_missing')
        title = verify_channel(self.send, access, bundle['channel_id'])
        return public_status({**bundle, 'channel_title': title,
                              'verified_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})

    def disconnect(self):
        """Explicit local removal only; Google grant revocation is user-controlled."""
        self.pending = None
        self.store.delete()
        return {'state': 'not_connected', 'google_grant_revoked': False}

def public_status(bundle):
    return {'state': 'connected', 'channel_id': bundle['channel_id'], 'channel_title': bundle['channel_title'],
            'checked_at': bundle['verified_at'], 'channel_verified': True,
            'upload_scope': SCOPES[0] in bundle['scopes'], 'read_scope': SCOPES[1] in bundle['scopes'],
            'analytics_scope': ANALYTICS_SCOPE in bundle['scopes'], 'profile': bundle.get('profile', 'onnellab'),
            'public_upload_verified': False, 'source': 'macos_keychain'}
