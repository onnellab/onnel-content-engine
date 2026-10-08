from __future__ import annotations
import json
import hashlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_manual_publish_site import apply_manual_publish_schedule
from publication_history import specific_permalink

class ManualPublishBacklogScheduleTest(unittest.TestCase):
    def write_schedule(self,path,backlog):
        path.write_text(json.dumps({'schema_version':1,'backlog':backlog}),encoding='utf-8')

    def test_frozen_backlog_overrides_only_named_items(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'schedule.json'; self.write_schedule(p,[{'sequence':1,'manual_key':'old','publish_at':'2026-09-19T09:00:00+09:00'}])
            items=[{'manual_key':'old','publishing_mode':'manual','due_at':'2026-08-01T09:00:00+09:00'}, {'manual_key':'future','publishing_mode':'manual','due_at':'2026-10-10T09:00:00+09:00'}, {'manual_key':'auto','publishing_mode':'automatic','due_at':'2026-08-01T09:00:00+09:00'}]
            apply_manual_publish_schedule(items,p)
        self.assertEqual(items[0]['manual_publish_due_at'],'2026-09-19T09:00:00+09:00')
        self.assertEqual(items[0]['original_due_at'],'2026-08-01T09:00:00+09:00')
        self.assertEqual(items[0]['manual_publish_schedule_kind'],'backlog')
        self.assertEqual(items[1]['manual_publish_due_at'],'2026-10-10T09:00:00+09:00')
        self.assertEqual(items[1]['manual_publish_schedule_kind'],'scheduled')
        self.assertNotIn('manual_publish_due_at',items[2])

    def test_duplicate_backlog_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'schedule.json'; self.write_schedule(p,[{'manual_key':'a','publish_at':'2026-09-19T09:00:00+09:00'},{'manual_key':'a','publish_at':'2026-09-20T09:00:00+09:00'}])
            with self.assertRaisesRegex(ValueError,'duplicate manual publish backlog key'):
                apply_manual_publish_schedule([],p)

    def test_repository_backlog_excludes_disabled_hashnode_items(self):
        payload=json.loads((ROOT/'data/manual_publish_schedule.json').read_text())
        rows=payload['backlog']; self.assertEqual(len(rows),21)
        self.assertEqual(len({r['manual_key'] for r in rows}),21)
        dates=[datetime.fromisoformat(r['publish_at']) for r in rows]
        self.assertEqual(dates,sorted(dates))
        self.assertEqual(rows[0]['publish_at'],'2026-09-20T09:00:00+09:00')
        self.assertEqual(rows[-1]['publish_at'],'2026-10-16T09:00:00+09:00')
        keys={r['manual_key'] for r in rows}
        self.assertIn('TOPIC-0016::x::en::x',keys)
        self.assertIn('TOPIC-0018::medium::en::markdown',keys)
        self.assertNotIn('TOPIC-0020::hashnode::en::markdown',keys)
        self.assertFalse(any(r.get('platform')=='hashnode' for r in rows))
        self.assertNotIn('TOPIC-0020::medium::en::markdown',keys)
        self.assertEqual(payload['policy']['future_manual_items'],'use_original_due_at')

    def test_false_404_completions_are_reopened_but_real_medium_post_stays_done(self):
        state=json.loads((ROOT/'data/manual_publish_state.json').read_text())['done']
        reopened={
            'TOPIC-0016::x::en::x','TOPIC-0016::linkedin::en::linkedin','TOPIC-0016::medium::en::markdown',
            'TOPIC-0018::x::en::x','TOPIC-0018::linkedin::en::linkedin','TOPIC-0018::medium::en::markdown',
            'TOPIC-0020::x::en::x','TOPIC-0020::linkedin::en::linkedin',
        }
        # A historical requeue can later be completed, but only with new,
        # hash-bound specific-post evidence. Never restore the false profile URL.
        receipts=json.loads((ROOT/'data/remote_browser_publications.json').read_text())['records']
        manifest=json.loads((ROOT/'generated/social/manifest.json').read_text())['posts']
        audit=json.loads((ROOT/'data/manual_publication_requeues.json').read_text())
        previous={row['manual_key']:row['previous_done_record'] for row in audit['requeued']}
        for receipt in receipts:
            if receipt.get('manual_key') in reopened and receipt.get('status')=='processed':
                self.assertIn(receipt['manual_key'],state)
        for key in reopened.intersection(state):
            with self.subTest(manual_key=key):
                done=state[key]
                matching=[r for r in receipts if r.get('manual_key')==key and r.get('status')=='processed'
                          and r.get('posted_url')==done.get('posted_url')]
                self.assertEqual(len(matching),1)
                posts=[p for p in manifest if '::'.join(str(p.get(k,'')) for k in
                       ('topic_id','platform','language','template_id'))==key]
                self.assertEqual(len(posts),1)
                source=(ROOT/posts[0]['draft_path']).resolve()
                self.assertTrue(source.is_relative_to(ROOT))
                draft=source.read_text(encoding='utf-8').replace('\r\n','\n')
                self.assert_verified_requeue_completion(done,previous[key],matching[0],draft,audit['requeued_at'],key)
                self.assertEqual(posts[0]['status'],'posted')
                self.assertEqual(posts[0]['posted_url'],done['posted_url'])
        self.assertIn('TOPIC-0020::medium::en::markdown',state)
        audit=json.loads((ROOT/'data/manual_publication_requeues.json').read_text())
        self.assertEqual({x['manual_key'] for x in audit['requeued']},reopened)
        self.assertEqual({x['manual_key'] for x in audit['withdrawn']},{'TOPIC-0020::hashnode::en::markdown'})
        self.assertEqual(audit['source_availability']['canonical_pages_http_status'],200)
        self.assertEqual(audit['source_availability']['social_cards_http_status'],200)

    def assert_verified_requeue_completion(self,done,previous,receipt,draft,requeued_at,manual_key):
        for record in (done,receipt):
            self.assertEqual('::'.join(str(record.get(field,'')) for field in ('topic_id','platform','language','template_id')),manual_key)
        self.assertTrue(specific_permalink(done['platform'],done.get('posted_url')))
        self.assertNotEqual(done['posted_url'],previous.get('posted_url'))
        self.assertEqual(receipt.get('posted_url'),done['posted_url'])
        self.assertEqual(receipt.get('status'),'processed')
        for field in ('topic_id','platform','language','template_id'):
            self.assertEqual(done.get(field),receipt.get(field))
        observed=datetime.fromisoformat(receipt['observed_at'].replace('Z','+00:00'))
        verified=datetime.fromisoformat(done['verified_at'].replace('Z','+00:00'))
        requeued=datetime.fromisoformat(requeued_at.replace('Z','+00:00'))
        self.assertIsNotNone(observed.tzinfo)
        self.assertIsNotNone(verified.tzinfo)
        self.assertGreater(observed,requeued)
        self.assertGreaterEqual(verified,observed)
        self.assertTrue(receipt.get('observation_source'))
        self.assertTrue(done.get('verification_method'))
        expected={
            'draft_sha256':hashlib.sha256(draft.encode('utf-8')).hexdigest(),
            'posted_body_sha256':hashlib.sha256(draft.removesuffix('\n').encode('utf-8')).hexdigest(),
        }
        for field,digest in expected.items():
            self.assertEqual(done.get(field),digest)
            self.assertEqual(receipt.get(field),digest)

    def test_requeue_completion_rejects_profile_stale_and_unbound_evidence(self):
        draft='A verified draft.\n'
        done={'topic_id':'TOPIC-0016','platform':'x','language':'en','template_id':'x',
              'posted_url':'https://x.com/onnellab/status/123456','verified_at':'2026-10-08T06:25:40Z',
              'verification_method':'browser_permalink',
              'draft_sha256':hashlib.sha256(draft.encode()).hexdigest(),
              'posted_body_sha256':hashlib.sha256(draft.removesuffix('\n').encode()).hexdigest()}
        previous={'posted_url':'https://x.com/onnellab'}
        receipt=dict(done,status='processed',observed_at='2026-10-08T06:25:40Z',
                     observation_source='Verified exact public post and submitted source.')
        self.assert_verified_requeue_completion(done,previous,receipt,draft,'2026-09-19T07:40:43+09:00','TOPIC-0016::x::en::x')
        with self.assertRaises(AssertionError):
            self.assert_verified_requeue_completion(dict(done,topic_id='TOPIC-9999'),previous,dict(receipt,topic_id='TOPIC-9999'),draft,'2026-09-19T07:40:43+09:00','TOPIC-0016::x::en::x')
        for change in (
            {'posted_url':'https://x.com/onnellab'},
            {'observed_at':'2026-09-18T00:00:00Z'},
            {'draft_sha256':'0'*64},
            {'posted_body_sha256':'0'*64},
            {'status':'new'},
            {'topic_id':'TOPIC-9999'},
            {'observation_source':''},
        ):
            with self.subTest(change=change),self.assertRaises(AssertionError):
                self.assert_verified_requeue_completion(done,previous,dict(receipt,**change),draft,'2026-09-19T07:40:43+09:00','TOPIC-0016::x::en::x')

if __name__=='__main__': unittest.main()

