#!/usr/bin/env python3
"""Validate a QA report before a Codex draft PR can request human approval."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=("task_id","repository","pr_url","qa_profile","tests","build","static_analysis","performance","risk","rollback")
REQUIRED_CHECKS={"critical_safety","recent_change_compliance","ios_device_risk","side_effects","whole_change_release_gate","unused_code","objective_quality","user_flow","final_release_gate","mobile_device_risk","platform_audit"}
PROFILE_CHECKS={
    "flutter_riverpod_firestore_autosave_v1": {
        "architecture_state_boundary",
        "riverpod_listener_lifecycle",
        "autosave_flush_integrity",
        "resource_disposal",
        "firestore_query_index",
        "firestore_security_rules",
        "quiet_sync_ux",
        "localization_tone",
    }
}
def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("report",type=Path); args=parser.parse_args()
    try: report=json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as error: print(error,file=sys.stderr); return 1
    missing=[key for key in REQUIRED if not report.get(key)]
    failed=[key for key in ("tests","build","static_analysis","performance") if report.get(key) not in {"passed","not_applicable_with_approval"}]
    invalid_profile=[] if report.get("qa_profile") in {"default", *PROFILE_CHECKS} else [report.get("qa_profile")]
    checks=report.get("checks",[])
    names={item.get("name") for item in checks if isinstance(item,dict)} if isinstance(checks,list) else set()
    invalid=[item.get("name","unknown") for item in checks if not isinstance(item,dict) or item.get("status") not in {"PASS","FAIL","STOP"} or not item.get("evidence")] if isinstance(checks,list) else ["checks"]
    required_checks=REQUIRED_CHECKS | PROFILE_CHECKS.get(report.get("qa_profile"), set())
    missing_checks=sorted(required_checks-names)
    failed_checks=[item.get("name","unknown") for item in checks if isinstance(item,dict) and item.get("status") != "PASS"] if isinstance(checks,list) else []
    if missing or failed or invalid_profile or invalid or missing_checks or failed_checks:
        print(json.dumps({"approved_for_human_review":False,"missing":missing,"failed":failed,"invalid_profile":invalid_profile,"invalid_checks":invalid,"missing_checks":missing_checks,"failed_checks":failed_checks}),file=sys.stderr); return 1
    print(json.dumps({"approved_for_human_review":True,"task_id":report["task_id"]})); return 0
if __name__=="__main__": raise SystemExit(main())
