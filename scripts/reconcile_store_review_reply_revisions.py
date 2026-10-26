#!/usr/bin/env python3
"""Reconcile an already-posted review edit from authenticated store-sync evidence.

This is a ledger-only verifier called by the existing Sync Store Reviews job.
It never contacts a store, sends a reply, creates an approval or retries a POST.
Uncertain edits remain unchanged unless the exact approved replacement is
observed by a newer, complete Google reviews.get snapshot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVISIONS = ROOT / "data/store_review_reply_revisions.json"
DEFAULT_REVIEWS = ROOT / "data/store_reviews.csv"
DEFAULT_STATUS = ROOT / "data/store_review_sync_status.json"
GOOGLE_REVIEW_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
GOOGLE_SOURCE = "google_reviews_get"
COMPLETE_SOURCE = "google_reviews_get_with_full_report_inventory"


def parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def reconcile(
    revisions_path: Path = DEFAULT_REVISIONS,
    reviews_path: Path = DEFAULT_REVIEWS,
    status_path: Path = DEFAULT_STATUS,
    *,
    now: datetime | None = None,
) -> int:
    """Return the count verified without modifying unchanged/uncertain entries."""
    ledger = json.loads(revisions_path.read_text(encoding="utf-8"))
    if ledger.get("schema_version") != 1 or not isinstance(ledger.get("requests"), list):
        raise ValueError("Invalid review-revision ledger")
    candidates = [r for r in ledger["requests"]
                  if isinstance(r, dict) and r.get("status") == "published_unverified"]
    if not candidates:
        return 0

    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("schema_version") != 1 or not isinstance(status.get("stores"), list):
        raise ValueError("Invalid store-review sync receipt")
    checked = parse_utc(status.get("checked_at"))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Reconciliation requires an aware UTC clock")
    current = current.astimezone(timezone.utc)
    if checked is None or not timedelta(0) <= current - checked <= timedelta(hours=24):
        return 0  # Stale or future receipts cannot establish a newly verified edit.

    snapshot = reviews_path.read_bytes()
    digest = hashlib.sha256(snapshot).hexdigest()
    if digest != status.get("snapshot_sha256"):
        return 0  # Never trust a CSV detached from its authenticated sync receipt.
    with reviews_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows_by_id: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        rows_by_id.setdefault(row.get("review_id", ""), []).append(row)
    verified_stores = {
        (store.get("app_id"), store.get("app_slug"), store.get("platform"))
        for store in status["stores"] if isinstance(store, dict)
        and store.get("state") == "verified"
        and store.get("source") == COMPLETE_SOURCE
        and parse_utc(store.get("checked_at")) == checked
    }

    changed = 0
    for record in candidates:
        publication = record.get("publication")
        if (not record.get("revision_id", "").startswith("revision-")
                or not GOOGLE_REVIEW_ID.fullmatch(str(record.get("review_id", "")))
                or record.get("platform") != "android"
                or not isinstance(publication, dict)
                or type(publication.get("attempts")) is not int
                or publication["attempts"] < 1
                or publication.get("approved_by") != "onnellab"
                or publication.get("approval_channel") != "github_owner_workflow_dispatch"
                or not re.fullmatch(r"[1-9][0-9]*", str(publication.get("workflow_run_id", "")))
                or str(publication.get("workflow_run_attempt")) != "1"):
            continue
        attempt = parse_utc(publication.get("last_attempt_at"))
        if attempt is None or checked < attempt:
            continue
        matching = rows_by_id.get(record["review_id"], [])
        if len(matching) != 1:
            continue
        row = matching[0]
        if (row.get("app_id"), row.get("app_slug"), row.get("platform")) not in verified_stores:
            continue
        verified_at = parse_utc(row.get("verified_at"))
        if (verified_at != checked or parse_utc(row.get("synced_at")) != checked
                or verified_at < attempt
                or row.get("verification_source") != GOOGLE_SOURCE
                or row.get("review_kind") != "review" or row.get("status") != "replied"
                or row.get("app_id") != record.get("app_id")
                or row.get("app_slug") != record.get("app_slug")
                or row.get("platform") != record.get("platform")
                or row.get("app_version") != record.get("app_version")
                or row.get("rating") != str(record.get("rating"))
                or row.get("title", "").strip() != record.get("expected_review_title")
                or row.get("body", "").strip() != record.get("expected_review_body")
                or not record.get("replacement_reply")
                or record.get("replacement_reply") == record.get("expected_current_reply")
                or row.get("developer_reply") != record.get("replacement_reply")):
            continue
        if publication.get("error"):
            publication.setdefault("previous_verification_error", publication["error"])
        record["status"] = "store_verified"
        publication["store_observed_at"] = row["verified_at"]
        publication["verification_source"] = GOOGLE_SOURCE
        publication["verification_snapshot_sha256"] = digest
        publication["error"] = ""
        record.pop("diagnostic", None)
        changed += 1

    if changed:
        ledger["updated_at"] = current.replace(microsecond=0).isoformat()
        revisions_path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = ""
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=revisions_path.parent,
                                             prefix=".review-revisions-", delete=False) as handle:
                temp_name = handle.name
                json.dump(ledger, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_name, revisions_path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revisions", type=Path, default=DEFAULT_REVISIONS)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--sync-status", type=Path, default=DEFAULT_STATUS)
    args = parser.parse_args()
    count = reconcile(args.revisions, args.reviews, args.sync_status)
    print(f"Store-observed existing reply revisions reconciled: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
