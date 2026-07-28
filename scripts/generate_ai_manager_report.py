#!/usr/bin/env python3
"""Create a concise daily operations report without external AI/API calls."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name: str, default: object) -> object:
    path = ROOT / "data" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def main() -> int:
    triage = load("store_review_triage.json", {"items": []})
    approvals = load("store_review_approvals.json", {"approvals": []})
    issues = load("review_issue_publications.json", {"items": []})
    doctor = load("ai_doctor_findings.json", {"findings": []})
    coder = load("ai_coder_tasks.json", {"tasks": []})
    os_updates = load("os_update_watchlist.json", {"sources": []})
    os_impacts = load("os_update_impact_tasks.json", {"tasks": []})
    crash_rows = []
    crash_path = ROOT / "data" / "crash_incidents.csv"
    if crash_path.exists():
        import csv
        with crash_path.open(encoding="utf-8", newline="") as handle: crash_rows = list(csv.DictReader(handle))
    items = triage.get("items", []) if isinstance(triage, dict) else []
    queued = approvals.get("approvals", []) if isinstance(approvals, dict) else []
    issue_items = issues.get("items", []) if isinstance(issues, dict) else []
    high = [item for item in items if item.get("category") in {"bug", "data_loss", "security"}]
    pricing = [item for item in items if item.get("category") == "pricing_confusion" and item.get("similar_reviews", 0) >= 3]
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": {"reviews_triaged": len(items), "high_risk_reports": len(high), "pricing_patterns": len(pricing), "replies_queued": sum(item.get("status") == "queued" for item in queued), "replies_published": sum(item.get("status") == "published" for item in queued), "issues_created": len(issue_items), "new_crash_incidents": sum(row.get("status") == "new" for row in crash_rows), "doctor_high_findings": sum(item.get("severity") in {"high", "critical"} for item in doctor.get("findings", [])), "coder_tasks_proposed": sum(item.get("status") == "proposed" for item in coder.get("tasks", [])), "os_updates_to_review": sum(item.get("status") == "changed" for item in os_updates.get("sources", [])), "os_impact_tasks":len(os_impacts.get("tasks", []))},
        "requires_attention": [{"review_id": item.get("review_id"), "category": item.get("category"), "actions": item.get("actions")} for item in high + pricing],
    }
    output = ROOT / "data" / "ai_manager_daily_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {output}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
