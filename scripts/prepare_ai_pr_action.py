#!/usr/bin/env python3
"""Resolve one recorded AI-Coder Draft PR for a human rework/discard action."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PR_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    tasks = json.loads((ROOT / "data/ai_coder_tasks.json").read_text(encoding="utf-8")).get("tasks", [])
    task = next((item for item in tasks if item.get("task_id") == args.task_id), None)
    match = PR_URL.fullmatch(str(task.get("pr_url", ""))) if task else None
    if not task or task.get("status") != "draft_pr_created" or not match:
        raise SystemExit("task must have a recorded open Draft PR")
    if task.get("repository") != match.group(1):
        raise SystemExit("task repository and PR URL do not match")
    args.github_output.write_text(
        f"repository={match.group(1)}\npr_number={match.group(2)}\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
