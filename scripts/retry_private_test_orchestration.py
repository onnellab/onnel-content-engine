#!/usr/bin/env python3
"""Resume a failed private-test orchestration from the latest safe evidence."""
from __future__ import annotations
import argparse,csv,json
from datetime import datetime,timezone
from pathlib import Path
from sync_codemagic_artifact_urls import CODEMAGIC_BUILDS_HEADER
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 p=argparse.ArgumentParser();p.add_argument('orchestration_id');p.add_argument('--approver',required=True);p.add_argument('--confirm',action='store_true');a=p.parse_args(); op=ROOT/'data/private_test_orchestrations.json'; payload=json.loads(op.read_text()); row=next((x for x in payload.get('orchestrations',[]) if x.get('orchestration_id')==a.orchestration_id),None)
 if not row or row.get('status')!='failed': raise SystemExit('orchestration must exist and be failed')
 if row.get('failure')=='upload_dispatched_timeout': raise SystemExit('upload outcome is ambiguous; verify the store console before retrying')
 submissions=json.loads((ROOT/'data/internal_store_submissions.json').read_text()).get('submissions',[])
 if any(x.get('release_id')==row['release_id'] and x.get('status')=='uploaded' for x in submissions): raise SystemExit('release is already recorded as uploaded')
 tasks=json.loads((ROOT/'data/ai_coder_tasks.json').read_text()).get('tasks',[]); task=next((x for x in tasks if x.get('task_id')==row['task_id']),{})
 builds_path=ROOT/'data/private_test_build_requests.json'; bp=json.loads(builds_path.read_text()); active=[x for x in bp.get('requests',[]) if x.get('release_id')==row['release_id'] and x.get('status')!='retry_superseded']; build=active[-1] if active else None
 if build and build.get('status') in {'dispatched','running','succeeded'}: raise SystemExit('build outcome is still active or ambiguous; collect its status before retrying')
 if not a.confirm: print('dry run: orchestration retry is safe'); return 0
 if build and build.get('status')=='failed':
  build['status']='retry_superseded'; build['superseded_at']=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
  if row['platform']=='ios':
   cm=ROOT/'data/codemagic_builds.csv'; rows=list(csv.DictReader(cm.open(newline=''))); target=next((x for x in rows if x['release_id']==row['release_id']),None)
   if not target: raise SystemExit('Codemagic mapping is missing'); target['build_id']=''; target['notes']='Cleared after approved retry.'
   with cm.open('w',newline='') as h: w=csv.DictWriter(h,fieldnames=CODEMAGIC_BUILDS_HEADER,lineterminator='\n');w.writeheader();w.writerows(rows)
  builds_path.write_text(json.dumps(bp,ensure_ascii=False,indent=2)+'\n')
 readiness=json.loads((ROOT/'data/internal_test_readiness.json').read_text()).get('records',[])
 if any(x.get('release_id')==row['release_id'] and x.get('status')=='ready_for_internal_upload' for x in readiness): status='readiness_dispatched'
 elif build and build.get('status')=='artifact_ready': status='build_dispatched'
 elif task.get('status')=='merged': status='merge_dispatched'
 else: status='approved_for_merge'
 now=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); row.setdefault('retry_history',[]).append({'failure':row.get('failure'),'approved_by':a.approver,'retried_at':now}); row['status']=status; row['approver']=a.approver; row.pop('failure',None); row['last_transition_at']=now; op.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n'); return 0
if __name__=='__main__': raise SystemExit(main())
