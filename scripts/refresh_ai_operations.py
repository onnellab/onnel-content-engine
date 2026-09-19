#!/usr/bin/env python3
"""Run the local AI operations refresh in a bounded, audit-only sequence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "data/ai_operations_refresh_status.json"
STEPS = (
    "check_store_versions.py", "sync_store_reviews.py", "collect_github_issues.py",
    "collect_os_updates.py", "collect_store_policy_updates.py",
    "collect_gmail_policy_alerts.py", "collect_gmail_policy_alerts.py",
    "validate_crash_source_config.py", "collect_sentry_crashes.py",
    "collect_crashlytics_incidents.py", "collect_codemagic_private_test_builds.py",
    "collect_internal_store_processing_status.py", "triage_store_reviews.py",
    "analyze_incidents.py", "analyze_internal_test_feedback.py",
    "generate_ai_coder_tasks.py", "analyze_os_update_impact.py",
    "analyze_store_policy_impact.py", "evaluate_store_submission_readiness.py",
    "generate_ai_manager_report.py", "generate_chatgpt_monitor_snapshot.py",
)
MANUAL_LEDGER_PATHS = (
    "data/store_review_approvals.json", "data/store_submission_approvals.json",
    "data/ai_doctor_findings.json", "data/ai_coder_tasks.json",
    "data/internal_test_feedback.json", "data/internal_test_findings.json",
    "data/internal_test_results.json", "data/internal_test_readiness.json",
    "data/internal_test_availability.json", "data/internal_store_submissions.json",
    "data/private_test_orchestrations.json", "data/ios-device-qa-reports",
    "data/review_issue_publications.json", "data/store_policy_assessments.json",
    "data/qa-reports", "data/release-candidate-reports",
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_file(root: Path, relative: str) -> object:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def required_json(root: Path, relative: str) -> tuple[dict, bool]:
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
        return (value, isinstance(value, dict))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}, False


def semantic_status(script: str, root: Path) -> str:
    required: dict[str, str] = {
        "collect_os_updates.py": "data/os_update_watchlist.json",
        "collect_store_policy_updates.py": "data/store_policy_watchlist.json",
        "collect_github_issues.py": "data/github_issue_sync_status.json",
        "sync_store_reviews.py": "data/store_review_sync_status.json",
        "collect_sentry_crashes.py": "data/crash_sync_status.json",
        "collect_crashlytics_incidents.py": "data/crashlytics_sync_status.json",
        "collect_codemagic_private_test_builds.py": "data/private_test_build_sync_status.json",
    }
    if script in required:
        _, valid = required_json(root, required[script])
        if not valid:
            return "unavailable"
    if script == "collect_os_updates.py":
        value = json_file(root, "data/os_update_watchlist.json")
        return "failed" if any(item.get("status") == "failed" for item in value.get("sources", [])) else "ok"
    if script == "collect_store_policy_updates.py":
        value = json_file(root, "data/store_policy_watchlist.json")
        return "failed" if any(item.get("status") == "failed" for item in value.get("sources", [])) else "ok"
    if script == "collect_github_issues.py":
        state = json_file(root, "data/github_issue_sync_status.json").get("state")
        return "unavailable" if state in {"failed", "not_connected", "token_missing"} else "ok"
    if script == "sync_store_reviews.py":
        states = [item.get("state") for item in json_file(root, "data/store_review_sync_status.json").get("stores", [])]
        return "unavailable" if states and any(state not in {"verified", "not_released", "not_applicable", "disabled"} for state in states) else "ok"
    if script in {"collect_sentry_crashes.py", "collect_crashlytics_incidents.py"}:
        status_file = "data/crash_sync_status.json" if script.startswith("collect_sentry") else "data/crashlytics_sync_status.json"
        state = json_file(root, status_file).get("state")
        return "unavailable" if state in {"failed", "token_missing"} else "ok"
    if script == "check_store_versions.py":
        try:
            import csv
            with (root / "data/store_versions.csv").open(encoding="utf-8", newline="") as handle:
                return "failed" if any(row.get("status") in {"failed", "manual_check"} for row in csv.DictReader(handle)) else "ok"
        except (FileNotFoundError, OSError, csv.Error):
            return "unavailable"
    if script == "collect_codemagic_private_test_builds.py":
        state = json_file(root, "data/private_test_build_sync_status.json")
        records = state.get("records", [])
        return "unavailable" if state.get("state") == "token_missing" else "failed" if any(item.get("status") == "unknown" for item in records) else "ok"
    return "ok"


def ledger(root: Path) -> list[dict[str, object]]:
    result = []
    for relative in MANUAL_LEDGER_PATHS:
        path = root / relative
        paths = sorted(path.rglob("*") if path.is_dir() else ([path] if path.exists() else []))
        digest = hashlib.sha256()
        count = 0
        for item in paths:
            if not item.is_file():
                continue
            count += 1
            digest.update(str(item.relative_to(root)).encode())
            digest.update(item.read_bytes())
        result.append({"path": relative, "count": count, "sha256": digest.hexdigest(), "status": "recorded_only"})
    return result


def run_refresh(root: Path = ROOT, runner: Callable = subprocess.run) -> int:
    steps: list[dict[str, object]] = []
    overall = "complete"
    for index, script in enumerate(STEPS):
        if script == "generate_ai_manager_report.py":
            steps.append({"script": script, "checked_at": now(), "exit_code": None, "status": "pending"})
            continue
        account = ""
        env = dict(os.environ)
        args: list[str] = []
        if script == "collect_gmail_policy_alerts.py":
            account = "developer" if index == 5 else "official"
            token = env.get(f"GMAIL_POLICY_REFRESH_{account.upper()}", "")
            if not token:
                steps.append({"script": script, "account": account, "checked_at": now(), "exit_code": None, "status": "unavailable"})
                overall = "partial"
                continue
            env["GMAIL_ACCOUNT_ALIAS"] = account
            env["GMAIL_REFRESH_TOKEN"] = token
        if script == "collect_codemagic_private_test_builds.py":
            requests = json_file(root, "data/private_test_build_requests.json").get("requests", [])
            if not requests:
                steps.append({"script": script, "checked_at": now(), "exit_code": 0, "status": "not_applicable"})
                continue
        started = now()
        try:
            completed = runner([sys.executable, str(root / "scripts" / script), *args], cwd=root, env=env, capture_output=True, text=True, timeout=180)
            exit_code = completed.returncode
            status = "failed" if exit_code else semantic_status(script, root)
        except (OSError, subprocess.TimeoutExpired):
            exit_code, status = 1, "failed"
        if status in {"failed", "unavailable"}:
            overall = "partial"
        entry: dict[str, object] = {"script": script, "checked_at": started, "exit_code": exit_code, "status": status}
        if account:
            entry["account"] = account
        steps.append(entry)
    manager = next(item for item in steps if item["script"] == "generate_ai_manager_report.py")
    status_path = root / "data/ai_operations_refresh_status.json"
    root.joinpath("data").mkdir(parents=True, exist_ok=True)
    def write_status() -> None:
        payload = {"generated_at": now(), "checked_at": now(), "status": overall, "steps": steps, "manual_ledgers": ledger(root)}
        status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_status()
    try:
        completed = runner([sys.executable, str(root / "scripts/generate_ai_manager_report.py")], cwd=root, env=dict(os.environ), capture_output=True, text=True, timeout=180)
        manager["exit_code"] = completed.returncode
        manager["status"] = "failed" if completed.returncode else "ok"
    except (OSError, subprocess.TimeoutExpired):
        manager["exit_code"], manager["status"] = 1, "failed"
    if manager["status"] == "failed":
        overall = "partial"
    write_status()
    # Re-render once so the report embeds the finalized refresh status.
    try:
        rendered = runner([sys.executable, str(root / "scripts/generate_ai_manager_report.py")], cwd=root, env=dict(os.environ), capture_output=True, text=True, timeout=180)
        render_exit = rendered.returncode
    except (OSError, subprocess.TimeoutExpired):
        render_exit = 1
    if render_exit:
        manager["exit_code"], manager["status"] = render_exit, "failed"
        overall = "partial"
        write_status()
    return 1 if overall == "partial" else 0


if __name__ == "__main__":
    raise SystemExit(run_refresh())
