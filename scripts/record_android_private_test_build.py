#!/usr/bin/env python3
"""Record the AAB artifact produced by the engine's Android build workflow."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('task_id'); p.add_argument('--release-id',required=True); p.add_argument('--tag',required=True); p.add_argument('--run-id',required=True); p.add_argument('--artifact-name',required=True); p.add_argument('--status',choices=('artifact_ready','failed'),required=True); p.add_argument('--approver',required=True); a=p.parse_args()
 path=ROOT/'data/private_test_build_requests.json'; payload=json.loads(path.read_text()); rows=payload.get('requests',[])
 if not isinstance(rows,list) or any(x.get('release_id')==a.release_id for x in rows): raise SystemExit('private test build request is invalid or already recorded')
 rows.append({'task_id':a.task_id,'release_id':a.release_id,'tag':a.tag,'github_run_id':a.run_id,'artifact_name':a.artifact_name if a.status=='artifact_ready' else '','source':'github_actions','status':a.status,'approved_by':a.approver,'dispatched_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
 path.write_text(json.dumps({'requests':rows},ensure_ascii=False,indent=2)+'\n'); return 0
if __name__=='__main__': raise SystemExit(main())
