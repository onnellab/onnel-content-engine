#!/usr/bin/env python3
"""Validate and record a read-only store-policy assessment."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 parser=argparse.ArgumentParser(); parser.add_argument("task_id"); parser.add_argument("assessment",type=Path); args=parser.parse_args()
 data=json.loads(args.assessment.read_text(encoding="utf-8"))
 if not isinstance(data,dict) or data.get("task_id")!=args.task_id or data.get("status") not in {"PASS","FAIL","STOP"} or data.get("patch_authorized") is not False or not isinstance(data.get("evidence"),list) or not data["evidence"] or not isinstance(data.get("conclusion"),str) or not data["conclusion"].strip(): raise SystemExit("invalid assessment: task_id, status, evidence, conclusion, and patch_authorized:false are required")
 if any(not isinstance(item,dict) or not item.get("reference") for item in data["evidence"]): raise SystemExit("each evidence item needs a reference")
 task_path=ROOT/"data/store_policy_impact_tasks.json"; tasks=json.loads(task_path.read_text(encoding="utf-8")); task=next((item for item in tasks.get("tasks",[]) if item.get("task_id")==args.task_id),None)
 if not task or task.get("status")!="approved_for_assessment": raise SystemExit("task must be approved_for_assessment")
 data["recorded_at"]=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); data["patch_authorized"]=False
 output=ROOT/"data/store_policy_assessments.json"; payload=json.loads(output.read_text(encoding="utf-8")); rows=[item for item in payload.get("assessments",[]) if item.get("task_id")!=args.task_id]; rows.append(data); output.write_text(json.dumps({"assessments":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 task.update({"status":"assessment_complete","assessment_status":data["status"],"assessment_recorded_at":data["recorded_at"]}); task_path.write_text(json.dumps(tasks,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"recorded policy assessment {args.task_id}")
 return 0
if __name__=="__main__": raise SystemExit(main())
