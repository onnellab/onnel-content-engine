#!/usr/bin/env python3
"""Create reproducibility-first findings from internal tester feedback."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    feedback = json.loads((ROOT / "data" / "internal_test_feedback.json").read_text(encoding="utf-8")).get("feedback", [])
    severity = {"security": "critical", "data_loss": "critical", "crash": "high", "bug": "medium", "performance": "medium", "usability": "low"}
    findings = []
    for item in feedback:
        if item.get("status") != "new":
            continue
        level = severity.get(item.get("kind"), "low")
        findings.append({
            "finding_id": f"internal-test-{item.get('feedback_id', '')}",
            "app_slug": item.get("app_slug", ""),
            "severity": level,
            "internal_test_feedback": item,
            "hypothesis": "A single internal-test report is unverified; reproduce the exact reported flow before assigning a root cause.",
            "recommended_actions": ["reproduce the recorded steps on the uploaded build", "preserve user data and do not request personal data", "create or link a GitHub issue only after reproduction"],
            "github_issue_recommended": level in {"high", "critical"},
        })
    output = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "findings": findings}
    path = ROOT / "data" / "internal_test_findings.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
