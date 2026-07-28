#!/usr/bin/env python3
"""Persist a successful internal-only store upload without contacting a store."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "internal_store_submissions.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--provider", choices=("google_play", "app_store"), required=True)
    parser.add_argument("--identifier", required=True)
    parser.add_argument("--run-url", required=True)
    args = parser.parse_args()

    payload = json.loads(PATH.read_text(encoding="utf-8"))
    submissions = payload.get("submissions")
    if not isinstance(submissions, list):
        raise SystemExit("internal store submission audit has invalid shape")
    if any(item.get("release_id") == args.release_id for item in submissions):
        raise SystemExit("release already has an internal store submission audit record")
    submissions.append(
        {
            "release_id": args.release_id,
            "provider": args.provider,
            "identifier": args.identifier,
            "channel": "internal" if args.provider == "google_play" else "testflight",
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "workflow_run_url": args.run_url,
        }
    )
    PATH.write_text(json.dumps({"submissions": submissions}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded internal {args.provider} upload for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
