"""Offline tests for the loopback-only Suno Platform credential helper."""
from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from short_video_credentials import CredentialError
from suno_api_connect import SetupHandler, SetupServer
from suno_api_credentials import credential_status, validate_api_key


class MemoryStore:
    def __init__(self):
        self.value = None
        self.loads = 0

    def present(self):
        return self.value is not None

    def load(self):
        self.loads += 1
        if self.value is None:
            raise CredentialError("missing_suno_api_key")
        return self.value

    def save(self, value):
        self.value = validate_api_key(value)

    def delete(self):
        self.value = None


class SunoCredentialTests(unittest.TestCase):
    def test_key_validation_is_bounded_and_printable(self):
        self.assertEqual("key-123_ABC", validate_api_key("  key-123_ABC  "))
        for value in ["", "   ", "bad\nkey", "x" * 8193]:
            with self.subTest(value=value[:16]), self.assertRaises(CredentialError):
                validate_api_key(value)

    def test_status_is_attribute_only(self):
        store = MemoryStore()
        self.assertFalse(credential_status(store=store)["configured"])
        store.value = "DO-NOT-PRINT-SUNO"
        result = credential_status(store=store)
        self.assertTrue(result["configured"])
        self.assertEqual(0, store.loads)
        self.assertNotIn("DO-NOT-PRINT", json.dumps(result))


class SunoLocalConsoleTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.server = SimpleNamespace(
            origin="http://127.0.0.1:49002",
            csrf="csrf-token",
            nonce="nonce",
            store=self.store,
            instance="instance",
        )

    def handler(self, path="/", *, body=None, extra=None):
        handler = object.__new__(SetupHandler)
        handler.server = self.server
        handler.client_address = ("127.0.0.1", 50000)
        handler.path = path
        handler.headers = Message()
        handler.headers["Host"] = "127.0.0.1:49002"
        handler.headers["Origin"] = self.server.origin
        handler.headers["X-ONNELLAB-CSRF"] = self.server.csrf
        if extra:
            for key, value in extra.items():
                if key in handler.headers:
                    del handler.headers[key]
                if value is not None:
                    handler.headers[key] = value
        data = json.dumps(body or {}).encode()
        handler.rfile = io.BytesIO(data)
        handler.headers["Content-Type"] = "application/json"
        handler.headers["Content-Length"] = str(len(data))
        handler.reply = Mock()
        return handler

    def test_root_never_contains_key_or_browser_storage(self):
        self.store.value = "DO-NOT-PRINT-SUNO"
        handler = self.handler()
        handler.do_GET()
        html = handler.reply.call_args.kwargs["html"]
        self.assertIn("Suno Platform API", html)
        self.assertIn("csrf-token", html)
        for forbidden in ["DO-NOT-PRINT-SUNO", "localStorage", "sessionStorage", "indexedDB", ".innerHTML"]:
            self.assertNotIn(forbidden, html)

    def test_status_does_not_load_secret(self):
        self.store.value = "DO-NOT-PRINT-SUNO"
        handler = self.handler("/api/status")
        handler.do_GET()
        result = handler.reply.call_args.args[1]
        self.assertTrue(result["configured"])
        self.assertEqual(0, self.store.loads)
        self.assertNotIn("DO-NOT-PRINT", json.dumps(result))

    def test_save_does_not_echo_secret(self):
        handler = self.handler("/api/save", body={"api_key": "DO-NOT-PRINT-SUNO"})
        handler.do_POST()
        self.assertEqual(200, handler.reply.call_args.args[0])
        self.assertEqual("DO-NOT-PRINT-SUNO", self.store.value)
        self.assertNotIn("DO-NOT-PRINT-SUNO", json.dumps(handler.reply.call_args.args[1]))

    def test_delete_requires_confirmation(self):
        self.store.value = "DO-NOT-PRINT-SUNO"
        handler = self.handler("/api/delete", body={})
        handler.do_POST()
        self.assertEqual(400, handler.reply.call_args.args[0])
        self.assertTrue(self.store.present())
        handler = self.handler("/api/delete", body={"confirm": True})
        handler.do_POST()
        self.assertEqual(200, handler.reply.call_args.args[0])
        self.assertFalse(self.store.present())

    def test_cross_origin_and_lan_clients_are_rejected(self):
        handler = self.handler("/api/save", body={"api_key": "key"}, extra={"Origin": "https://evil.test"})
        handler.do_POST()
        self.assertEqual(403, handler.reply.call_args.args[0])
        self.assertFalse(self.store.present())
        handler = self.handler("/api/status")
        handler.client_address = ("192.168.1.2", 50000)
        handler.do_GET()
        self.assertEqual(403, handler.reply.call_args.args[0])

    def test_non_loopback_server_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "loopback_only"):
            SetupServer(self.store, address=("0.0.0.0", 0))


if __name__ == "__main__":
    unittest.main()
