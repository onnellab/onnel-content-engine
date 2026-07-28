#!/usr/bin/env python3
"""Record a human internal-test outcome; never promote or submit a release."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "internal_test_results.json"


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--outcome", choices=("pass", "fail"), required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.approver.strip() or not valid_url(args.evidence_url):
        raise SystemExit("approver and HTTPS evidence URL are required")
    uploads = json.loads((ROOT / "data" / "internal_store_submissions.json").read_text(encoding="utf-8")).get("submissions", [])
    if not any(item.get("release_id") == args.release_id and item.get("status") == "uploaded" for item in uploads):
        raise SystemExit("internal-test outcome requires a recorded successful upload")
    findings = json.loads((ROOT / "data" / "internal_test_findings.json").read_text(encoding="utf-8")).get("findings", [])
    blocking = [item for item in findings if item.get("internal_test_feedback", {}).get("release_id") == args.release_id and item.get("severity") in {"high", "critical"}]
    if args.outcome == "pass" and blocking:
        raise SystemExit("PASS is blocked by unresolved high/critical internal-test feedback")
    payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results = payload.get("results")
    if not isinstance(results, list):
        raise SystemExit("internal test results have invalid shape")
    if any(item.get("release_id") == args.release_id for item in results):
        raise SystemExit("release already has a recorded internal-test outcome")
    if not args.confirm:
        print(f"dry run: would record internal test {args.outcome} for {args.release_id}")
        return 0
    results.append({"release_id": args.release_id, "outcome": args.outcome, "status": "passed" if args.outcome == "pass" else "failed", "approved_by": args.approver.strip(), "evidence_url": args.evidence_url, "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    RESULTS_PATH.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded internal test {args.outcome} for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
