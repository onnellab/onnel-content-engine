#!/usr/bin/env python3
"""Normalize telemetry, review, and GitHub issue signals into AI-Doctor findings."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIGH_RISK = re.compile(r"\b(crash|data loss|security|corrupt|freeze|hang|실행.?종료|충돌|데이터.?손실)\b", re.I)


def load_json(name: str, default: dict) -> dict:
    path = ROOT / "data" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def preserved_diagnosis(previous: dict) -> dict:
    return {
        key: previous[key]
        for key in ("diagnosis_status", "diagnosis", "diagnosed_at")
        if key in previous
    }


def main() -> int:
    crash_path = ROOT / "data" / "crash_incidents.csv"
    if crash_path.exists():
        with crash_path.open(encoding="utf-8", newline="") as handle:
            crashes = list(csv.DictReader(handle))
    else:
        crashes = []
    triage = load_json("store_review_triage.json", {"items": []}).get("items", [])
    with (ROOT / "data" / "store_reviews.csv").open(encoding="utf-8", newline="") as handle:
        reviews = {row["review_id"]: row for row in csv.DictReader(handle)}
    previous = {
        item.get("finding_id"): item
        for item in load_json("ai_doctor_findings.json", {"findings": []}).get("findings", [])
    }
    findings: list[dict] = []
    for crash in crashes:
        related = []
        for item in triage:
            review = reviews.get(item.get("review_id", ""), {})
            if (
                review.get("app_slug") == crash.get("app_slug")
                and item.get("category") in {"bug", "data_loss", "security"}
                and (
                    not crash.get("app_version")
                    or not review.get("app_version")
                    or review.get("app_version") == crash.get("app_version")
                )
            ):
                related.append(item.get("review_id"))
        users = int(crash.get("affected_users", "0") or 0)
        severity = "critical" if users >= 100 else "high" if users >= 10 or related else "medium"
        finding_id = f"crash-{crash.get('incident_id', '')}"
        finding = {
            "finding_id": finding_id,
            "origin": "crash_telemetry",
            "app_slug": crash.get("app_slug"),
            "severity": severity,
            "crash": crash,
            "related_review_ids": related,
            "hypothesis": "Telemetry and user reports may describe the same defect; code evidence is required.",
            "recommended_actions": [
                "prepare a read-only app code context",
                "reproduce on the listed app and OS version",
                "inspect the source telemetry stack trace",
            ],
            "github_issue_recommended": severity in {"high", "critical"},
            "diagnosis_status": "pending",
        }
        finding.update(preserved_diagnosis(previous.get(finding_id, {})))
        findings.append(finding)
    for issue in load_json("github_issues.json", {"issues": []}).get("issues", []):
        if issue.get("status") != "open":
            continue
        labels = {str(label).lower() for label in issue.get("labels", [])}
        ai_fix_requested = "ai-fix" in labels
        high = ai_fix_requested or bool(labels & {"bug", "crash", "security", "data-loss", "data loss"}) or bool(
            HIGH_RISK.search(str(issue.get("title", "")))
        )
        finding_id = f"github-{issue.get('app_slug', '')}-{issue.get('number', '')}"
        finding = {
            "finding_id": finding_id,
            "origin": "github_issue",
            "app_slug": issue.get("app_slug"),
            "severity": "high" if high else "medium",
            "github_issue": issue,
            "related_review_ids": [],
            "hypothesis": "The issue title and labels identify a symptom; inspect code and recent changes before assigning a cause.",
            "recommended_actions": [
                "inspect the linked issue in GitHub",
                "prepare a read-only app code context",
                "reproduce before proposing a change",
            ],
            "github_issue_recommended": high,
            "ai_fix_requested": ai_fix_requested,
            "diagnosis_status": "pending",
        }
        finding.update(preserved_diagnosis(previous.get(finding_id, {})))
        findings.append(finding)
    correlated_review_ids = {
        review_id
        for finding in findings
        for review_id in finding.get("related_review_ids", [])
    }
    for item in triage:
        review_id = str(item.get("review_id", ""))
        review = reviews.get(review_id, {})
        actions = item.get("actions", {})
        if (
            not review_id
            or review_id in correlated_review_ids
            or not isinstance(actions, dict)
            or actions.get("code_change") != "investigate"
        ):
            continue
        category = str(item.get("category", ""))
        finding_id = f"review-{review_id}"
        finding = {
            "finding_id": finding_id,
            "origin": "store_review",
            "app_slug": review.get("app_slug"),
            "severity": "critical" if category in {"data_loss", "security"} else "high",
            "review": review,
            "related_review_ids": [review_id],
            "hypothesis": "A high-risk store review identifies a symptom; reproduction and code evidence are required.",
            "recommended_actions": [
                "prepare a read-only app code context",
                "reproduce on the reported app version when available",
                "correlate with telemetry when a crash source becomes available",
            ],
            "github_issue_recommended": True,
            "diagnosis_status": "pending",
        }
        finding.update(preserved_diagnosis(previous.get(finding_id, {})))
        findings.append(finding)
    output = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "findings": findings,
    }
    path = ROOT / "data" / "ai_doctor_findings.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
