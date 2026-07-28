#!/usr/bin/env python3
"""Create a proposed AI-Coder task from a human-selected FAIL policy assessment."""
from __future__ import annotations
import argparse, csv, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument("task_id"); p.add_argument("--approver",required=True); p.add_argument("--scope",required=True); p.add_argument("--allowed-path",action="append",default=[]); p.add_argument("--confirm",action="store_true"); a=p.parse_args()
 scope=" ".join(a.scope.split())
 if not scope or len(scope)>500 or not a.allowed_path: raise SystemExit("a concise --scope and at least one --allowed-path are required")
 if any(not item or item.startswith("/") or ".." in Path(item).parts for item in a.allowed_path): raise SystemExit("--allowed-path must be a safe app-relative path")
 assessments=json.loads((ROOT/"data/store_policy_assessments.json").read_text(encoding="utf-8")).get("assessments",[])
 assessment=next((x for x in assessments if x.get("task_id")==a.task_id),None)
 if not assessment or assessment.get("status")!="FAIL" or assessment.get("patch_authorized") is not False: raise SystemExit("only a recorded FAIL assessment with patch_authorized:false can be escalated")
 policy=json.loads((ROOT/"data/store_policy_impact_tasks.json").read_text(encoding="utf-8")).get("tasks",[]); source=next((x for x in policy if x.get("task_id")==a.task_id),None)
 if not source or source.get("status")!="assessment_complete": raise SystemExit("policy task must be assessment_complete")
 new_id=f"remediate-{a.task_id}"
 if not a.confirm: print(f"dry run: would create proposed coder task {new_id}"); return 0
 with (ROOT/"data/app_release_config.csv").open(encoding="utf-8",newline="") as h: repos={r["app_slug"]:r["repository"] for r in csv.DictReader(h)}
 path=ROOT/"data/ai_coder_tasks.json"; payload=json.loads(path.read_text(encoding="utf-8")); tasks=[x for x in payload.get("tasks",[]) if x.get("task_id")!=new_id]
 tasks.append({"task_id":new_id,"origin":"store_policy_assessment","policy_task_id":a.task_id,"app_slug":source["app_slug"],"repository":repos.get(source["app_slug"],""),"status":"proposed","escalated_by":a.approver,"escalated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"approved_scope":scope,"allowed_paths":a.allowed_path,"finding":{"assessment":assessment,"policy_evidence":source.get("evidence",{})},"constraints":["Create a draft PR only; never merge, submit, or deploy.","Change only approved_scope and allowed_paths after reproducing or testing.","Do not modify billing, authentication, privacy, cryptography, database migrations, signing, or store metadata.","If the assessment concerns a restricted area, stop and report; do not patch."]})
 path.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"tasks":tasks},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"created proposed coder task {new_id}")
 return 0
if __name__=="__main__": raise SystemExit(main())
