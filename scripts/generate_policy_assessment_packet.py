#!/usr/bin/env python3
"""Create the bounded input packet for one approved local Codex policy assessment."""
from __future__ import annotations
import argparse, csv, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 parser=argparse.ArgumentParser(); parser.add_argument("task_id"); args=parser.parse_args()
 tasks=json.loads((ROOT/"data/store_policy_impact_tasks.json").read_text(encoding="utf-8")).get("tasks",[])
 task=next((item for item in tasks if item.get("task_id")==args.task_id),None)
 if not task or task.get("status")!="approved_for_assessment": raise SystemExit("task must be approved_for_assessment")
 with (ROOT/"data/local_repositories.csv").open(encoding="utf-8",newline="") as handle: local=next((row for row in csv.DictReader(handle) if row["app_slug"]==task.get("app_slug")),None)
 if not local or not Path(local["path"]).expanduser().is_dir(): raise SystemExit("mapped local app checkout is unavailable")
 packet={"task":task,"app_path":local["path"],"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"output":"data/store_policy_assessments.json","rules":["Read-only assessment only.","Use only task evidence and file/rule references.","Do not infer compliance or a remediation.","Do not edit code, store metadata, policy settings, or credentials."]}
 out=ROOT/"generated/policy-assessments"; out.mkdir(parents=True,exist_ok=True); path=out/f"{args.task_id}.json"; path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(path)
 return 0
if __name__=="__main__": raise SystemExit(main())
