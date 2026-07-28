#!/usr/bin/env python3
"""Turn approved AI-Doctor findings into constrained Codex bug-fix tasks."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    findings=json.loads((ROOT/"data/ai_doctor_findings.json").read_text(encoding="utf-8")).get("findings",[])
    with (ROOT/"data/app_release_config.csv").open(encoding="utf-8",newline="") as handle: repos={row["app_slug"]:row["repository"] for row in csv.DictReader(handle)}
    tasks=[]
    for finding in findings:
        if not finding.get("github_issue_recommended"): continue
        slug=finding.get("app_slug","")
        tasks.append({"task_id":finding.get("finding_id"),"app_slug":slug,"repository":repos.get(slug,""),"status":"proposed","finding":finding,"constraints":["Create a draft PR only; never merge or deploy.","Reproduce or add a failing test before changing production code.","Do not modify billing, authentication, privacy, cryptography, or database migrations.","Run the app repository's relevant tests and report results."]})
    output={"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"tasks":tasks}
    path=ROOT/"data/ai_coder_tasks.json"; path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"generated {path}")
    return 0
if __name__=="__main__": raise SystemExit(main())
