#!/usr/bin/env python3
"""Approve a single evidence-only policy assessment; this never authorizes a patch."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("task_id"); parser.add_argument("--approver", required=True); parser.add_argument("--confirm", action="store_true"); args=parser.parse_args()
    path=ROOT/"data/store_policy_impact_tasks.json"; payload=json.loads(path.read_text(encoding="utf-8"))
    task=next((item for item in payload.get("tasks",[]) if item.get("task_id")==args.task_id),None)
    if not task or task.get("status") != "review_required": raise SystemExit("task must exist and be review_required")
    if not args.confirm: print(f"dry run: would approve assessment for {args.task_id}"); return 0
    task.update({"status":"approved_for_assessment","approved_by":args.approver,"approved_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"approved policy assessment {args.task_id}")
    return 0
if __name__=="__main__": raise SystemExit(main())
