#!/usr/bin/env python3
"""Normalize a Crashlytics/Sentry CSV export into AI-Scout crash incidents."""
from __future__ import annotations
import argparse, csv, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["incident_id","app_slug","platform","app_version","os_version","title","affected_users","event_count","first_seen","last_seen","source","status"]

def value(row: dict[str,str], *names: str) -> str:
    lower = {key.lower(): (val or "").strip() for key,val in row.items()}
    return next((lower.get(name.lower(), "") for name in names if lower.get(name.lower(), "")), "")

def main() -> int:
    parser = argparse.ArgumentParser(description="Import crash exports without external API credentials")
    parser.add_argument("input", type=Path); parser.add_argument("--app-slug", required=True); parser.add_argument("--source", choices=("crashlytics","sentry"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data/crash_incidents.csv")
    args = parser.parse_args()
    existing = []
    if args.output.exists():
        with args.output.open(encoding="utf-8", newline="") as handle: existing = list(csv.DictReader(handle))
    imported = []
    with args.input.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            title = value(row, "title", "issue", "exception", "exception title")
            version = value(row, "app_version", "release", "version")
            key = hashlib.sha256(f"{args.app_slug}|{title}|{version}".encode()).hexdigest()[:16]
            imported.append({"incident_id":key,"app_slug":args.app_slug,"platform":value(row,"platform"),"app_version":version,"os_version":value(row,"os_version","os"),"title":title,"affected_users":value(row,"affected_users","users"),"event_count":value(row,"event_count","events","count"),"first_seen":value(row,"first_seen"),"last_seen":value(row,"last_seen") or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"source":args.source,"status":"new"})
    merged = {row.get("incident_id",""):row for row in existing}; merged.update({row["incident_id"]:row for row in imported})
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer=csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(merged.values())
    print(f"imported {len(imported)} crash incidents")
    return 0
if __name__ == "__main__": raise SystemExit(main())
