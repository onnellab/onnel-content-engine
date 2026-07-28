#!/usr/bin/env python3
"""Store a successful no-upload internal-test readiness check."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "internal_test_readiness.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--provider", choices=("google_play", "app_store"), required=True)
    parser.add_argument("--identifier", required=True)
    parser.add_argument("--checksum-sha256", required=True)
    parser.add_argument("--run-url", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{64}", args.checksum_sha256):
        raise SystemExit("checksum must be a 64-character lowercase SHA-256")
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise SystemExit("internal test readiness has invalid shape")
    record = {"release_id": args.release_id, "provider": args.provider, "identifier": args.identifier, "checksum_sha256": args.checksum_sha256, "status": "ready_for_internal_upload", "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "workflow_run_url": args.run_url}
    records = [item for item in records if item.get("release_id") != args.release_id]
    records.append(record)
    PATH.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded internal test readiness for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
