#!/usr/bin/env python3
"""Advance at most one private-test orchestration stage from recorded evidence."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PATH=ROOT/'data/private_test_orchestrations.json'
def load(name,default):
 p=ROOT/'data'/name; return json.loads(p.read_text()) if p.exists() else default
def main() -> int:
 p=argparse.ArgumentParser();p.add_argument('--github-output',type=Path,required=True);a=p.parse_args(); payload=load('private_test_orchestrations.json',{'orchestrations':[]}); rows=payload.get('orchestrations',[])
 active=next((x for x in rows if x.get('status') not in {'completed','failed'}),None); action='none'
 if active:
  status=active['status']; task_id=active['task_id']; release_id=active['release_id']; platform=active['platform']
  tasks=load('ai_coder_tasks.json',{'tasks':[]}).get('tasks',[]); task=next((x for x in tasks if x.get('task_id')==task_id),{})
  builds=load('private_test_build_requests.json',{'requests':[]}).get('requests',[]); build=next((x for x in reversed(builds) if x.get('release_id')==release_id and x.get('status')!='retry_superseded'),{})
  ready=load('internal_test_readiness.json',{'records':[]}).get('records',[]); upload=load('internal_store_submissions.json',{'submissions':[]}).get('submissions',[])
  try: transitioned=datetime.fromisoformat(active.get('last_transition_at',''))
  except ValueError: transitioned=None
  if status.endswith('_dispatched') and (transitioned is None or transitioned.tzinfo is None or transitioned+timedelta(hours=6)<=datetime.now(timezone.utc)): active['status']='failed'; active['failure']=f'{status}_timeout'
  elif status=='approved_for_merge': action='merge'; active['status']='merge_dispatched'
  elif status=='merge_dispatched' and task.get('status')=='merged': action='android_build' if platform=='android' else 'ios_build'; active['status']='build_dispatched'
  elif status=='build_dispatched' and build.get('status')=='failed': active['status']='failed'; active['failure']='private_test_build_failed'
  elif status=='build_dispatched' and build.get('status')=='artifact_ready': action='readiness'; active['status']='readiness_dispatched'
  elif status=='readiness_dispatched' and any(x.get('release_id')==release_id and x.get('status')=='ready_for_internal_upload' for x in ready): action='upload'; active['status']='upload_dispatched'
  elif status=='upload_dispatched' and any(x.get('release_id')==release_id and x.get('status')=='uploaded' for x in upload): active['status']='completed'
  if action!='none' or active.get('status') in {'completed','failed'}: active['last_transition_at']=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); PATH.write_text(json.dumps({'orchestrations':rows},ensure_ascii=False,indent=2)+'\n')
  a.github_output.write_text(f"action={action}\ntask_id={task_id}\nrelease_id={release_id}\napprover={active['approver']}\n",encoding='utf-8')
 else: a.github_output.write_text('action=none\n',encoding='utf-8')
 return 0
if __name__=='__main__': raise SystemExit(main())
