#!/usr/bin/env python3
"""Require a matching successful no-upload preflight before store upload."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--provider", choices=("google_play", "app_store"), required=True)
    parser.add_argument("--identifier", required=True)
    parser.add_argument("--checksum-sha256", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{64}", args.checksum_sha256):
        raise SystemExit("checksum must be a 64-character lowercase SHA-256")
    records = json.loads((ROOT / "data" / "internal_test_readiness.json").read_text(encoding="utf-8")).get("records", [])
    if not any(item.get("release_id") == args.release_id and item.get("status") == "ready_for_internal_upload" and item.get("provider") == args.provider and item.get("identifier") == args.identifier and item.get("checksum_sha256") == args.checksum_sha256 for item in records):
        raise SystemExit("a matching Check Internal Test Readiness record is required before upload")
    print(f"matching internal test readiness confirmed for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
