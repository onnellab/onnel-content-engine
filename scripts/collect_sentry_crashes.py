#!/usr/bin/env python3
"""Collect unresolved Sentry issues into the normalized AI-Scout crash ledger."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["incident_id", "app_slug", "platform", "app_version", "os_version", "title", "affected_users", "event_count", "first_seen", "last_seen", "source", "status"]


def fetch(url: str, token: str) -> list[dict]:
    request = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Sentry request failed for {url}: {error}") from error
    if not isinstance(payload, list):
        raise RuntimeError("Sentry issues response was not a list")
    return payload


def main() -> int:
    config = json.loads((ROOT / "data/sentry_crash_sources.json").read_text(encoding="utf-8"))
    projects = config.get("projects", [])
    token = os.environ.get("SENTRY_AUTH_TOKEN", "")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status = {"checked_at": now, "configured_projects": len(projects), "connected": bool(token), "imported": 0, "state": "not_configured"}
    if not projects:
        (ROOT / "data/crash_sync_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        print("no Sentry projects configured")
        return 0
    if not token:
        status["state"] = "token_missing"
        (ROOT / "data/crash_sync_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        print("SENTRY_AUTH_TOKEN is not configured; no crash data collected")
        return 0
    existing_path = ROOT / "data/crash_incidents.csv"
    with existing_path.open(encoding="utf-8", newline="") as handle:
        incidents = {row["incident_id"]: row for row in csv.DictReader(handle)}
    for project in projects:
        required = ("app_slug", "organization", "project", "platform")
        if any(not project.get(key) for key in required):
            raise RuntimeError("every Sentry project needs app_slug, organization, project, and platform")
        url = f"https://sentry.io/api/0/projects/{project['organization']}/{project['project']}/issues/?query=is%3Aunresolved&sort=freq&limit=100"
        for issue in fetch(url, token):
            sentry_id = str(issue.get("id", ""))
            if not sentry_id:
                continue
            incident_id = hashlib.sha256(f"sentry|{project['app_slug']}|{sentry_id}".encode()).hexdigest()[:16]
            metadata = issue.get("metadata") if isinstance(issue.get("metadata"), dict) else {}
            release = issue.get("firstRelease") if isinstance(issue.get("firstRelease"), dict) else {}
            incidents[incident_id] = {"incident_id": incident_id, "app_slug": project["app_slug"], "platform": project["platform"],
                "app_version": str(release.get("version", "")), "os_version": "", "title": str(issue.get("title") or metadata.get("title") or "Sentry issue"),
                "affected_users": str(issue.get("userCount", 0)), "event_count": str(issue.get("count", 0)), "first_seen": str(issue.get("firstSeen", "")),
                "last_seen": str(issue.get("lastSeen", "")), "source": "sentry", "status": "new"}
            status["imported"] += 1
    with existing_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(incidents.values())
    status["state"] = "collected"
    (ROOT / "data/crash_sync_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"collected {status['imported']} Sentry issues")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
