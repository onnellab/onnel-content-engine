#!/usr/bin/env python3
"""Record human confirmation that an uploaded build is visible to testers."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "internal_test_availability.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--approver", required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    parsed = urlparse(args.evidence_url)
    if not args.approver.strip() or parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("approver and HTTPS console evidence URL are required")
    submissions = json.loads((ROOT / "data" / "internal_store_submissions.json").read_text(encoding="utf-8")).get("submissions", [])
    submission = next((item for item in submissions if item.get("release_id") == args.release_id and item.get("status") == "uploaded"), None)
    if not submission:
        raise SystemExit("availability confirmation requires a recorded successful internal upload")
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise SystemExit("internal test availability has invalid shape")
    if any(item.get("release_id") == args.release_id for item in records):
        raise SystemExit("release already has an internal test availability record")
    if not args.confirm:
        print(f"dry run: would confirm tester availability for {args.release_id}")
        return 0
    records.append({"release_id": args.release_id, "provider": submission["provider"], "channel": submission["channel"], "status": "available_to_testers", "confirmed_by": args.approver.strip(), "evidence_url": args.evidence_url, "confirmed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    PATH.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"confirmed tester availability for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
