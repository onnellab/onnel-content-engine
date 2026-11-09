import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import aether_sleep_worker as sleep
import aether_sleep_contract as contract
import aether_daily_local as daily


def job():
    return {'id': 'a' * 24, 'profile': 'aether_inn', 'series': contract.SERIES,
            'source_kind': contract.SOURCE_KIND, 'concept_id': contract.CONCEPTS[0][0],
            'title': contract.CONCEPTS[0][1], 'slot': '2026-11-09', 'duration_seconds': 1800,
            'status': 'blocked'}


class ContractTests(unittest.TestCase):
    def test_identity_requires_markers_and_exact_concept(self):
        contract.validate_identity(job())
        for field in ('profile', 'series', 'source_kind', 'concept_id', 'title', 'duration_seconds'):
            altered = {**job(), field: None}
            with self.assertRaises(ValueError):
                contract.validate_identity(altered)

    def test_today_exception_is_kst_and_first_concept_only(self):
        self.assertEqual(sleep.require_window(job(), datetime.fromisoformat('2026-11-09T14:59:59+00:00')), 'public')
        with self.assertRaises(ValueError):
            sleep.require_window(job(), datetime.fromisoformat('2026-11-09T15:00:00+00:00'))
        self.assertFalse(contract.today_exception_valid(datetime.fromisoformat('2026-11-09T10:00:00+09:00'), contract.CONCEPTS[1][0], '2026-11-09'))

    def test_future_slots_have_no_late_exception(self):
        j = {**job(), 'concept_id': contract.CONCEPTS[1][0], 'title': contract.CONCEPTS[1][1], 'slot': '2026-11-13'}
        self.assertEqual(sleep.require_window(j, datetime.fromisoformat('2026-11-13T08:59:59+09:00')), 'private')
        with self.assertRaises(ValueError):
            sleep.require_window(j, datetime.fromisoformat('2026-11-13T09:00:00+09:00'))

    def test_wrong_slot_naive_clock_fail(self):
        for j, now in (({**job(), 'slot': '2026-11-10'}, datetime.fromisoformat('2026-11-10T01:00:00+09:00')), (job(), datetime(2026,11,9))):
            with self.assertRaises(ValueError): sleep.require_window(j, now)

    def test_budget_counts_failed_or_uncertain_without_refund(self):
        rows = [{'concept_id': c[0], 'request_count': 1, 'all_in_reserved_usd': '0.17', 'state':'failed'} for c in contract.CONCEPTS]
        with self.assertRaisesRegex(ValueError, 'budget_exceeded'): contract.validate_budget_reservations(rows)
        with self.assertRaisesRegex(ValueError, 'retry_forbidden'): contract.validate_budget_reservations([rows[0], rows[0]])
        self.assertEqual(str(contract.validate_budget_reservations(rows[:2])), '0.34')

    def test_consumer_disclosure_is_not_adventure_or_unique_30min(self):
        brief = sleep.brief_for(job())
        self.assertIn('Not 30 minutes of unique', brief['description'])
        self.assertEqual(brief['source_kind'], 'purpose_composed_sleep')
        self.assertNotIn('JRPG', brief['title'])

    def test_review_exact_binding_permissions_and_actual_listening(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'sleep-source-review.json'
            bindings = {'source':'1'*64, 'original':'2'*64}
            receipt = {'job_id':job()['id'], 'series':contract.SERIES, 'stage':'source', 'sha256':bindings,
                       'accepted':True, 'reviewer':'reviewer', 'reviewed_at':'2026-11-09T12:00:00Z', 'authority_reference':'delegated review',
                       **{k:True for k in ['purpose_composed_sleep','commercial_rights_checked','actual_audio_listened','no_abrupt_swells','no_prominent_beat','no_voice','sleep_suitable']}}
            p.write_text(json.dumps(receipt)); p.chmod(0o600)
            sleep.require_review(folder, job(), 'source', bindings)
            with self.assertRaises(ValueError): sleep.require_review(folder, job(), 'source', {'source':'3'*64})
            receipt['actual_audio_listened'] = False
            p.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError): sleep.require_review(folder, job(), 'source', bindings)
            p.chmod(0o644)
            with self.assertRaises(ValueError): sleep.require_review(folder, job(), 'source', bindings)

    def test_absent_review_does_not_get_fabricated(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): sleep.require_review(folder, job(), 'loop', {})
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_mp3_decode_pins_original_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder)/'candidate.mp3', Path(folder)/'pcm.wav'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i','sine=frequency=220:duration=30','-c:a','libmp3lame',str(source)],check=True,timeout=30)
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            result = sleep.decode_source(source, sha, out)
            self.assertEqual(result['original_sha256'], sha)
            self.assertAlmostEqual(result['duration_seconds'], 30, places=1)
            with self.assertRaises(ValueError): sleep.decode_source(source, sha, out)
            with self.assertRaises(ValueError): sleep.decode_source(source, '0'*64, Path(folder)/'other.wav')
            self.assertFalse((Path(folder)/'other.wav').exists())

    def test_wav_decode_uses_distinct_snapshot_output(self):
        import wave
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder)/'candidate.wav', Path(folder)/'pcm.wav'
            with wave.open(str(source), 'wb') as stream:
                stream.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\0\0' * 24000 * 30)
            result = sleep.decode_source(source, hashlib.sha256(source.read_bytes()).hexdigest(), out)
            self.assertEqual(result['duration_seconds'], 30)
            self.assertNotEqual(result['original_sha256'], result['sha256'])

    def test_missing_billing_does_not_create_queue_job_or_contact_youtube(self):
        import aether_single as single
        from short_video_credentials import CredentialError
        with tempfile.TemporaryDirectory() as folder:
            api = Mock()
            with patch.object(sleep, 'require_window', return_value='public'), \
                 patch('lyria_config.load_settings', return_value={'enabled': True, 'project_id': 'sleep-project'}), \
                 patch('aether_sleep_guard.load_all_in_proof', side_effect=CredentialError('sleep_account_all_in_cost_unverified')):
                with self.assertRaises(CredentialError):
                    sleep.worker(root=Path(folder).resolve(), concept_id=contract.CONCEPTS[0][0], slot='2026-11-09', execute=True, publish=True, api_factory=api)
            api.assert_not_called()
            self.assertEqual(single.SingleQueue(Path(folder).resolve())._read()['jobs'], {})

    def test_runner_only_fixed_dates_and_same_worker(self):
        report={'blockers':[]}
        with patch.object(daily, 'run_step', return_value=(2,'{"status":"blocked","error":"sleep_account_all_in_cost_unverified"}','')) as run:
            daily.run_sleep_slot(report, datetime.fromisoformat('2026-11-09T16:00:00+09:00'))
            args = run.call_args.args[2]
            self.assertIn('scripts/aether_single.py',args)
            self.assertIn('sleep-worker',args)
            self.assertIn('sleep_moonlit_guestroom',args)
        with patch.object(daily,'run_step') as run:
            daily.run_sleep_slot({'blockers':[]},datetime.fromisoformat('2026-11-10T07:00:00+09:00'))
            run.assert_not_called()

    def test_runner_does_not_repeat_reconciled_sleep(self):
        with patch.object(daily, 'run_step') as run:
            daily.run_sleep_slot({'blockers':[]},datetime.fromisoformat('2026-11-09T12:00:00+09:00'),{'series':contract.SERIES,'status':'blocked'})
            run.assert_not_called()

    def test_expired_unspent_job_retires_but_uncertain_does_not(self):
        with tempfile.TemporaryDirectory() as folder:
            q=types.SimpleNamespace(root=Path(folder),state_path=Path(folder)/'queue.json')
            fake=types.SimpleNamespace(directory=lambda p:(p.mkdir(parents=True,exist_ok=True) or p),
                atomic_json=Mock(), paid_guard=types.SimpleNamespace(require_no_unsettled_intents=Mock()), VideoError=RuntimeError)
            gen=types.SimpleNamespace(generate_sleep=Mock())
            j=job(); state={'jobs':{j['id']:j}}
            with patch.dict(sys.modules, {'aether_single':fake,'lyria_generate':gen}), patch.object(sleep,'require_window',side_effect=ValueError('sleep_publication_window_closed')):
                result=sleep.run_locked(q,state,j,publish=True,reconcile_only=True)
                self.assertEqual(result['status'],'idle'); self.assertEqual(j['status'],'rejected')
                gen.generate_sleep.assert_not_called()
                j['status']='blocked'
                fake.paid_guard.require_no_unsettled_intents.side_effect=RuntimeError('uncertain')
                with self.assertRaises(RuntimeError): sleep.run_locked(q,state,j,publish=True)
                self.assertEqual(j['status'],'blocked')

if __name__ == '__main__': unittest.main()
