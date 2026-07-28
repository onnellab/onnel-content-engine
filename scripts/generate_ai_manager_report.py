#!/usr/bin/env python3
"""Create a concise daily operations report without external AI/API calls."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name: str, default: object) -> object:
    path = ROOT / "data" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def load_reports(directory: str) -> list[dict]:
    path = ROOT / "data" / directory
    if not path.exists(): return []
    reports=[]
    for item in path.glob("*.json"):
        try:
            value=json.loads(item.read_text(encoding="utf-8"))
            if isinstance(value,dict): reports.append(value)
        except json.JSONDecodeError:
            continue
    return reports

def main() -> int:
    triage = load("store_review_triage.json", {"items": []})
    approvals = load("store_review_approvals.json", {"approvals": []})
    issues = load("review_issue_publications.json", {"items": []})
    doctor = load("ai_doctor_findings.json", {"findings": []})
    coder = load("ai_coder_tasks.json", {"tasks": []})
    os_updates = load("os_update_watchlist.json", {"sources": []})
    os_impacts = load("os_update_impact_tasks.json", {"tasks": []})
    policy_impacts = load("store_policy_impact_tasks.json", {"tasks": []})
    submissions = load("store_submission_readiness.json", {"records": []})
    internal_submissions = load("internal_store_submissions.json", {"submissions": []})
    internal_feedback = load("internal_test_feedback.json", {"feedback": []})
    internal_findings = load("internal_test_findings.json", {"findings": []})
    internal_results = load("internal_test_results.json", {"results": []})
    internal_readiness = load("internal_test_readiness.json", {"records": []})
    internal_availability = load("internal_test_availability.json", {"records": []})
    internal_processing = load("internal_store_processing_status.json", {"records": []})
    private_test_builds = load("private_test_build_requests.json", {"requests": []})
    private_test_orchestrations = load("private_test_orchestrations.json", {"orchestrations": []})
    policy_assessments = load("store_policy_assessments.json", {"assessments": []})
    release_candidates = load_reports("release-candidate-reports")
    ios_device_reports = load_reports("ios-device-qa-reports")
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
    coder_tasks = coder.get("tasks", []) if isinstance(coder, dict) else []
    policy_tasks = policy_impacts.get("tasks", []) if isinstance(policy_impacts, dict) else []
    failed_candidates = [item for item in release_candidates if any(item.get(key) == "failed" for key in ("pub_get", "static_analysis", "tests", "android_release_bundle", "ios_unsigned_release_build"))]
    stopped_ios = [item for item in ios_device_reports if item.get("status") in {"FAIL", "STOP"}]
    now = datetime.now(timezone.utc)
    uploaded_release_ids = {item.get("release_id") for item in internal_submissions.get("submissions", []) if item.get("status") == "uploaded"}
    android_artifacts = [item for item in private_test_builds.get("requests", []) if item.get("source") == "github_actions" and item.get("status") == "artifact_ready" and item.get("release_id") not in uploaded_release_ids]
    def expiry(item: dict) -> datetime | None:
        try:
            value=datetime.fromisoformat(item.get("artifact_expires_at", "")); return value if value.tzinfo else None
        except ValueError: return None
    expired_android = [item for item in android_artifacts if expiry(item) is None or expiry(item) <= now]
    expiring_android = [item for item in android_artifacts if expiry(item) is not None and now < expiry(item) <= now + timedelta(days=2)]
    failed_orchestrations = [item for item in private_test_orchestrations.get("orchestrations", []) if item.get("status") == "failed"]
    processing_records = internal_processing.get("records", []) if isinstance(internal_processing, dict) else []
    failed_processing = [item for item in processing_records if item.get("processing_status") == "failed"]
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": {"reviews_triaged": len(items), "high_risk_reports": len(high), "pricing_patterns": len(pricing), "replies_queued": sum(item.get("status") == "queued" for item in queued), "replies_published": sum(item.get("status") == "published" for item in queued), "issues_created": len(issue_items), "new_crash_incidents": sum(row.get("status") == "new" for row in crash_rows), "doctor_high_findings": sum(item.get("severity") in {"high", "critical"} for item in doctor.get("findings", [])), "coder_tasks_proposed": sum(item.get("status") == "proposed" for item in coder_tasks), "coder_draft_prs":sum(item.get("status") == "draft_pr_created" for item in coder_tasks), "policy_assessments_pending":sum(item.get("status") == "approved_for_assessment" for item in policy_tasks), "policy_assessment_failures":sum(item.get("status") == "FAIL" for item in policy_assessments.get("assessments", [])), "release_candidates_failed":len(failed_candidates), "ios_device_qa_blocked":len(stopped_ios), "os_updates_to_review": sum(item.get("status") == "changed" for item in os_updates.get("sources", [])), "os_impact_tasks":len(os_impacts.get("tasks", [])), "store_policy_tasks":len(policy_tasks), "store_submissions_blocked":sum(item.get("status") == "blocked" for item in submissions.get("records", [])), "internal_test_uploads":sum(item.get("status") == "uploaded" for item in internal_submissions.get("submissions", [])), "internal_store_processing":sum(item.get("processing_status") == "processing" for item in processing_records), "internal_store_processed":sum(item.get("processing_status") == "processed" for item in processing_records), "internal_store_processing_failed":len(failed_processing), "new_internal_test_feedback":sum(item.get("status") == "new" for item in internal_feedback.get("feedback", [])), "internal_test_high_findings":sum(item.get("severity") in {"high", "critical"} for item in internal_findings.get("findings", [])), "internal_test_passed":sum(item.get("status") == "passed" for item in internal_results.get("results", [])), "internal_test_failed":sum(item.get("status") == "failed" for item in internal_results.get("results", [])), "internal_test_ready_for_upload":sum(item.get("status") == "ready_for_internal_upload" for item in internal_readiness.get("records", [])), "internal_test_available_to_testers":sum(item.get("status") == "available_to_testers" for item in internal_availability.get("records", [])), "private_test_builds_dispatched":sum(item.get("status") == "dispatched" for item in private_test_builds.get("requests", [])), "private_test_builds_artifact_ready":sum(item.get("status") == "artifact_ready" for item in private_test_builds.get("requests", [])), "private_test_builds_failed":sum(item.get("status") == "failed" for item in private_test_builds.get("requests", [])), "private_test_orchestrations_active":sum(item.get("status") not in {"completed","failed"} for item in private_test_orchestrations.get("orchestrations", [])), "private_test_orchestrations_failed":sum(item.get("status") == "failed" for item in private_test_orchestrations.get("orchestrations", [])), "android_aab_expiring":len(expiring_android), "android_aab_expired":len(expired_android)},
        "requires_attention": ([{"review_id": item.get("review_id"), "category": item.get("category"), "actions": item.get("actions")} for item in high + pricing] + [{"task_id":item.get("task_id"),"category":"release_candidate_failed","actions":"inspect release-candidate-reports"} for item in failed_candidates] + [{"task_id":item.get("task_id"),"category":"ios_device_qa_blocked","actions":item.get("evidence")} for item in stopped_ios] + [{"finding_id":item.get("finding_id"),"category":"internal_test_high_finding","actions":item.get("recommended_actions")} for item in internal_findings.get("findings", []) if item.get("severity") in {"high", "critical"}] + [{"release_id":item.get("release_id"),"category":"internal_test_failed","actions":"create a new private-test build after remediation"} for item in internal_results.get("results", []) if item.get("status") == "failed"] + [{"release_id":item.get("release_id"),"category":"private_test_build_failed","actions":"inspect the GitHub Actions or Codemagic build before retrying"} for item in private_test_builds.get("requests", []) if item.get("status") == "failed"] + [{"release_id":item.get("release_id"),"category":"internal_store_processing_failed","actions":"inspect the official store processing state before another upload"} for item in failed_processing] + [{"release_id":item.get("release_id"),"category":"android_aab_expired","actions":"build a new Android private-test AAB"} for item in expired_android] + [{"release_id":item.get("release_id"),"category":"android_aab_expiring","actions":"run internal readiness and Play internal upload before expiration"} for item in expiring_android] + [{"orchestration_id":item.get("orchestration_id"),"category":"private_test_orchestration_failed","actions":item.get("failure")} for item in failed_orchestrations]),
    }
    output = ROOT / "data" / "ai_manager_daily_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {output}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
