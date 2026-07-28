#!/usr/bin/env python3
"""Correlate normalized crashes with review triage into AI-Doctor findings."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    crashes=[]
    crash_path=ROOT/"data/crash_incidents.csv"
    if crash_path.exists():
        with crash_path.open(encoding="utf-8",newline="") as handle: crashes=list(csv.DictReader(handle))
    triage=json.loads((ROOT/"data/store_review_triage.json").read_text(encoding="utf-8")).get("items",[])
    reviews={row["review_id"]:row for row in csv.DictReader((ROOT/"data/store_reviews.csv").open(encoding="utf-8",newline=""))}
    findings=[]
    for crash in crashes:
        related=[]
        for item in triage:
            review=reviews.get(item.get("review_id",""),{})
            if review.get("app_slug")==crash.get("app_slug") and item.get("category") in {"bug","data_loss","security"} and (not crash.get("app_version") or not review.get("app_version") or review.get("app_version")==crash.get("app_version")):
                related.append(item.get("review_id"))
        users=int(crash.get("affected_users","0") or 0)
        severity="critical" if users>=100 else "high" if users>=10 or related else "medium"
        findings.append({"finding_id":f"crash-{crash.get('incident_id','')}","app_slug":crash.get("app_slug"),"severity":severity,"crash":crash,"related_review_ids":related,"hypothesis":"Crash telemetry and user reports may describe the same defect; reproduce before assigning a root cause.","recommended_actions":["reproduce on listed app/OS version","inspect stack trace in source telemetry","create or link a GitHub issue"],"github_issue_recommended":severity in {"high","critical"}})
    output={"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"findings":findings}
    path=ROOT/"data/ai_doctor_findings.json"; path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"generated {path}")
    return 0
if __name__=="__main__": raise SystemExit(main())
