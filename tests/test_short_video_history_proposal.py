"""Offline evidence proposals cannot create completed upload receipts."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_history_proposal import CHANNEL, ROOT, build_proposal, public_observation


class HistoryProposalTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((ROOT / 'data/youtube_ops_snapshot.json').read_text(encoding='utf-8'))
        self.mapping = json.loads((ROOT / 'data/video_history_app_mapping.json').read_text(encoding='utf-8'))

    def test_eight_candidates_remain_unverified_receipts_and_unknown_dates(self):
        result = build_proposal(self.snapshot, self.mapping)
        self.assertEqual(8, len(result['videos']))
        self.assertFalse(result['import_ready'])
        self.assertEqual([], result['claim_slots'])
        self.assertEqual(5, len({v['proposed_app_mapping']['app_id'] for v in result['videos']}))
        for row in result['videos']:
            self.assertIsNone(row['published_at'])
            self.assertFalse(row['upload_receipt_available'])
            self.assertEqual('unknown', row['provider_privacy_status'])

    def test_observed_oembed_never_becomes_a_provider_receipt_or_date(self):
        video = self.snapshot['profiles']['onnellab']['videos'][0]
        result = build_proposal(self.snapshot, self.mapping, observations={video['video']: {
            'status': 'observed', 'title': video['title'], 'checked_at': '2026-10-04T00:00:00+00:00'}})
        row = result['videos'][0]
        self.assertTrue(row['snapshot_title_matches_public'])
        self.assertFalse(row['provider_channel_identity_verified'])
        self.assertIsNone(row['published_at'])
        self.assertFalse(result['import_ready'])

    def test_music_channel_cannot_be_imported(self):
        self.snapshot['profiles']['onnellab']['channel']['id'] = 'UC' + 'a' * 22
        with self.assertRaisesRegex(ValueError, 'channel_mismatch'):
            build_proposal(self.snapshot, self.mapping)

    def test_duplicate_ids_and_missing_mappings_are_not_silently_guessed(self):
        self.mapping['mappings'].clear()
        result = build_proposal(self.snapshot, self.mapping)
        self.assertTrue(all(v['proposed_app_mapping'] is None for v in result['videos']))
        self.snapshot['profiles']['onnellab']['videos'].append(copy.deepcopy(self.snapshot['profiles']['onnellab']['videos'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            build_proposal(self.snapshot, self.mapping)

    def test_public_lookup_checks_author_and_records_only_allowlisted_fields(self):
        response = io.BytesIO(json.dumps({'title': 'Example', 'author_name': 'ONNELLAB',
            'author_url': 'https://www.youtube.com/@ONNELLAB', 'html': 'untrusted embed'}).encode())
        response.status = 200
        result = public_observation('ScIaoTTLmc8', fetch=Mock(return_value=response))
        self.assertEqual('observed', result['status'])
        self.assertNotIn('html', result)
        self.assertNotIn('published_at', result)

    def test_unavailable_or_foreign_author_is_unknown_not_deleted(self):
        for fetch in (Mock(side_effect=OSError()), Mock(return_value=self.foreign_response())):
            result = public_observation('ScIaoTTLmc8', fetch=fetch)
            self.assertEqual('unverified', result['status'])
            self.assertNotIn('deleted', result)

    @staticmethod
    def foreign_response():
        response = io.BytesIO(json.dumps({'title': 'Example', 'author_name': 'ONNELLAB',
            'author_url': 'https://evil.example/@ONNELLAB'}).encode())
        response.status = 200
        return response


if __name__ == '__main__':
    unittest.main()
