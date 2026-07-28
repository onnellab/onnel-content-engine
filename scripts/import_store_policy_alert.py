#!/usr/bin/env python3
"""Record a store-console warning without retaining account or user data."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STORES = {"google_play", "app_store"}
ALLOWED_KINDS = {"warning", "rejection", "deadline", "metadata", "privacy", "billing", "other"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import an evidence-only store policy alert")
    parser.add_argument("--store", required=True, choices=sorted(ALLOWED_STORES))
    parser.add_argument("--app-slug", required=True)
    parser.add_argument("--kind", required=True, choices=sorted(ALLOWED_KINDS))
    parser.add_argument("--summary", required=True, help="Sanitized alert summary; do not include account or customer data")
    parser.add_argument("--reference-url", default="")
    parser.add_argument("--occurred-at", default="")
    parser.add_argument("--output", type=Path, default=ROOT / "data/store_policy_alerts.json")
    args = parser.parse_args()
    summary = " ".join(args.summary.split())
    if not summary or len(summary) > 1000:
        parser.error("--summary must contain 1 to 1000 non-whitespace characters")
    if args.reference_url and not args.reference_url.startswith("https://"):
        parser.error("--reference-url must be an https URL")
    occurred_at = args.occurred_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError:
        parser.error("--occurred-at must be ISO-8601")
    payload = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {"alerts": []}
    alert_id = hashlib.sha256(f"{args.store}|{args.app_slug}|{args.kind}|{summary}|{occurred_at}".encode()).hexdigest()[:16]
    alert = {"alert_id": alert_id, "store": args.store, "app_slug": args.app_slug, "kind": args.kind,
             "summary": summary, "reference_url": args.reference_url, "occurred_at": occurred_at,
             "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "status": "new"}
    alerts = {item.get("alert_id"): item for item in payload.get("alerts", [])}
    alerts[alert_id] = alert
    args.output.write_text(json.dumps({"alerts": sorted(alerts.values(), key=lambda item: item["occurred_at"], reverse=True)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded store policy alert {alert_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
