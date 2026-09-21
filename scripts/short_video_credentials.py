"""One atomic YouTube credential bundle; never put secrets in argv or diagnostics."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
import json
import os
import re
import sys
import threading

from short_video_pipeline import VideoError

NAMES = ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_CHANNEL_ID')
FIELDS = ('client_id', 'client_secret', 'refresh_token', 'channel_id')
SERVICE = 'com.onnellab.content-engine.youtube'
ACCOUNT = 'onnellab'
SCOPES = ('https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly')
MAX_BUNDLE = 32768
_LOCK = threading.RLock()


class CredentialError(VideoError):
    pass


def strict_json(raw: bytes | str) -> dict:
    if not isinstance(raw, (str, bytes)) or len(raw) > MAX_BUNDLE:
        raise CredentialError('credential_document_invalid')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate')
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise CredentialError('credential_document_invalid') from None


def channel_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', value):
        raise CredentialError('invalid_expected_channel')
    return value


def validate_bundle(bundle):
    required = {'schema_version', *FIELDS, 'channel_title', 'scopes', 'verified_at'}
    if not isinstance(bundle, dict) or set(bundle) != required or type(bundle['schema_version']) is not int or bundle['schema_version'] != 1:
        raise CredentialError('keychain_bundle_invalid')
    for name in FIELDS:
        value = bundle[name]
        if not isinstance(value, str) or not value or len(value) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise CredentialError('keychain_bundle_invalid')
    channel_id(bundle['channel_id'])
    if not isinstance(bundle['channel_title'], str) or len(bundle['channel_title']) > 256:
        raise CredentialError('keychain_bundle_invalid')
    if not isinstance(bundle['scopes'], list) or not all(isinstance(x, str) for x in bundle['scopes']) or not set(SCOPES).issubset(bundle['scopes']):
        raise CredentialError('youtube_scopes_missing')
    if not isinstance(bundle['verified_at'], str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', bundle['verified_at']):
        raise CredentialError('keychain_bundle_invalid')
    return bundle


class MacKeychain:
    """Security.framework directly, scoped generic-password item, no subprocess secrets."""
    def __init__(self, *, service=SERVICE, account=ACCOUNT, interactive=False):
        if sys.platform != 'darwin':
            raise CredentialError('keychain_requires_macos')
        self.service, self.account, self.interactive = service, account, interactive
        try:
            self.cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
            self.sec = C.CDLL('/System/Library/Frameworks/Security.framework/Security')
            signatures = {
                'CFStringCreateWithCString': ([C.c_void_p, C.c_char_p, C.c_uint32], C.c_void_p),
                'CFDataCreate': ([C.c_void_p, C.c_void_p, C.c_long], C.c_void_p),
                'CFDataGetLength': ([C.c_void_p], C.c_long),
                'CFDataGetBytePtr': ([C.c_void_p], C.c_void_p),
                'CFDictionaryCreateMutable': ([C.c_void_p, C.c_long, C.c_void_p, C.c_void_p], C.c_void_p),
                'CFDictionarySetValue': ([C.c_void_p, C.c_void_p, C.c_void_p], None),
                'CFRelease': ([C.c_void_p], None),
            }
            for name, (args, ret) in signatures.items():
                function = getattr(self.cf, name); function.argtypes = args; function.restype = ret
            for name, args in [('SecItemCopyMatching', [C.c_void_p, C.POINTER(C.c_void_p)]),
                               ('SecItemAdd', [C.c_void_p, C.POINTER(C.c_void_p)]),
                               ('SecItemUpdate', [C.c_void_p, C.c_void_p]), ('SecItemDelete', [C.c_void_p]),
                               ('SecKeychainSetUserInteractionAllowed', [C.c_bool]),
                               ('SecKeychainGetUserInteractionAllowed', [C.POINTER(C.c_bool)])]:
                function = getattr(self.sec, name); function.argtypes = args; function.restype = C.c_int32
        except (OSError, AttributeError):
            raise CredentialError('keychain_unavailable') from None

    def _symbol(self, name):
        lib = self.cf if name.startswith('kCF') else self.sec
        return C.c_void_p.in_dll(lib, name).value

    @contextmanager
    def _dict(self, values):
        # No-retain dictionary; hold and release our CFString/CFData values explicitly.
        refs = []
        query = self.cf.CFDictionaryCreateMutable(None, 0, None, None)
        if not query:
            raise CredentialError('keychain_unavailable')
        try:
            for key, value in values.items():
                if isinstance(value, tuple):
                    obj = self._symbol(value[0])
                elif isinstance(value, bytes):
                    obj = self.cf.CFDataCreate(None, value, len(value)); refs.append(obj)
                else:
                    obj = self.cf.CFStringCreateWithCString(None, value.encode('utf-8'), 0x08000100); refs.append(obj)
                if not obj:
                    raise CredentialError('keychain_unavailable')
                self.cf.CFDictionarySetValue(query, self._symbol(key), obj)
            yield query
        finally:
            self.cf.CFRelease(query)
            for obj in refs:
                if obj: self.cf.CFRelease(obj)

    def _base(self):
        return {'kSecClass': ('kSecClassGenericPassword',), 'kSecAttrService': self.service,
                'kSecAttrAccount': self.account, 'kSecAttrSynchronizable': ('kCFBooleanFalse',)}

    @contextmanager
    def _interaction(self):
        # Workers fail immediately when Keychain needs user interaction; never unlock it.
        with _LOCK:
            previous = C.c_bool()
            self._check(self.sec.SecKeychainGetUserInteractionAllowed(C.byref(previous)))
            self._check(self.sec.SecKeychainSetUserInteractionAllowed(self.interactive))
            try:
                yield
            finally:
                self.sec.SecKeychainSetUserInteractionAllowed(previous.value)

    @staticmethod
    def _check(code):
        if code == 0: return
        if code == -25300: raise CredentialError('missing_youtube_credentials')
        if code in (-25308, -25293, -128): raise CredentialError('keychain_locked_or_access_denied')
        raise CredentialError('keychain_operation_failed')

    def present(self):
        """Attribute-only existence query; does not retrieve any credential payload."""
        with self._interaction(), self._dict(self._base()) as query:
            code = self.sec.SecItemCopyMatching(query, None)
        if code == -25300: return False
        self._check(code)
        return True

    def load(self):
        query_values = {**self._base(), 'kSecReturnData': ('kCFBooleanTrue',), 'kSecMatchLimit': ('kSecMatchLimitOne',)}
        result = C.c_void_p()
        with self._interaction(), self._dict(query_values) as query:
            code = self.sec.SecItemCopyMatching(query, C.byref(result))
        self._check(code)
        try:
            size = self.cf.CFDataGetLength(result)
            if not 0 < size <= MAX_BUNDLE: raise CredentialError('keychain_bundle_invalid')
            raw = C.string_at(self.cf.CFDataGetBytePtr(result), size)
            return validate_bundle(strict_json(raw))
        finally:
            if result: self.cf.CFRelease(result)

    def save(self, bundle):
        raw = json.dumps(validate_bundle(bundle), separators=(',', ':'), ensure_ascii=False).encode()
        if len(raw) > MAX_BUNDLE: raise CredentialError('keychain_bundle_invalid')
        with self._interaction(), self._dict(self._base()) as query, self._dict({'kSecValueData': raw}) as values:
            code = self.sec.SecItemUpdate(query, values)
            if code == -25300:
                with self._dict({**self._base(), 'kSecValueData': raw}) as item:
                    code = self.sec.SecItemAdd(item, None)
            self._check(code)

    def delete(self):
        with self._interaction(), self._dict(self._base()) as query:
            code = self.sec.SecItemDelete(query)
        if code != -25300: self._check(code)


def resolve_credentials(*, store=None, environ=None):
    """Explicit environment mode never mixes values from different credential sources."""
    environ = os.environ if environ is None else environ
    source = environ.get('ONNELLAB_YOUTUBE_CREDENTIAL_SOURCE', 'keychain')
    if source == 'environment':
        values = {name: environ.get(name, '') for name in NAMES}
        if not all(values.values()): raise CredentialError('missing_youtube_credentials')
        channel_id(values['YOUTUBE_CHANNEL_ID'])
        return values
    if source != 'keychain': raise CredentialError('youtube_credential_source_invalid')
    bundle = (store if store is not None else MacKeychain()).load()
    validate_bundle(bundle)
    return {name: bundle[field] for name, field in zip(NAMES, FIELDS)}


def credential_status(*, store=None, environ=None):
    """No refresh, network, token loading, or secret-bearing values in readiness."""
    environ = os.environ if environ is None else environ
    source = environ.get('ONNELLAB_YOUTUBE_CREDENTIAL_SOURCE', 'keychain')
    result = {'source': source, 'required': list(NAMES), 'network_verified': False}
    try:
        if source == 'environment':
            result['missing'] = [name for name in NAMES if not environ.get(name)]
            result['configured'] = not result['missing']
        elif source == 'keychain':
            present = (store if store is not None else MacKeychain()).present()
            result.update(configured=present, missing=[] if present else list(NAMES))
        else:
            raise CredentialError('youtube_credential_source_invalid')
    except CredentialError as exc:
        result.update(configured=False, missing=list(NAMES), error=str(exc))
    return result
