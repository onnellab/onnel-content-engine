#!/usr/bin/env python3
"""Record the Draft PR created for one human-approved AI-Coder task."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    if not args.pr_url.startswith("https://github.com/"):
        parser.error("--pr-url must be a GitHub HTTPS PR URL")
    path = ROOT / "data/ai_coder_tasks.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    task = next((item for item in payload.get("tasks", []) if item.get("task_id") == args.task_id), None)
    if not task or task.get("status") != "approved_for_draft_pr":
        raise SystemExit("task must be approved_for_draft_pr")
    task.update({"status": "draft_pr_created", "branch": args.branch, "pr_url": args.pr_url,
                 "commit": args.commit, "draft_pr_created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded Draft PR for {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
