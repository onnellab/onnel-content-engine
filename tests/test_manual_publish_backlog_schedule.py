from __future__ import annotations
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_manual_publish_site import apply_manual_publish_schedule

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

    def test_repository_backlog_includes_reopened_404_items_at_one_daily_slot(self):
        payload=json.loads((ROOT/'data/manual_publish_schedule.json').read_text())
        rows=payload['backlog']; self.assertEqual(len(rows),29)
        self.assertEqual(len({r['manual_key'] for r in rows}),29)
        start=datetime.fromisoformat('2026-09-19T09:00:00+09:00')
        for index,row in enumerate(rows):
            self.assertEqual(datetime.fromisoformat(row['publish_at']),start+timedelta(days=index))
        self.assertEqual(rows[-1]['publish_at'],'2026-10-17T09:00:00+09:00')
        keys={r['manual_key'] for r in rows}
        self.assertIn('TOPIC-0016::x::en::x',keys)
        self.assertIn('TOPIC-0018::medium::en::markdown',keys)
        self.assertIn('TOPIC-0020::hashnode::en::markdown',keys)
        self.assertNotIn('TOPIC-0020::medium::en::markdown',keys)
        self.assertEqual(payload['policy']['future_manual_items'],'use_original_due_at')

    def test_false_404_completions_are_reopened_but_real_medium_post_stays_done(self):
        state=json.loads((ROOT/'data/manual_publish_state.json').read_text())['done']
        reopened={
            'TOPIC-0016::x::en::x','TOPIC-0016::linkedin::en::linkedin','TOPIC-0016::medium::en::markdown',
            'TOPIC-0018::x::en::x','TOPIC-0018::linkedin::en::linkedin','TOPIC-0018::medium::en::markdown',
            'TOPIC-0020::x::en::x','TOPIC-0020::linkedin::en::linkedin','TOPIC-0020::hashnode::en::markdown',
        }
        self.assertTrue(reopened.isdisjoint(state))
        self.assertIn('TOPIC-0020::medium::en::markdown',state)
        audit=json.loads((ROOT/'data/manual_publication_requeues.json').read_text())
        self.assertEqual({x['manual_key'] for x in audit['requeued']},reopened)
        self.assertEqual(audit['source_availability']['canonical_pages_http_status'],200)
        self.assertEqual(audit['source_availability']['social_cards_http_status'],200)

if __name__=='__main__': unittest.main()
