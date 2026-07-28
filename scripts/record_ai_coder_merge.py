#!/usr/bin/env python3
"""Record a completed, human-approved merge against its exact Coder task."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--merge-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.merge_commit):
        raise SystemExit("merge commit must be a 40-character lowercase Git SHA")
    task_path = ROOT / "data" / "ai_coder_tasks.json"
    tasks_payload = json.loads(task_path.read_text(encoding="utf-8"))
    task = next((item for item in tasks_payload.get("tasks", []) if item.get("task_id") == args.task_id), None)
    expected_url = f"https://github.com/{args.repository}/pull/{args.pr_number}"
    if not task or task.get("status") != "draft_pr_created" or task.get("repository") != args.repository or task.get("pr_url") != expected_url:
        raise SystemExit("merge record does not match an eligible Coder task")
    merged_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    task.update({"status": "merged", "merged_by": args.approver, "merged_at": merged_at, "merge_commit": args.merge_commit})
    task_path.write_text(json.dumps(tasks_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    approval_path = ROOT / "data" / "ai_merge_approvals.json"
    payload = json.loads(approval_path.read_text(encoding="utf-8")) if approval_path.exists() else {"schema_version": 1, "items": []}
    items = payload.get("items")
    if not isinstance(items, list) or any(item.get("task_id") == args.task_id for item in items):
        raise SystemExit("merge approval audit is invalid or already recorded")
    items.append({"task_id": args.task_id, "repository": args.repository, "pr_number": args.pr_number, "merge_commit": args.merge_commit, "approved_by": args.approver, "merged_at": merged_at})
    approval_path.write_text(json.dumps({"schema_version": 1, "items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded merge for {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
