from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from publication_history import body_evidence_matches, preserve_publication
from reconcile_remote_browser_publications import sync_verified_social_manifest, reconcile, RemotePublicationError


class PublicationBodyEvidenceTest(unittest.TestCase):
    def fixture(self):
        source = 'A different generated draft.\n'
        body = 'Observed public copy. Read more: https://t.co/Abc123'
        post = dict(topic_id='T1', platform='x', language='en', template_id='x',
                    draft_path='draft.txt', canonical_url='https://onnellab.com/blog/en/example/',
                    status='failed', error='old failure', posted_url='')
        receipt = dict(topic_id='T1', platform='x', language='en', template_id='x',
                       manual_key='T1::x::en::x', status='processed',
                       draft_sha256=hashlib.sha256(source.encode()).hexdigest(),
                       body_evidence_kind='observed_public_body', observed_body=body,
                       observed_body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                       observed_body_hash_normalization='UTF-8, collapsed whitespace; URLs retained.',
                       observed_body_normalization='utf8_whitespace_collapsed_urls_preserved_v1',
                       account='@onnellab', post_id='123', posted_url='https://x.com/onnellab/status/123',
                       source_draft_path=post['draft_path'], canonical_url=post['canonical_url'],
                       observed_short_url='https://t.co/Abc123',
                       observed_at='2026-10-15T00:44:18Z',
                       canonical_destination_verified_at='2026-10-15T00:44:47Z',
                       observation_source='Exact author, body and short-link target read in cloud browser.')
        done = dict(receipt, verified_at='2026-10-15T00:45:29Z',
                    verification_method='browser_permalink', published_at='2026-10-14T00:54:49.000Z',
                    published_at_precision='second')
        return source, post, receipt, done

    def test_observed_copy_is_hash_bound_without_claiming_submitted_source(self):
        source, post, receipt, done = self.fixture()
        self.assertTrue(body_evidence_matches(done, receipt, source, post))
        self.assertNotEqual(hashlib.sha256(source.removesuffix('\n').encode()).hexdigest(), receipt['observed_body_sha256'])
        self.assertNotIn('posted_body_sha256', receipt)

    def test_observed_evidence_fails_closed_for_tampering_and_missing_bindings(self):
        source, post, receipt, done = self.fixture()
        changes = (
            {'observed_body': 'Altered public body https://t.co/Abc123'},
            {'observed_body_sha256': '0' * 64}, {'draft_sha256': '0' * 64},
            {'body_evidence_kind': 'unsupported'}, {'body_evidence_kind': 'submitted_source'},
            {'observed_body_normalization': 'unsupported'}, {'observed_body_hash_normalization': ''},
            {'posted_body_sha256': receipt['observed_body_sha256']}, {'submitted_body': 'invented'},
            {'account': '@someone_else'}, {'post_id': '456'},
            {'posted_url': 'https://x.com/onnellab'}, {'source_draft_path': 'other.txt'},
            {'canonical_url': 'https://onnellab.com/blog/en/other/'},
            {'observed_short_url': 'https://t.co/Unknown'},
            {'canonical_destination_verified_at': ''},
            {'canonical_destination_verified_at': '2026-10-14T00:44:47Z'},
            {'canonical_destination_verified_at': '2026-10-16T00:44:47Z'},
            {'canonical_destination_verified_at': '2026-10-15T00:44:47'},
        )
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(body_evidence_matches(dict(done, **change), dict(receipt, **change), source, post))
        for field in ('observed_body', 'observed_body_sha256', 'body_evidence_kind', 'account'):
            changed = dict(done); changed.pop(field)
            self.assertFalse(body_evidence_matches(changed, receipt, source, post))
        changed = dict(receipt, observed_body=receipt['observed_body'] + '\n')
        changed['observed_body_sha256'] = hashlib.sha256(changed['observed_body'].encode()).hexdigest()
        self.assertFalse(body_evidence_matches(dict(done, **changed), changed, source, post))

    def test_observed_receipt_repairs_manifest_without_rewriting_history_or_source(self):
        source, post, receipt, done = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'draft.txt').write_text(source)
            social = root / 'social.json'
            social.write_text(json.dumps({'posts': [dict(post, posted_body_sha256='old')] }))
            inbox = {'records': [receipt]}; state = {'done': {'T1::x::en::x': done}}
            original = json.dumps([inbox, state])
            self.assertTrue(sync_verified_social_manifest(social, inbox, state))
            updated = json.loads(social.read_text())['posts'][0]
            self.assertEqual(updated['status'], 'posted')
            self.assertEqual(updated['posted_at'], done['published_at'])
            self.assertEqual(updated['observed_at'], receipt['observed_at'])
            self.assertEqual(updated['observed_body_sha256'], receipt['observed_body_sha256'])
            self.assertNotIn('posted_body_sha256', updated)
            self.assertEqual((root / 'draft.txt').read_text(), source)
            self.assertEqual(json.dumps([inbox, state]), original)
            self.assertFalse(sync_verified_social_manifest(social, inbox, state))
            joined = preserve_publication(dict(post, posted_body_sha256='old'),
                                          {'T1::x::en::x': dict(done, _valid_permalink=True)})
            self.assertNotIn('posted_body_sha256', joined)
            self.assertEqual(joined['observed_body_sha256'], receipt['observed_body_sha256'])

    def test_recovered_repository_receipt_preserves_original_observation(self):
        inbox = json.loads((ROOT / 'data/remote_browser_publications.json').read_text())
        receipt = next(r for r in inbox['records'] if r['manual_key'] == 'TOPIC-0020::x::en::x')
        self.assertEqual(receipt['observed_body_sha256'], 'e4f0ec9a5de9462e2c4dc1a8e03e2607b43b50e21ad184e80a80d81cccc40002')
        self.assertEqual(receipt['published_at'], '2026-10-14T00:54:49.000Z')
        self.assertEqual(receipt['observed_at'], '2026-10-15T00:44:18Z')
        self.assertEqual(receipt['processed_at'], '2026-10-15T00:45:29+00:00')
        self.assertEqual(receipt['canonical_destination_verified_at'], '2026-10-15T00:44:47Z')
        self.assertNotIn('posted_body_sha256', receipt)

    def test_new_observed_receipt_is_validated_before_any_state_write(self):
        source, post, receipt, _ = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'draft.txt').write_text(source)
            social, synd, inbox, state = [root / name for name in ('social.json', 'synd.json', 'inbox.json', 'state.json')]
            social.write_text(json.dumps({'posts': [post]}))
            synd.write_text(json.dumps({'drafts': []}))
            original = {'done': {}}
            state.write_text(json.dumps(original))
            receipt['status'] = 'new'
            valid_hash = receipt['observed_body_sha256']
            receipt['observed_body_sha256'] = '0' * 64
            inbox.write_text(json.dumps({'schema_version': 1, 'records': [receipt]}))
            before = inbox.read_bytes(), state.read_bytes(), social.read_bytes()
            with self.assertRaisesRegex(RemotePublicationError, 'invalid observed body evidence'):
                reconcile(inbox, state, social, synd)
            self.assertEqual(before, (inbox.read_bytes(), state.read_bytes(), social.read_bytes()))
            receipt['observed_body_sha256'] = valid_hash
            inbox.write_text(json.dumps({'schema_version': 1, 'records': [receipt]}))
            self.assertEqual(reconcile(inbox, state, social, synd), 1)
            done = json.loads(state.read_text())['done']['T1::x::en::x']
            self.assertEqual(done['observed_body_sha256'], valid_hash)
            self.assertNotIn('posted_body_sha256', done)

    def test_receipt_context_cannot_rewrite_manifest_canonical_url(self):
        source, post, receipt, done = self.fixture()
        key = receipt['manual_key']
        evidence = dict(done, _valid_permalink=True, canonical_url='https://onnellab.com/blog/en/stale/')
        with self.assertRaisesRegex(ValueError, 'canonical URL mismatch'):
            preserve_publication(post, {key: evidence})
        self.assertFalse(body_evidence_matches(evidence, dict(receipt, canonical_url=evidence['canonical_url']), source, post))
        # Untyped legacy evidence retains existing behavior but cannot replace context.
        evidence.pop('body_evidence_kind')
        joined = preserve_publication(post, {key: evidence})
        self.assertEqual(joined['canonical_url'], post['canonical_url'])

    def test_submitted_source_sync_cannot_replace_manifest_canonical_url(self):
        source, post, receipt, done = self.fixture()
        for record in (receipt, done):
            record.pop('observed_body_sha256')
            record['body_evidence_kind'] = 'submitted_source'
            record['posted_body_sha256'] = hashlib.sha256(source.removesuffix('\n').encode()).hexdigest()
            record['canonical_url'] = 'https://onnellab.com/blog/en/stale/'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'draft.txt').write_text(source)
            social = root / 'social.json'
            social.write_text(json.dumps({'posts': [post]}))
            self.assertTrue(sync_verified_social_manifest(social, {'records': [receipt]},
                                                          {'done': {receipt['manual_key']: done}}))
            self.assertEqual(json.loads(social.read_text())['posts'][0]['canonical_url'], post['canonical_url'])


if __name__ == '__main__':
    unittest.main()
