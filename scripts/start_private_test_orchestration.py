#!/usr/bin/env python3
"""Record one human approval for the complete private-test delivery chain."""
from __future__ import annotations
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from validate_app_releases import RELEASE_HEADER,RELEASES_PATH,read_csv
ROOT=Path(__file__).resolve().parents[1]; PATH=ROOT/'data/private_test_orchestrations.json'
def main() -> int:
 p=argparse.ArgumentParser();p.add_argument('task_id');p.add_argument('--release-id',required=True);p.add_argument('--approver',required=True);p.add_argument('--confirm',action='store_true');a=p.parse_args()
 releases=read_csv(RELEASES_PATH,RELEASE_HEADER); release=next((x for x in releases if x['release_id']==a.release_id),None)
 tasks=json.loads((ROOT/'data/ai_coder_tasks.json').read_text()).get('tasks',[]); task=next((x for x in tasks if x.get('task_id')==a.task_id),None)
 if not release or release['platform'] not in {'android','ios'} or release['status']!='planned' or release['release_type']!='binary' or release['release_channel']!='private_test': raise SystemExit('release must be a planned Android/iOS private_test binary')
 if not task or task.get('status')!='draft_pr_created' or task.get('app_slug')!=release['app_slug'] or task.get('repository')!=release['repository']: raise SystemExit('QA candidate task must match the private-test release app')
 report=ROOT/'data/qa-reports'/f"{a.task_id}.json"; check=subprocess.run([sys.executable,str(ROOT/'scripts/validate_ai_qa_report.py'),str(report)],capture_output=True,text=True)
 if check.returncode: raise SystemExit('task QA report is not a complete PASS')
 payload=json.loads(PATH.read_text()); rows=payload.get('orchestrations')
 if not isinstance(rows,list) or any(x.get('release_id')==a.release_id and x.get('status') not in {'completed','failed'} for x in rows): raise SystemExit('release already has an active private-test orchestration')
 if not a.confirm: print('dry run: orchestration is valid'); return 0
 now=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); rows.append({'orchestration_id':f"PTO-{a.task_id}-{a.release_id}",'task_id':a.task_id,'release_id':a.release_id,'platform':release['platform'],'approver':a.approver,'status':'approved_for_merge','approved_at':now,'last_transition_at':now})
 PATH.write_text(json.dumps({'orchestrations':rows},ensure_ascii=False,indent=2)+'\n'); return 0
if __name__=='__main__': raise SystemExit(main())
