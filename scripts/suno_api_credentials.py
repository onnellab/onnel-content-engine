"""Secure local storage for the official Suno Platform API key."""
from __future__ import annotations

import ctypes as C

from short_video_credentials import CredentialError, MacKeychain

SERVICE = "com.onnellab.content-engine.suno-platform"
ACCOUNT = "aether_inn"
MAX_SECRET = 8192


def validate_api_key(value: str) -> str:
    if not isinstance(value, str):
        raise CredentialError("suno_api_key_invalid")
    value = value.strip()
    if not value or len(value) > MAX_SECRET:
        raise CredentialError("suno_api_key_invalid")
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise CredentialError("suno_api_key_invalid")
    return value


class SunoKeychain(MacKeychain):
    """One generic-password item dedicated to the Aether Inn Suno API key."""

    def __init__(self, *, interactive: bool = False):
        super().__init__(service=SERVICE, account=ACCOUNT, interactive=interactive)

    @staticmethod
    def _check(code):
        if code == 0:
            return
        if code == -25300:
            raise CredentialError("missing_suno_api_key")
        if code in (-25308, -25293, -128):
            raise CredentialError("keychain_locked_or_access_denied")
        raise CredentialError("keychain_operation_failed")

    def load(self) -> str:
        query_values = {
            **self._base(),
            "kSecReturnData": ("kCFBooleanTrue",),
            "kSecMatchLimit": ("kSecMatchLimitOne",),
        }
        result = C.c_void_p()
        with self._interaction(), self._dict(query_values) as query:
            code = self.sec.SecItemCopyMatching(query, C.byref(result))
        self._check(code)
        try:
            size = self.cf.CFDataGetLength(result)
            if not 0 < size <= MAX_SECRET:
                raise CredentialError("suno_api_key_invalid")
            raw = C.string_at(self.cf.CFDataGetBytePtr(result), size)
            try:
                value = raw.decode("ascii")
            except UnicodeDecodeError:
                raise CredentialError("suno_api_key_invalid") from None
            return validate_api_key(value)
        finally:
            if result:
                self.cf.CFRelease(result)

    def save(self, api_key: str) -> None:
        raw = validate_api_key(api_key).encode("ascii")
        with self._interaction(), self._dict(self._base()) as query, self._dict({"kSecValueData": raw}) as values:
            code = self.sec.SecItemUpdate(query, values)
            if code == -25300:
                with self._dict({**self._base(), "kSecValueData": raw}) as item:
                    code = self.sec.SecItemAdd(item, None)
            self._check(code)


def credential_status(*, store=None) -> dict:
    """Attribute-only readiness; never loads or returns the API key."""
    store = store if store is not None else SunoKeychain()
    try:
        configured = store.present()
        return {
            "provider": "suno_platform",
            "source": "macos_keychain",
            "configured": configured,
            "network_verified": False,
        }
    except CredentialError as exc:
        return {
            "provider": "suno_platform",
            "source": "macos_keychain",
            "configured": False,
            "network_verified": False,
            "error": str(exc),
        }
