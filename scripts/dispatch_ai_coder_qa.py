#!/usr/bin/env python3
"""Dispatch the portable QA workflow for one newly recorded Draft PR."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    payload = json.loads((ROOT / "data" / "ai_coder_tasks.json").read_text(encoding="utf-8"))
    task = next((item for item in payload.get("tasks", []) if item.get("task_id") == args.task_id), None)
    if not task or task.get("status") != "draft_pr_created":
        raise SystemExit("task must have a recorded Draft PR")
    values = {
        "task_id": args.task_id,
        "repository": task.get("repository", ""),
        "ref": task.get("commit", ""),
        "pr_url": task.get("pr_url", ""),
        "confirm_qa": "QA",
    }
    if not all(values.values()):
        raise SystemExit("Draft PR audit record is incomplete")
    if not args.execute:
        print(f"dry run: would dispatch QA for {args.task_id}")
        return 0
    engine_repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not engine_repository:
        raise SystemExit("GITHUB_REPOSITORY is required")
    command = [
        "gh", "workflow", "run", "run-app-qa.yml",
        "--repo", engine_repository,
        "--ref", "main",
    ]
    for key, value in values.items():
        command.extend(["-f", f"{key}={value}"])
    subprocess.run(command, check=True)
    print(f"dispatched portable QA for {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
