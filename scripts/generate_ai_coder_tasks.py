#!/usr/bin/env python3
"""Turn approved AI-Doctor findings into constrained Codex bug-fix tasks."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    findings=json.loads((ROOT/"data/ai_doctor_findings.json").read_text(encoding="utf-8")).get("findings",[])
    internal_path=ROOT/"data/internal_test_findings.json"
    if internal_path.exists(): findings.extend(json.loads(internal_path.read_text(encoding="utf-8")).get("findings",[]))
    with (ROOT/"data/app_release_config.csv").open(encoding="utf-8",newline="") as handle: repos={row["app_slug"]:row["repository"] for row in csv.DictReader(handle)}
    path=ROOT/"data/ai_coder_tasks.json"
    previous=json.loads(path.read_text(encoding="utf-8")).get("tasks",[]) if path.exists() else []
    previous_by_id={task.get("task_id"):task for task in previous}
    tasks=[]
    for finding in findings:
        if not finding.get("github_issue_recommended"): continue
        slug=finding.get("app_slug","")
        task_id=finding.get("finding_id")
        task={"task_id":task_id,"app_slug":slug,"repository":repos.get(slug,""),"status":"proposed","finding":finding,"constraints":["Create a draft PR only; never merge or deploy.","Reproduce or add a failing test before changing production code.","Do not modify billing, authentication, privacy, cryptography, or database migrations.","Run the app repository's relevant tests and report results."]}
        existing=previous_by_id.get(task_id,{})
        if existing.get("status") in {"approved_for_draft_pr","draft_pr_created","merged","closed"}:
            task.update({key:value for key,value in existing.items() if key not in {"finding","app_slug","repository","constraints"}})
            task["finding"]=finding; task["app_slug"]=slug; task["repository"]=repos.get(slug,"")
        tasks.append(task)
    # Policy remediation tasks are human-created from a recorded FAIL assessment;
    # keep them intact when daily crash-derived tasks are regenerated.
    tasks.extend(task for task in previous if task.get("origin") == "store_policy_assessment" and task.get("task_id") not in {item.get("task_id") for item in tasks})
    output={"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"tasks":tasks}
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"generated {path}")
    return 0
if __name__=="__main__": raise SystemExit(main())
