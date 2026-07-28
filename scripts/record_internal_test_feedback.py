#!/usr/bin/env python3
"""Record privacy-safe feedback for one successfully uploaded internal build."""
from __future__ import annotations

import argparse
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_PATH = ROOT / "data" / "internal_test_feedback.json"


def clean(value: str, limit: int, field: str) -> str:
    value = " ".join(value.split())
    if not value or len(value) > limit:
        raise SystemExit(f"{field} must contain 1 to {limit} characters")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--kind", choices=("crash", "data_loss", "security", "bug", "performance", "usability"), required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--reproduction", required=True)
    args = parser.parse_args()

    availability = json.loads((ROOT / "data" / "internal_test_availability.json").read_text(encoding="utf-8")).get("records", [])
    if not any(item.get("release_id") == args.release_id and item.get("status") == "available_to_testers" for item in availability):
        raise SystemExit("feedback requires a confirmed available-to-testers internal build")
    with (ROOT / "data" / "app_releases.csv").open(encoding="utf-8", newline="") as handle:
        release = next((row for row in csv.DictReader(handle) if row["release_id"] == args.release_id), None)
    if not release:
        raise SystemExit("release ID is unknown")
    payload = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    feedback = payload.get("feedback")
    if not isinstance(feedback, list):
        raise SystemExit("internal test feedback has invalid shape")
    feedback.append({
        "feedback_id": f"ITF-{uuid.uuid4().hex[:12]}",
        "release_id": args.release_id,
        "app_slug": release["app_slug"],
        "platform": release["platform"],
        "kind": args.kind,
        "summary": clean(args.summary, 500, "summary"),
        "reproduction": clean(args.reproduction, 1500, "reproduction"),
        "status": "new",
        "reported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    })
    FEEDBACK_PATH.write_text(json.dumps({"feedback": feedback}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded internal test feedback for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
