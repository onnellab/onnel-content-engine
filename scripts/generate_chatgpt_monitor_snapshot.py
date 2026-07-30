#!/usr/bin/env python3
"""Generate the privacy-minimized GitHub state consumed by ChatGPT Scheduled."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_ai_qa_report import PROFILE_CHECKS, REQUIRED, REQUIRED_CHECKS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(path: Path, default: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return value if isinstance(value, dict) else default


def load_qa_reports(root: Path) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    directory = root / "data/qa-reports"
    if not directory.exists():
        return reports
    for path in directory.glob("*.json"):
        report = load_json(path, {})
        if report.get("task_id"):
            reports[str(report["task_id"])] = report
    return reports


def notification_key(item: dict) -> str:
    material = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(material.encode()).hexdigest()[:20]


def qa_state(report: dict | None) -> str:
    if report is None:
        return "draft_pr_qa_pending"
    required = ("tests", "build", "static_analysis", "performance")
    if any(report.get(key) not in {"passed", "not_applicable_with_approval"} for key in required):
        return "draft_pr_qa_blocked"
    profile = report.get("qa_profile")
    checks = report.get("checks", [])
    names = {
        item.get("name")
        for item in checks
        if isinstance(item, dict) and item.get("status") == "PASS" and item.get("evidence")
    } if isinstance(checks, list) else set()
    required_checks = REQUIRED_CHECKS | PROFILE_CHECKS.get(profile, set())
    if (
        not any(not report.get(key) for key in REQUIRED)
        and profile in {"default", *PROFILE_CHECKS}
        and isinstance(checks, list)
        and checks
        and required_checks <= names
        and all(
            isinstance(item, dict)
            and item.get("status") == "PASS"
            and item.get("evidence")
            for item in checks
        )
    ):
        return "draft_pr_ready"
    return "draft_pr_qa_pending"


def build(root: Path = ROOT) -> dict:
    config = load_json(root / "data/chatgpt_monitor_config.json", {})
    tasks = load_json(root / "data/ai_coder_tasks.json", {"tasks": []}).get("tasks", [])
    reports = load_qa_reports(root)
    workflow_root = f"https://github.com/{config.get('repository', '')}/actions/workflows"
    items: list[dict] = []
    for task in tasks if isinstance(tasks, list) else []:
        status = task.get("status")
        if status == "approved_for_draft_pr":
            state = "coder_execution_pending"
        elif status == "draft_pr_created":
            state = qa_state(reports.get(str(task.get("task_id"))))
        else:
            continue
        if state not in config.get("notify_states", []):
            continue
        report = reports.get(str(task.get("task_id")), {})
        item = {
            "task_id": task.get("task_id"),
            "app_slug": task.get("app_slug"),
            "repository": task.get("repository"),
            "state": state,
            "risk_class": task.get("risk_class"),
            "pr_url": task.get("pr_url", ""),
            "commit": task.get("commit", ""),
            "checks": {
                "verification": task.get("verification", {}).get("status", "pending"),
                "security_scan": task.get("security_scan", "pending"),
                "tests": report.get("tests", "pending"),
                "build": report.get("build", "pending"),
                "static_analysis": report.get("static_analysis", "pending"),
                "performance": report.get("performance", "pending"),
            },
            "action_urls": {
                "approve": f"{workflow_root}/approve-ai-coder-task.yml",
                "merge": f"{workflow_root}/merge-approved-app-pr.yml",
                "rework": f"{workflow_root}/rework-ai-coder-task.yml",
                "discard": f"{workflow_root}/discard-ai-coder-task.yml",
            },
        }
        if item["pr_url"]:
            item["action_urls"]["view_pr"] = item["pr_url"]
        item["notification_key"] = notification_key(item)
        items.append(item)
    items.sort(key=lambda item: (str(item.get("app_slug", "")), str(item.get("task_id", ""))))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository": config.get("repository"),
        "schedule": config.get("schedule"),
        "lookback_hours": config.get("lookback_hours", 2),
        "source_of_truth": "GitHub task ledger, QA reports, Draft PRs, and Actions runs",
        "items": items,
    }


def main() -> int:
    output = DATA / "chatgpt_monitor_snapshot.json"
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
