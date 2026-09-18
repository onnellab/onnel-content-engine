from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from reconcile_work_browser_publications import WorkPublicationError, normalized_permalink, reconcile

class WorkBrowserPublicationTest(unittest.TestCase):
    def manifests(self, root: Path):
        social=root/'social.json'; synd=root/'synd.json'
        social.write_text(json.dumps({'posts':[{'topic_id':'T1','platform':'x','language':'en','template_id':'x','is_variant':False}]}))
        synd.write_text(json.dumps({'drafts':[{'topic_id':'T2','platform':'medium','language':'en'}]}))
        return social,synd
    def test_specific_permalinks_only(self):
        self.assertEqual(normalized_permalink('x','https://x.com/onnellab/status/123'),'https://x.com/onnellab/status/123')
        self.assertIn('medium.com/@onnellab/post-',normalized_permalink('medium','https://medium.com/@onnellab/post-abc123'))
        for platform,url in [('x','https://x.com/onnellab'),('linkedin','https://www.linkedin.com/in/onnellab/'),('hashnode','https://onnellab.hashnode.dev/rss.xml'),('medium','https://medium.com/@onnellab.app')]:
            with self.subTest(platform=platform), self.assertRaises(WorkPublicationError): normalized_permalink(platform,url)
    def test_reconcile_marks_done_and_processes_inbox(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); social,synd=self.manifests(root); inbox=root/'inbox.json'; state=root/'state.json'
            inbox.write_text(json.dumps({'schema_version':1,'records':[{'manual_key':'T1::x::en::x','platform':'x','posted_url':'https://x.com/onnellab/status/123','published_at':'2026-09-19T09:05:00+09:00','status':'new'}]}))
            state.write_text(json.dumps({'version':1,'updated_at':'','done':{}}))
            self.assertEqual(reconcile(inbox,state,social,synd),1)
            done=json.loads(state.read_text())['done']['T1::x::en::x']
            self.assertEqual(done['marked_by'],'chatgpt_work_browser')
            self.assertEqual(done['posted_url'],'https://x.com/onnellab/status/123')
            self.assertEqual(json.loads(inbox.read_text())['records'][0]['status'],'processed')
    def test_invalid_record_fails_before_state_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); social,synd=self.manifests(root); inbox=root/'inbox.json'; state=root/'state.json'
            inbox.write_text(json.dumps({'schema_version':1,'records':[{'manual_key':'T1::x::en::x','platform':'x','posted_url':'https://x.com/onnellab','status':'new'}]}))
            original={'version':1,'updated_at':'','done':{}};state.write_text(json.dumps(original))
            with self.assertRaises(WorkPublicationError): reconcile(inbox,state,social,synd)
            self.assertEqual(json.loads(state.read_text()),original)

if __name__=='__main__': unittest.main()
