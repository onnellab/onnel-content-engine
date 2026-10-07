from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_store_reviews import (  # noqa: E402
    app_store_connect_read_token_from_env,
    app_store_connect_token,
    resolve_app_store_connect_read_credentials,
)


def _fake_der_signature() -> bytes:
    r = bytes.fromhex("01" * 32)
    s = bytes.fromhex("02" * 32)
    return b"\x30\x44\x02\x20" + r + b"\x02\x20" + s


def _payload(token: str) -> dict[str, object]:
    segment = token.split(".")[1]
    raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    return json.loads(raw)


class AppStoreConnectReadCredentialsTest(unittest.TestCase):
    def test_team_key_uses_issuer_and_never_subject(self) -> None:
        token = app_store_connect_token(
            "TEAMKEY",
            "issuer-123",
            "private",
            issued_at=1_800_000_000,
            signer=lambda *_: _fake_der_signature(),
            key_type="team",
        )
        payload = _payload(token)
        self.assertEqual(payload["iss"], "issuer-123")
        self.assertNotIn("sub", payload)
        self.assertEqual(payload["aud"], "appstoreconnect-v1")

    def test_individual_key_uses_user_subject_and_never_issuer(self) -> None:
        token = app_store_connect_token(
            "INDIVIDUALKEY",
            "stale-issuer-must-be-ignored",
            "private",
            issued_at=1_800_000_000,
            signer=lambda *_: _fake_der_signature(),
            key_type="individual",
        )
        payload = _payload(token)
        self.assertEqual(payload["sub"], "user")
        self.assertNotIn("iss", payload)
        self.assertEqual(payload["aud"], "appstoreconnect-v1")

    def test_individual_key_accepts_blank_issuer(self) -> None:
        token = app_store_connect_token(
            "INDIVIDUALKEY",
            "",
            "private",
            issued_at=1_800_000_000,
            signer=lambda *_: _fake_der_signature(),
            key_type="individual",
        )
        self.assertEqual(_payload(token)["sub"], "user")

    def test_team_key_rejects_blank_issuer(self) -> None:
        with self.assertRaisesRegex(ValueError, "team key requires Issuer ID"):
            app_store_connect_token(
                "TEAMKEY",
                "",
                "private",
                signer=lambda *_: _fake_der_signature(),
                key_type="team",
            )

    def test_rejects_unknown_key_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "key type must be individual or team"):
            app_store_connect_token(
                "KEY",
                "",
                "private",
                signer=lambda *_: _fake_der_signature(),
                key_type="developer-team-id",
            )

    def test_read_namespace_wins_and_individual_ignores_stale_issuer(self) -> None:
        env = {
            "APP_STORE_CONNECT_READ_KEY_TYPE": "individual",
            "APP_STORE_CONNECT_READ_KEY_ID": "READKEY",
            "APP_STORE_CONNECT_READ_ISSUER_ID": "stale-read-issuer",
            "APP_STORE_CONNECT_READ_PRIVATE_KEY_BASE64": base64.b64encode(b"read-private").decode(),
            "APP_STORE_CONNECT_KEY_ID": "LEGACYKEY",
            "APP_STORE_CONNECT_ISSUER_ID": "legacy-issuer",
            "APP_STORE_CONNECT_PRIVATE_KEY_BASE64": base64.b64encode(b"legacy-private").decode(),
        }
        credentials = resolve_app_store_connect_read_credentials(env)
        self.assertIsNotNone(credentials)
        assert credentials is not None
        self.assertEqual(credentials["key_type"], "individual")
        self.assertEqual(credentials["key_id"], "READKEY")
        self.assertEqual(credentials["issuer_id"], "")
        self.assertEqual(credentials["private_key"], "read-private")

    def test_legacy_namespace_falls_back_as_team_key(self) -> None:
        env = {
            "APP_STORE_CONNECT_KEY_ID": "LEGACYKEY",
            "APP_STORE_CONNECT_ISSUER_ID": "legacy-issuer",
            "APP_STORE_CONNECT_PRIVATE_KEY_BASE64": base64.b64encode(b"legacy-private").decode(),
        }
        credentials = resolve_app_store_connect_read_credentials(env)
        self.assertIsNotNone(credentials)
        assert credentials is not None
        self.assertEqual(credentials["key_type"], "team")
        self.assertEqual(credentials["key_id"], "LEGACYKEY")
        self.assertEqual(credentials["issuer_id"], "legacy-issuer")
        self.assertEqual(credentials["private_key"], "legacy-private")

    def test_partial_read_namespace_fails_closed_instead_of_mixing_legacy(self) -> None:
        env = {
            "APP_STORE_CONNECT_READ_KEY_TYPE": "individual",
            "APP_STORE_CONNECT_KEY_ID": "LEGACYKEY",
            "APP_STORE_CONNECT_ISSUER_ID": "legacy-issuer",
            "APP_STORE_CONNECT_PRIVATE_KEY_BASE64": base64.b64encode(b"legacy-private").decode(),
        }
        with self.assertRaisesRegex(ValueError, "APP_STORE_CONNECT_READ_KEY_ID"):
            resolve_app_store_connect_read_credentials(env)

    def test_read_credentials_take_precedence_over_legacy_token_override(self) -> None:
        env = {
            "APP_STORE_CONNECT_READ_KEY_TYPE": "individual",
            "APP_STORE_CONNECT_READ_KEY_ID": "READKEY",
            "APP_STORE_CONNECT_READ_PRIVATE_KEY_BASE64": base64.b64encode(b"read-private").decode(),
            "APP_STORE_CONNECT_TOKEN": "legacy-token",
        }
        with (
            patch.dict("os.environ", env, clear=True),
            patch("sync_store_reviews.app_store_connect_token", return_value="read-token") as signer,
        ):
            token = app_store_connect_read_token_from_env()
        self.assertEqual(token, "read-token")
        self.assertEqual(signer.call_args.kwargs["key_type"], "individual")


if __name__ == "__main__":
    unittest.main()
