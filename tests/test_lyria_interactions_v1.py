"""Current Google Interactions wire contract; fully mocked, no paid requests."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import lyria_generate as g
from short_video_credentials import CredentialError
from test_aether_paid_boundary import fixture_environment, SLOT

AUDIO = b"fictional audio bytes" * 100


def output():
    return {"type": "audio", "mime_type": "audio/mpeg",
            "data": base64.b64encode(AUDIO).decode()}


def response(steps):
    return json.dumps({"status": "completed", "model": g.MODEL, "steps": steps}).encode()


class InteractionsV1Tests(unittest.TestCase):
    def test_current_steps_decode_and_ignore_user_input(self):
        raw, mime, meta = g.parse_audio_response(response([
            {"type": "user_input", "content": [output()]},
            {"type": "model_output", "content": [{"type": "text", "text": "Fixture description"}]},
            {"type": "model_output", "content": [output()]},
        ]))
        self.assertEqual(AUDIO, raw)
        self.assertEqual("audio/mpeg", mime)
        self.assertEqual("Fixture description", meta["description"])

    def test_historical_outputs_remain_readable(self):
        data = {"status": "completed", "model": g.MODEL, "outputs": [output()]}
        self.assertEqual(AUDIO, g.parse_audio_response(json.dumps(data).encode())[0])

    def test_missing_malformed_or_multiple_outputs_are_rejected(self):
        cases = [b"[]", response({}), response([None]),
                 response([{"type": "model_output", "content": {}}]),
                 response([{"type": "user_input", "content": [output()]}]),
                 response([{"type": "model_output", "content": [output(), output()]}])]
        for raw in cases:
            with self.subTest(raw=raw[:80]), self.assertRaises(CredentialError):
                g.parse_audio_response(raw)

    def test_real_adapter_builds_one_stateless_v1_request_under_existing_gates(self):
        with tempfile.TemporaryDirectory() as tmp, fixture_environment(Path(tmp).resolve()), \
             patch.object(g, "access_token", return_value="fixture-token"):
            def wire(request, **kwargs):
                self.assertEqual("https://aiplatform.googleapis.com/v1beta1/projects/fixture-project/locations/global/interactions", request.full_url)
                body = json.loads(request.data)
                self.assertEqual({"model", "input"}, set(body))
                self.assertEqual(g.MODEL, body["model"])
                self.assertEqual("text", body["input"][0]["type"])
                self.assertIn("Fixture Journey", body["input"][0]["text"])
                self.assertNotIn("background", body)
                stream = io.BytesIO(response([{"type": "model_output", "content": [output()]}]))
                stream.headers = {}
                return stream
            with patch.object(g, "urlopen", side_effect=wire) as transport:
                result = g.generate("Fixture Journey", "Instrumental travel", execute=True,
                                    slot=SLOT, output_root=Path(tmp).resolve() / "lyria")
            transport.assert_called_once()
            self.assertEqual("generated", result["state"])
            self.assertEqual(1, len(result["candidates"]))
            self.assertEqual(AUDIO, Path(result["candidates"][0]["file"]).read_bytes())


if __name__ == "__main__":
    unittest.main()
