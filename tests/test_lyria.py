"""Offline tests for Lyria configuration, setup console, and Aether prompt/response gates."""
from __future__ import annotations

import base64
import io
import json
from email.message import Message
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from short_video_credentials import CredentialError
import lyria_config
import lyria_connect
import lyria_generate


class LyriaConfigTests(unittest.TestCase):
    def settings(self, **changes):
        value = {
            "project_id": "aether-music-123",
            "candidate_count": 1,
            "max_usd_per_run": 0.08,
            "enabled": True,
        }
        value.update(changes)
        return value

    def test_validation_and_spend_gate(self):
        result = lyria_config.validate_settings(self.settings())
        self.assertEqual("lyria-3-pro-preview", result["model"])
        self.assertEqual("global", result["location"])
        with self.assertRaisesRegex(CredentialError, "spend_cap_below"):
            lyria_config.validate_settings(self.settings(candidate_count=2, max_usd_per_run=0.08))
        for project in ["UPPERCASE", "x", "bad_project"]:
            with self.subTest(project=project), self.assertRaises(CredentialError):
                lyria_config.validate_project_id(project)

    def test_private_config_round_trip(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            saved = lyria_config.save_settings(self.settings(enabled=False, max_usd_per_run=0.0), path)
            loaded = lyria_config.load_settings(path)
            self.assertEqual(saved, loaded)
            self.assertEqual(0, path.stat().st_mode & 0o077)

    def test_status_never_returns_access_token(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            lyria_config.save_settings(self.settings(), path)
            with patch.object(lyria_config, "_gcloud", return_value="/usr/bin/gcloud"),                  patch.object(lyria_config, "access_token", return_value="DO-NOT-PRINT"):
                result = lyria_config.connection_status(path=path)
            self.assertEqual("ready", result["state"])
            self.assertNotIn("DO-NOT-PRINT", json.dumps(result))


class LyriaGenerationTests(unittest.TestCase):
    def test_aether_prompt_has_major_resolution_contract(self):
        prompt = lyria_generate.build_aether_prompt(
            "Beyond the Silent Stone Gate",
            "Warm guitar, gentle piano, nostalgic JRPG frontier theme",
        )
        for required in [
            "warm major key",
            "dominant-to-tonic cadence",
            "V-I",
            "final melody note must resolve clearly to the tonic",
            "Do not flatten the final melody note",
            "No vocals",
        ]:
            self.assertIn(required, prompt)

    def test_cost_and_configured_candidate_cap(self):
        self.assertEqual(0.08, lyria_generate.estimate_cost(1))
        self.assertEqual(0.4, lyria_generate.estimate_cost(5))
        settings = {
            "project_id": "aether-music-123",
            "candidate_count": 1,
            "max_usd_per_run": 0.08,
            "enabled": True,
        }
        with patch.object(lyria_generate, "load_settings", return_value=settings):
            result = lyria_generate.generate("Test Road", "Warm JRPG field theme", execute=False)
        self.assertEqual("planned", result["state"])
        self.assertFalse(result["execute"])

    def test_audio_response_decodes_only_completed_expected_model(self):
        raw = b"A" * 2048
        payload = json.dumps({
            "status": "completed",
            "model": "lyria-3-pro-preview",
            "outputs": [
                {"type": "text", "text": "instrumental"},
                {"type": "audio", "mime_type": "audio/mpeg", "data": base64.b64encode(raw).decode()},
            ],
        }).encode()
        audio, mime, meta = lyria_generate.parse_audio_response(payload)
        self.assertEqual(raw, audio)
        self.assertEqual("audio/mpeg", mime)
        self.assertEqual("instrumental", meta["description"])
        bad = json.dumps({"status": "completed", "model": "other", "outputs": []}).encode()
        with self.assertRaises(CredentialError):
            lyria_generate.parse_audio_response(bad)


class LyriaConsoleTests(unittest.TestCase):
    def setUp(self):
        self.server = SimpleNamespace(
            origin="http://127.0.0.1:49003",
            csrf="csrf-token",
            nonce="nonce",
            instance="instance",
        )

    def handler(self, path="/", *, body=None, extra=None):
        handler = object.__new__(lyria_connect.SetupHandler)
        handler.server = self.server
        handler.client_address = ("127.0.0.1", 50000)
        handler.path = path
        handler.headers = Message()
        handler.headers["Host"] = "127.0.0.1:49003"
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

    def test_root_template_has_no_browser_secret_storage(self):
        page = (Path(__file__).resolve().parents[1] / "templates" / "lyria_connect.html").read_text()
        for forbidden in ["localStorage", "sessionStorage", "indexedDB", "access_token", "refresh_token", "client_secret"]:
            self.assertNotIn(forbidden, page)
        self.assertIn("gcloud auth application-default login", page)

    def test_cross_origin_mutation_rejected(self):
        handler = self.handler("/api/save", body={}, extra={"Origin": "https://evil.test"})
        handler.do_POST()
        self.assertEqual(403, handler.reply.call_args.args[0])

    def test_save_accepts_only_local_settings_path(self):
        status = {
            "state": "configured", "configured": True, "gcloud_ready": True,
            "auth_ready": False, "project_id": "aether-music-123",
        }
        handler = self.handler("/api/save", body={
            "project_id": "aether-music-123",
            "candidate_count": 1,
            "max_usd_per_run": 0.08,
            "enabled": False,
        })
        with patch.object(lyria_connect, "save_settings") as save,              patch.object(lyria_connect, "connection_status", return_value=status):
            handler.do_POST()
        self.assertEqual(200, handler.reply.call_args.args[0])
        save.assert_called_once()

    def test_non_loopback_server_rejected(self):
        with self.assertRaisesRegex(ValueError, "loopback_only"):
            lyria_connect.SetupServer(address=("0.0.0.0", 0))


if __name__ == "__main__":
    unittest.main()
