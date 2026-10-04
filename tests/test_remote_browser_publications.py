from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from reconcile_remote_browser_publications import RemotePublicationError, normalized_permalink, reconcile
from publication_history import publication_history, preserve_publication

class RemoteBrowserPublicationTest(unittest.TestCase):
    def manifests(self, root: Path):
        social=root/'social.json'; synd=root/'synd.json'
        social.write_text(json.dumps({'posts':[{'topic_id':'T1','platform':'x','language':'en','template_id':'x','is_variant':False}]}))
        synd.write_text(json.dumps({'drafts':[{'topic_id':'T2','platform':'medium','language':'en'}]}))
        return social,synd
    def test_specific_permalinks_only(self):
        self.assertEqual(normalized_permalink('x','https://x.com/onnellab/status/123'),'https://x.com/onnellab/status/123')
        self.assertIn('medium.com/@onnellab/post-',normalized_permalink('medium','https://medium.com/@onnellab/post-abc123'))
        for platform,url in [('x','https://x.com/onnellab'),('linkedin','https://www.linkedin.com/in/onnellab/'),('hashnode','https://onnellab.hashnode.dev/rss.xml'),('medium','https://medium.com/@onnellab.app')]:
            with self.subTest(platform=platform), self.assertRaises(RemotePublicationError): normalized_permalink(platform,url)
    def test_reconcile_marks_done_and_processes_inbox(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); social,synd=self.manifests(root); inbox=root/'inbox.json'; state=root/'state.json'
            inbox.write_text(json.dumps({'schema_version':1,'records':[{'manual_key':'T1::x::en::x','platform':'x','posted_url':'https://x.com/onnellab/status/123','published_at':'2026-09-19T09:05:00+09:00','status':'new'}]}))
            state.write_text(json.dumps({'version':1,'updated_at':'','done':{}}))
            self.assertEqual(reconcile(inbox,state,social,synd),1)
            done=json.loads(state.read_text())['done']['T1::x::en::x']
            self.assertEqual(done['marked_by'],'chatgpt_remote_browser')
            self.assertEqual(done['posted_url'],'https://x.com/onnellab/status/123')
            self.assertEqual(json.loads(inbox.read_text())['records'][0]['status'],'processed')
    def test_invalid_record_fails_before_state_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); social,synd=self.manifests(root); inbox=root/'inbox.json'; state=root/'state.json'
            inbox.write_text(json.dumps({'schema_version':1,'records':[{'manual_key':'T1::x::en::x','platform':'x','posted_url':'https://x.com/onnellab','status':'new'}]}))
            original={'version':1,'updated_at':'','done':{}};state.write_text(json.dumps(original))
            with self.assertRaises(RemotePublicationError): reconcile(inbox,state,social,synd)
            self.assertEqual(json.loads(state.read_text()),original)

    def test_existing_permalink_conflict_cannot_overwrite_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            social, synd = self.manifests(root)
            inbox = root / 'inbox.json'
            state = root / 'state.json'
            key = 'T1::x::en::x'
            inbox.write_text(json.dumps({'schema_version': 1, 'records': [{'manual_key': key, 'platform': 'x', 'posted_url': 'https://x.com/onnellab/status/456', 'status': 'new'}]}))
            state.write_text(json.dumps({'done': {key: {'posted_url': 'https://x.com/onnellab/status/123', 'marked_at': 'original'}}}))
            original_state, original_inbox = state.read_bytes(), inbox.read_bytes()
            with self.assertRaisesRegex(RemotePublicationError, 'conflicting'):
                reconcile(inbox, state, social, synd)
            self.assertEqual(state.read_bytes(), original_state)
            self.assertEqual(inbox.read_bytes(), original_inbox)

    def test_same_permalink_preserves_existing_evidence_and_legacy_profile_can_upgrade(self):
        for existing in ('https://x.com/onnellab/status/123', 'https://x.com/onnellab'):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                social, synd = self.manifests(root)
                inbox, state = root / 'inbox.json', root / 'state.json'
                key = 'T1::x::en::x'
                old = {'posted_url': existing, 'marked_at': 'original', 'marked_by': 'original_verifier'}
                state.write_text(json.dumps({'done': {key: old}}))
                inbox.write_text(json.dumps({'schema_version': 1, 'records': [{'manual_key': key, 'platform': 'x', 'posted_url': 'https://x.com/onnellab/status/123', 'status': 'new'}]}))
                self.assertEqual(reconcile(inbox, state, social, synd), 1)
                result = json.loads(state.read_text())['done'][key]
                self.assertEqual(result['posted_url'], 'https://x.com/onnellab/status/123')
                if '/status/' in existing:
                    self.assertEqual(result, old)
                self.assertEqual(reconcile(inbox, state, social, synd), 0)

    def test_unrelated_linkedin_host_and_editor_urls_are_not_permalinks(self):
        for platform, url in [('linkedin', 'https://evillinkedin.com/posts/fake'), ('medium', 'https://medium.com/p/abc123/edit')]:
            with self.subTest(url=url), self.assertRaises(RemotePublicationError):
                normalized_permalink(platform, url)

    def test_unknown_server_publication_time_keeps_observation_provenance_and_no_fabricated_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            social, synd = self.manifests(root)
            inbox, state = root / 'inbox.json', root / 'state.json'
            provenance = {'published_at_precision': 'unknown',
                'observed_at': '2026-10-04T06:33:36Z', 'observed_at_precision': 'approximate',
                'observation_source': 'parent_authoritative_local_chrome',
                'browser_ui_timestamp': 'Oct 3 11:33 PM', 'browser_ui_timezone': 'unknown',
                'draft_sha256': 'a' * 64, 'posted_body_sha256': 'b' * 64, 'account': '@onnellab',
                'draft_hash_normalization': 'UTF-8 with CRLF normalized to LF',
                'posted_body_hash_normalization': 'same, terminal LF removed'}
            record = {'manual_key': 'T1::x::en::x', 'platform': 'x',
                'posted_url': 'https://x.com/onnellab/status/123', 'published_at': '',
                'status': 'new', **provenance}
            inbox.write_text(json.dumps({'schema_version': 1, 'records': [record]}))
            state.write_text(json.dumps({'done': {}}))
            self.assertEqual(1, reconcile(inbox, state, social, synd))
            done = json.loads(state.read_text())['done']['T1::x::en::x']
            self.assertEqual('', done['published_at'])
            self.assertTrue(done['marked_at'])
            self.assertTrue(done['verified_at'])
            for field, value in provenance.items():
                self.assertEqual(value, done[field])
                self.assertEqual(value, json.loads(inbox.read_text())['records'][0][field])
            before = state.read_bytes(), inbox.read_bytes()
            self.assertEqual(0, reconcile(inbox, state, social, synd))
            self.assertEqual(before, (state.read_bytes(), inbox.read_bytes()))

    def test_unknown_receipt_join_does_not_promote_marked_or_stale_posted_time(self):
        from publishing import apply_previous_social_state
        key = 'T1::x::en::x'
        item = {'topic_id': 'T1', 'platform': 'x', 'language': 'en', 'template_id': 'x',
                'status': 'draft', 'posted_at': '2026-10-04T07:00:00Z'}
        evidence = {'_valid_permalink': True, 'posted_url': 'https://x.com/onnellab/status/123',
                    'published_at': '', 'published_at_precision': 'unknown',
                    'marked_at': '2026-10-04T07:00:00Z', 'observed_at': '2026-10-04T06:33:36Z',
                    'observed_at_precision': 'approximate', 'draft_hash_normalization': 'LF'}
        joined = preserve_publication(item, {key: evidence})
        self.assertEqual('posted', joined['status'])
        self.assertEqual('', joined['posted_at'])
        self.assertEqual('unknown', joined['published_at_precision'])
        target = dict(item, posted_at='')
        apply_previous_social_state(target, {('T1', 'x', 'en', 'x'): joined})
        self.assertEqual('', target['posted_at'])
        self.assertEqual('unknown', target['published_at_precision'])
        self.assertEqual('LF', target['draft_hash_normalization'])

    def test_unknown_time_with_a_claimed_exact_date_fails_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            social, synd = self.manifests(root)
            inbox, state = root / 'inbox.json', root / 'state.json'
            inbox.write_text(json.dumps({'schema_version': 1, 'records': [{
                'manual_key': 'T1::x::en::x', 'platform': 'x', 'status': 'new',
                'posted_url': 'https://x.com/onnellab/status/123',
                'published_at_precision': 'unknown', 'published_at': '2026-10-04T06:33:36Z'}]}))
            state.write_text(json.dumps({'done': {}}))
            before = state.read_bytes(), inbox.read_bytes()
            with self.assertRaisesRegex(RemotePublicationError, 'unknown publication time'):
                reconcile(inbox, state, social, synd)
            self.assertEqual(before, (state.read_bytes(), inbox.read_bytes()))

if __name__=='__main__': unittest.main()
