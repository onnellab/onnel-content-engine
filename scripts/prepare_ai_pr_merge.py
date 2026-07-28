#!/usr/bin/env python3
"""Resolve the only PR eligible for one human-approved AI-Coder merge."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT
PR_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    tasks = json.loads((ROOT / "data" / "ai_coder_tasks.json").read_text(encoding="utf-8")).get("tasks", [])
    task = next((item for item in tasks if item.get("task_id") == args.task_id), None)
    if not task or task.get("status") != "draft_pr_created":
        raise SystemExit("task must be an existing draft_pr_created Coder task")
    match = PR_URL.fullmatch(task.get("pr_url", ""))
    if not match or task.get("repository") != match.group(1):
        raise SystemExit("task repository and GitHub PR URL must match")
    report = ROOT / "data" / "qa-reports" / f"{args.task_id}.json"
    completed = subprocess.run([sys.executable, str(SCRIPT_ROOT / "scripts" / "validate_ai_qa_report.py"), str(report)], check=False, capture_output=True, text=True)
    if completed.returncode:
        raise SystemExit(f"QA report is not approved for human merge: {completed.stderr.strip() or completed.stdout.strip()}")
    args.github_output.write_text(f"repository={match.group(1)}\npr_number={match.group(2)}\n", encoding="utf-8")
    print(f"prepared approved merge for {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
