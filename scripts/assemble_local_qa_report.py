#!/usr/bin/env python3
"""Assemble local command results and review evidence without invoking a model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_ai_qa_report import PROFILE_CHECKS, REQUIRED_CHECKS


def assemble(packet: dict, review: dict | None = None) -> dict:
    task = packet["task"]
    identity = {key: task[key] for key in ("task_id", "repository", "pr_url", "commit")}
    identity["qa_profile"] = packet["qa_profile"]
    if identity["qa_profile"] not in {"default", *PROFILE_CHECKS}:
        raise ValueError("unsupported QA profile")
    if review is not None:
        if not isinstance(review, dict):
            raise ValueError("review report must be a JSON object")
        for key, expected in identity.items():
            if review.get(key) != expected:
                raise ValueError(f"review report {key} does not match the prepared packet")
    report = dict(review or {})
    report.update(identity)
    checks = report.get("checks", [])
    if not isinstance(checks, list):
        raise ValueError("review checks must be a list")
    by_name = {}
    for item in checks:
        if (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                or not item["name"] or item["name"] in by_name
                or item.get("status") not in {"PASS", "FAIL", "STOP"}
                or not isinstance(item.get("evidence"), str) or not item["evidence"].strip()):
            raise ValueError("review checks require unique names, valid status, and evidence")
        by_name[item["name"]] = dict(item)
    required = REQUIRED_CHECKS | PROFILE_CHECKS.get(identity["qa_profile"], set())
    for name in sorted(required - by_name.keys()):
        by_name[name] = {
            "name": name, "status": "STOP", "severity": "HIGH",
            "evidence": "No separately reviewed evidence was supplied for this check.",
        }
    if packet.get("ios_device_required"):
        device = packet.get("ios_device_report")
        device_pass = (isinstance(device, dict) and device.get("status") == "PASS"
                       and device.get("task_id") == identity["task_id"]
                       and device.get("commit") == identity["commit"]
                       and bool(device.get("device_id")) and bool(device.get("evidence")))
        if not device_pass and by_name["ios_device_risk"]["status"] != "FAIL":
            by_name["ios_device_risk"].update(
                status="STOP", severity="HIGH",
                evidence="No commit-bound physical-iOS-device PASS report; local checks cannot replace it.",
            )
    if packet.get("source_integrity") != "passed":
        check = by_name["recent_change_compliance"]
        if check["status"] != "FAIL":
            check.update(status="STOP", severity="HIGH",
                         evidence="App HEAD or worktree changed during local verification.")
    # Local exit codes are authoritative, even when a supplied review says PASS.
    command_results = packet["command_results"]
    for field, command in (("tests", "flutter_test"), ("static_analysis", "flutter_analyze"),
                           ("performance", "performance")):
        value = command_results.get(command)
        if value not in {"passed", "failed", "not_configured"}:
            raise ValueError(f"missing or invalid local result: {command}")
        report[field] = value
    report.setdefault("build", "not_run")
    report.setdefault("risk", "Unverified until the required review evidence is supplied.")
    report.setdefault("rollback", "Rollback has not been reviewed.")
    report["checks"] = list(by_name.values())
    report["command_results"] = dict(command_results)
    report["command_exit_codes"] = dict(packet["command_exit_codes"])
    report["verification_method"] = "free_local_commands_and_supplied_review"
    report["review_evidence_supplied"] = review is not None
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--review-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        review_bytes = args.review_report.read_bytes() if args.review_report else None
        review = json.loads(review_bytes) if review_bytes is not None else None
        if review_bytes is not None and not isinstance(review, dict):
            raise ValueError("review report must be a JSON object")
        report = assemble(packet, review)
        report["review_evidence_sha256"] = (
            hashlib.sha256(review_bytes).hexdigest() if review_bytes is not None else None
        )
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Local QA report is unverified: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
