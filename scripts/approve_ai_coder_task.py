#!/usr/bin/env python3
"""Approve exactly one proposed AI-Coder task for Draft-PR work."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("task_id"); parser.add_argument("--approver",required=True); parser.add_argument("--confirm",action="store_true"); args=parser.parse_args()
    path=ROOT/"data/ai_coder_tasks.json"; payload=json.loads(path.read_text(encoding="utf-8")); task=next((x for x in payload.get("tasks",[]) if x.get("task_id")==args.task_id),None)
    if not task or task.get("status")!="proposed": raise SystemExit("task must exist and be proposed")
    if not args.confirm: print(f"dry run: would approve {args.task_id}"); return 0
    task.update({"status":"approved_for_draft_pr","approved_by":args.approver,"approved_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"approved {args.task_id}"); return 0
if __name__=="__main__": raise SystemExit(main())
