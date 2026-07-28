#!/usr/bin/env python3
"""Validate a QA report before a Codex draft PR can request human approval."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=("task_id","repository","pr_url","tests","build","static_analysis","risk","rollback")
def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("report",type=Path); args=parser.parse_args()
    try: report=json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as error: print(error,file=sys.stderr); return 1
    missing=[key for key in REQUIRED if not report.get(key)]
    failed=[key for key in ("tests","build","static_analysis") if report.get(key) not in {"passed","not_applicable_with_approval"}]
    if missing or failed:
        print(json.dumps({"approved_for_human_review":False,"missing":missing,"failed":failed}),file=sys.stderr); return 1
    print(json.dumps({"approved_for_human_review":True,"task_id":report["task_id"]})); return 0
if __name__=="__main__": raise SystemExit(main())
