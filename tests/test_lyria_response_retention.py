"""Keep stateless provider bytes even when audio decoding fails; no live calls."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import lyria_generate as lyria
from short_video_credentials import CredentialError
from test_aether_paid_boundary import fixture_environment, response_fixture, SLOT


class ResponseRetentionTests(unittest.TestCase):
    def test_missing_audio_preserves_exact_response_before_error_and_blocks_repayment(self):
        payload = json.dumps({'status': 'completed', 'model': lyria.MODEL,
                              'steps': [{'type': 'model_output', 'content': []}]}).encode()
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria, 'access_token', return_value='private-fixture-token'):
            output = Path(temporary) / 'lyria'
            response = io.BytesIO(payload)
            response.headers = {}
            with patch.object(lyria, 'urlopen', return_value=response) as transport:
                with self.assertRaisesRegex(CredentialError, 'lyria_audio_missing'):
                    lyria.generate('Fixture Song', 'Fixture instrumental', execute=True,
                                   slot=SLOT, output_root=output)
                path = next(output.glob('*/manifest.json'))
                before = path.read_bytes()
                record = json.loads(before)
                raw_path = path.parent / record['provider_response']['file']
                self.assertEqual(payload, raw_path.read_bytes())
                self.assertEqual(hashlib.sha256(payload).hexdigest(), record['provider_response']['sha256'])
                self.assertEqual(0o600, raw_path.stat().st_mode & 0o777)
                self.assertEqual('request_started', record['state'])
                self.assertNotIn('private-fixture-token', before.decode())
                with self.assertRaisesRegex(CredentialError, 'generation_uncertain'):
                    lyria.generate('Fixture Song', 'Fixture instrumental', execute=True,
                                   slot=SLOT, output_root=output)
                self.assertEqual(before, path.read_bytes())
                transport.assert_called_once()

    def test_success_retains_response_and_records_generated_candidate(self):
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria, 'access_token', return_value='fixture'), \
             patch.object(lyria, 'urlopen', side_effect=lambda *a, **k: response_fixture()) as transport:
            result = lyria.generate('Fixture Song', 'Fixture instrumental', execute=True,
                                   slot=SLOT, output_root=Path(temporary) / 'lyria')
            self.assertEqual('generated', result['state'])
            self.assertEqual(1, len(result['candidates']))
            raw = (Path(result['manifest']).parent / result['provider_response']['file']).read_bytes()
            self.assertEqual(result['provider_response']['sha256'], hashlib.sha256(raw).hexdigest())
            transport.assert_called_once()


class ErrorResponseRetentionTests(unittest.TestCase):
    def test_http_error_preserves_body_and_never_retries(self):
        from urllib.error import HTTPError
        payload = b'{"error":{"code":400,"message":"Fictional invalid input"}}'
        with tempfile.TemporaryDirectory() as temporary, fixture_environment(Path(temporary)), \
             patch.object(lyria, 'access_token', return_value='private-fixture-token'):
            output = Path(temporary) / 'lyria'
            error = HTTPError('https://fixture.invalid', 400, 'fixture', {}, io.BytesIO(payload))
            with patch.object(lyria, 'urlopen', side_effect=error) as transport:
                with self.assertRaisesRegex(CredentialError, 'lyria_api_error'):
                    lyria.generate('Fixture Song', 'Fixture instrumental', execute=True,
                                   slot=SLOT, output_root=output)
            path = next(output.glob('*/manifest.json'))
            record = json.loads(path.read_text())
            evidence = record['provider_error']
            self.assertEqual(400, evidence['http_status'])
            self.assertEqual(payload, (path.parent / evidence['file']).read_bytes())
            self.assertEqual('request_started', record['state'])
            self.assertNotIn('private-fixture-token', path.read_text())
            transport.assert_called_once()


if __name__ == '__main__':
    unittest.main()
