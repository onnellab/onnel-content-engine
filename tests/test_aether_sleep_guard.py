"""Offline safety checks. Synthetic fixtures are never production evidence."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import aether_sleep_guard as guard
import lyria_generate
from short_video_credentials import CredentialError

NOW = datetime(2026, 11, 9, 4, tzinfo=timezone.utc)
PROJECT = 'example-project'


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # macOS may return /var/folders/... while /var is a symlink to
        # /private/var. Canonicalize the fixture, not the production guard.
        self.root = Path(self.tmp.name).resolve()
        self.root.chmod(0o700)
        self.patches = [patch.object(guard, 'ROOT', self.root / 'pilot'),
                        patch.object(guard, 'PROOF_PATH', self.root / 'pilot' / 'receipt.json'),
                        patch.object(guard.paid, 'AETHER_ROOT', self.root),
                        patch.object(guard.paid, 'utc_now', return_value=NOW)]
        for p in self.patches: p.start()
        guard.ROOT.mkdir(mode=0o700)
        self.scope = {'concept_id': 'sleep_moonlit_guestroom', 'job_id': 'a' * 24, 'slot': '2026-11-09'}
        self.row = guard.concept(self.scope['concept_id'])
        self.intent_path = guard.output_for(self.scope['job_id']) / 'run' / 'manifest.json'
        self.intent = {'sleep_scope': self.scope, 'title': self.row['title'], 'model': guard.MODEL,
                       'project_id': PROJECT, 'candidate_count': 1,
                       'prompt_sha256': hashlib.sha256(self.row['prompt'].encode()).hexdigest()}

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def write(self, path, value):
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        path.chmod(0o600)

    def receipt(self, total='0.10'):
        source = b'SYNTHETIC TEST FIXTURE ONLY: account upper bound review'
        digest = hashlib.sha256(source).hexdigest()
        self.write(guard.ROOT / ('account-receipt-' + digest + '.bin'), source)
        proof = {'schema_version': 1, 'kind': 'google_cloud_account_all_in_upper_bound',
                 'project_id': PROJECT, 'model': guard.MODEL, 'currency': 'USD',
                 'account_reference': 'synthetic-account', 'receipt_reference': 'synthetic-test',
                 'coverage': ['provider_base', 'tax', 'currency_conversion', 'mandatory_fees'],
                 'checked_at': '2026-11-09T00:00:00Z', 'expires_at': '2026-11-10T00:00:00Z',
                 'provider_base_usd': '0.08', 'tax_upper_bound_usd': '0.02',
                 'fx_upper_bound_usd': '0', 'mandatory_fees_upper_bound_usd': '0',
                 'per_request_all_in_upper_bound_usd': total, 'source_sha256': digest}
        fields = ('project_id', 'account_reference', 'model', 'currency', 'provider_base_usd',
                  'tax_upper_bound_usd', 'fx_upper_bound_usd', 'mandatory_fees_upper_bound_usd',
                  'per_request_all_in_upper_bound_usd')
        proof['review_attestation'] = {'kind': 'reviewed_account_upper_bound', 'reviewer_kind': 'dot_delegated',
            'source_sha256': digest, 'reviewer': 'synthetic-test', 'reviewed_at': '2026-11-09T01:00:00Z',
            'reviewed_values': {k: proof[k] for k in fields},
            'source_references': {k: 'synthetic line 1' for k in fields}}
        self.write(guard.PROOF_PATH, proof)
        return proof

    def test_missing_receipt(self):
        with self.assertRaisesRegex(CredentialError, 'unverified'): guard.load_all_in_proof(PROJECT)

    def test_receipt_binding_expiry_bad_amounts(self):
        proof = self.receipt()
        self.assertEqual(guard.load_all_in_proof(PROJECT)['all_in_reserved_usd'], '0.10')
        for key, value in [('project_id', 'other-project'), ('model', 'other'),
                           ('expires_at', '2026-11-09T03:00:00Z'),
                           ('provider_base_usd', True), ('provider_base_usd', 'NaN'),
                           ('per_request_all_in_upper_bound_usd', '0.08'),
                           ('review_attestation', {'verified': True})]:
            with self.subTest(key=key, value=value):
                bad = copy.deepcopy(proof); bad[key] = value; self.write(guard.PROOF_PATH, bad)
                with self.assertRaises(CredentialError): guard.load_all_in_proof(PROJECT)
        self.write(guard.PROOF_PATH, proof)
        with self.assertRaises(CredentialError): guard.load_all_in_proof(PROJECT, expected_sha256='0'*64)

    def test_reservation_no_retry_and_binding(self):
        self.receipt(); proof = guard.load_all_in_proof(PROJECT)
        guard.reserve(self.scope, PROJECT, self.row['prompt'], self.intent_path, 'f'*64, proof)
        guard.require_dispatch(self.scope, PROJECT, self.row['prompt'], self.intent_path, 'f'*64, self.intent)
        with self.assertRaisesRegex(CredentialError, 'retry_forbidden'):
            guard.reserve(self.scope, PROJECT, self.row['prompt'], self.intent_path, 'f'*64, proof)
        for key, value in [('title', 'Changed'), ('project_id', 'other-project'), ('candidate_count', True),
                           ('prompt_sha256', '0'*64)]:
            bad = {**self.intent, key: value}
            with self.assertRaises(CredentialError):
                guard.require_dispatch(self.scope, PROJECT, self.row['prompt'], self.intent_path, 'f'*64, bad)
        with self.assertRaises(CredentialError):
            guard.require_dispatch(self.scope, PROJECT, self.row['prompt'], self.intent_path, 'e'*64, self.intent)

    def test_sum_over_cap_and_non_finite(self):
        rows = guard.build_plan()['drafts']
        for row in rows:
            self.write(guard.ROOT / ('reservation-' + row['id'] + '.json'),
                       {'concept_id': row['id'], 'request_count': 1, 'all_in_reserved_usd': '0.17'})
        with self.assertRaisesRegex(CredentialError, 'budget_exceeded'): guard.ledger_rows()
        for bad in [True, 'NaN', '-0.1', 0.08]:
            for path in guard.ROOT.glob('reservation-*'): path.unlink()
            self.write(guard.ROOT / ('reservation-' + rows[0]['id'] + '.json'),
                       {'concept_id': rows[0]['id'], 'request_count': 1, 'all_in_reserved_usd': bad})
            with self.assertRaises(CredentialError): guard.ledger_rows()

    def test_prompt_date_and_private_permissions(self):
        with self.assertRaises(CredentialError): guard.identity(self.scope, PROJECT, 'adventure')
        with self.assertRaises(CredentialError):
            guard.identity(self.scope, PROJECT, self.row['prompt'], now=datetime(2026,11,10,tzinfo=timezone.utc))
        self.receipt(); guard.PROOF_PATH.chmod(0o644)
        with self.assertRaises(CredentialError): guard.load_all_in_proof(PROJECT)

    def test_concurrent_same_concept_reserves_once(self):
        from concurrent.futures import ThreadPoolExecutor
        self.receipt(); proof = guard.load_all_in_proof(PROJECT)
        def attempt(_):
            try:
                guard.reserve(self.scope, PROJECT, self.row['prompt'], self.intent_path, 'f'*64, proof)
                return 'reserved'
            except CredentialError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, ['reserved', 'sleep_paid_retry_forbidden'])
        self.assertEqual(len(guard.ledger_rows()), 1)


    def test_failed_transport_is_reserved_and_never_retried(self):
        self.receipt()
        settings = {'enabled': True, 'project_id': PROJECT, 'candidate_count': 1, 'max_usd_per_run': 0.08}
        base_proof = {'proof_sha256': 'b'*64, 'checked_at': '2026-11-09T00:00:00Z',
                      'expires_at': '2026-11-10T00:00:00Z'}
        with patch.object(lyria_generate, 'load_settings', return_value=settings), \
             patch.object(lyria_generate, 'access_token', return_value='offline-fixture'), \
             patch.object(guard.paid, 'load_paid_proof', return_value=base_proof), \
             patch.object(guard.paid, 'require_no_unsettled_intents'), \
             patch.object(lyria_generate, 'urlopen', side_effect=TimeoutError()) as transport:
            with self.assertRaisesRegex(CredentialError, 'network_error'):
                lyria_generate.generate_sleep(self.scope['concept_id'], execute=True,
                    output_root=guard.output_for(self.scope['job_id']), slot=self.scope['slot'], job_id=self.scope['job_id'])
            self.assertEqual(transport.call_count, 1)
            with self.assertRaisesRegex(CredentialError, 'retry_forbidden'):
                lyria_generate.generate_sleep(self.scope['concept_id'], execute=True,
                    output_root=guard.output_for(self.scope['job_id']), slot=self.scope['slot'], job_id=self.scope['job_id'])
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(guard.ledger_rows()), 1)


    def test_generated_recovery_checks_source_and_ignores_expired_charge_proof(self):
        import base64
        import io
        self.receipt()
        settings = {'enabled': True, 'project_id': PROJECT, 'candidate_count': 1, 'max_usd_per_run': 0.08}
        base_proof = {'proof_sha256': 'b'*64, 'checked_at': '2026-11-09T00:00:00Z',
                      'expires_at': '2026-11-10T00:00:00Z'}
        response = io.BytesIO(json.dumps({'status': 'completed', 'model': guard.MODEL,
            'outputs': [{'type': 'audio', 'mime_type': 'audio/wav',
                         'data': base64.b64encode(b'x'*1024).decode()}]}).encode())
        response.headers = {}
        with patch.object(lyria_generate, 'load_settings', return_value=settings), \
             patch.object(lyria_generate, 'access_token', return_value='offline-fixture'), \
             patch.object(guard.paid, 'load_paid_proof', return_value=base_proof), \
             patch.object(guard.paid, 'require_no_unsettled_intents'), \
             patch.object(lyria_generate, 'urlopen', return_value=response):
            result = lyria_generate.generate_sleep(self.scope['concept_id'], execute=True,
                output_root=guard.output_for(self.scope['job_id']), slot=self.scope['slot'], job_id=self.scope['job_id'])
        with patch.object(guard.paid, 'utc_now', return_value=datetime(2026,11,12,tzinfo=timezone.utc)):
            recovered = guard.validate_generated_sleep(result['manifest'], **self.scope)
            self.assertEqual(recovered['state'], 'generated')
            Path(result['candidates'][0]['file']).write_bytes(b'changed')
            with self.assertRaises(CredentialError):
                guard.validate_generated_sleep(result['manifest'], **self.scope)


    def test_final_receipt_recheck_blocks_transport(self):
        self.receipt()
        settings = {'enabled': True, 'project_id': PROJECT, 'candidate_count': 1, 'max_usd_per_run': 0.08}
        base_proof = {'proof_sha256': 'b'*64, 'checked_at': '2026-11-09T00:00:00Z',
                      'expires_at': '2026-11-10T00:00:00Z'}
        original = guard.load_all_in_proof
        checks = []
        def expiry(*args, **kwargs):
            checks.append(1)
            if len(checks) == 4:
                raise CredentialError('sleep_all_in_proof_expired')
            return original(*args, **kwargs)
        with patch.object(lyria_generate, 'load_settings', return_value=settings), \
             patch.object(lyria_generate, 'access_token', return_value='offline-fixture'), \
             patch.object(guard.paid, 'load_paid_proof', return_value=base_proof), \
             patch.object(guard.paid, 'require_no_unsettled_intents'), \
             patch.object(guard, 'load_all_in_proof', side_effect=expiry), \
             patch.object(lyria_generate, 'urlopen', side_effect=AssertionError('network forbidden')) as transport:
            with self.assertRaisesRegex(CredentialError, 'expired'):
                lyria_generate.generate_sleep(self.scope['concept_id'], execute=True,
                    output_root=guard.output_for(self.scope['job_id']), slot=self.scope['slot'], job_id=self.scope['job_id'])
            transport.assert_not_called()
            self.assertEqual(len(guard.ledger_rows()), 1)

    def test_ordinary_request_keeps_fantasy_schedule(self):
        settings = {'enabled': True, 'project_id': PROJECT, 'candidate_count': 1, 'max_usd_per_run': 0.08}
        with patch.object(lyria_generate, 'load_settings', return_value=settings), \
             patch.object(guard.paid, 'require_generation_window', side_effect=CredentialError('fantasy-window')) as window, \
             patch.object(lyria_generate, 'urlopen') as transport:
            with self.assertRaisesRegex(CredentialError, 'fantasy-window'):
                lyria_generate.request_song(PROJECT, 'ordinary prompt', slot='2026-11-09')
            window.assert_called_once_with('2026-11-09', now=None)
            transport.assert_not_called()


    def test_dry_run_never_network(self):
        with patch.object(lyria_generate, 'urlopen', side_effect=AssertionError('network forbidden')):
            result = lyria_generate.generate_sleep(self.scope['concept_id'], output_root=self.root,
                                                  slot=self.scope['slot'], job_id=self.scope['job_id'])
        self.assertEqual(result['prompt'], self.row['prompt'])
        self.assertFalse(result['paid_authorized'])


if __name__ == '__main__': unittest.main()
