#!/usr/bin/env python3
"""Dispatch human-labeled, diagnosed GREEN GitHub issues to the Coder approval gate."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from ai_coder_task_contract import contract_errors

ROOT = Path(__file__).resolve().parents[1]


def eligible(task: dict) -> bool:
    issue = task.get("finding", {}).get("github_issue", {})
    labels = {str(label).strip().lower() for label in issue.get("labels", [])}
    return (
        task.get("status") == "proposed"
        and task.get("intake_status") == "ready"
        and task.get("risk_class") == "GREEN"
        and "ai-fix" in labels
        and not contract_errors(task)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repository = os.environ.get("GITHUB_REPOSITORY", "onnellab/onnel-content-engine")
    tasks = json.loads((ROOT / "data/ai_coder_tasks.json").read_text(encoding="utf-8")).get("tasks", [])
    selected = [task for task in tasks if eligible(task)]
    for task in selected:
        command = [
            "gh", "workflow", "run", "approve-ai-coder-task.yml",
            "--repo", repository,
            "--ref", "main",
            "-f", f"task_id={task['task_id']}",
            "-f", "approver=github-ai-fix-label",
            "-f", "confirm=APPROVE",
            "-f", "approve_yellow_plan=false",
        ]
        if args.execute:
            subprocess.run(command, check=True)
            print(f"dispatched ai-fix GREEN task {task['task_id']}")
        else:
            print(f"dry run: would dispatch ai-fix GREEN task {task['task_id']}")
    if not selected:
        print("no eligible ai-fix GREEN tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
