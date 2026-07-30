#!/usr/bin/env python3
"""Record a human decision to rework or discard an AI-Coder Draft PR."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--action", choices=("rework", "discard"), required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if not args.actor.strip() or not args.reason.strip():
        raise SystemExit("actor and reason are required")
    path = ROOT / "data/ai_coder_tasks.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    task = next((item for item in payload.get("tasks", []) if item.get("task_id") == args.task_id), None)
    if not task or task.get("status") != "draft_pr_created":
        raise SystemExit("task must have a recorded Draft PR")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    history = task.setdefault("pr_action_history", [])
    history.append(
        {
            "action": args.action,
            "actor": args.actor.strip(),
            "reason": args.reason.strip(),
            "pr_url": task.get("pr_url"),
            "commit": task.get("commit"),
            "recorded_at": now,
        }
    )
    if args.action == "rework":
        task["status"] = "proposed"
        task["attempt"] = int(task.get("attempt", 1)) + 1
        for key in (
            "approved_by", "approved_at", "plan_approved_at", "branch", "pr_url", "commit",
            "security_scan", "verification", "draft_pr_created_at",
        ):
            task.pop(key, None)
    else:
        task.update({"status": "closed", "closed_by": args.actor.strip(), "closed_at": now})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {args.action} for {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
