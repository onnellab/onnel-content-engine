#!/usr/bin/env python3
"""Maintain an append-only approval record and publication queue for reviews.

This command never contacts App Store Connect or Google Play. A later publisher
may consume only records with status ``queued`` after credentials and an
independent deployment approval have been configured.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEWS = ROOT / "data" / "store_reviews.csv"
DEFAULT_APPROVALS = ROOT / "data" / "store_review_approvals.json"
BLOCKED_PROMISES = ("will be fixed", "next update", "guaranteed", "refund approved", "다음 업데이트", "고쳐드리", "환불해드리")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_reviews(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row.get("review_id", "").strip(): {key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)}


def read_approvals(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "updated_at": "", "approvals": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("approvals"), list):
        raise ValueError("approval file must contain an approvals list")
    return payload


def validate_reply(reply: str) -> str:
    value = " ".join(reply.split())
    if not value:
        raise ValueError("approved reply cannot be empty")
    if len(value) > 1000:
        raise ValueError("approved reply exceeds 1000 characters")
    if any(term in value.casefold() for term in BLOCKED_PROMISES):
        raise ValueError("approved reply contains a prohibited promise")
    return value


def approve_review(
    reviews: dict[str, dict[str, str]], payload: dict[str, object], review_id: str, reply: str, approver: str, note: str = ""
) -> dict[str, object]:
    review = reviews.get(review_id)
    if not review:
        raise ValueError(f"unknown review ID: {review_id}")
    if review.get("developer_reply") or review.get("status") == "replied":
        raise ValueError("a reply is already published for this review")
    clean_reply = validate_reply(reply)
    approvals = payload["approvals"]
    assert isinstance(approvals, list)
    if any(isinstance(item, dict) and item.get("review_id") == review_id and item.get("status") in {"queued", "published"} for item in approvals):
        raise ValueError("this review already has an active approval")
    record = {
        "approval_id": f"review-{review_id}", "review_id": review_id,
        "app_id": review.get("app_id", ""), "app_slug": review.get("app_slug", ""),
        "platform": review.get("platform", ""), "reply": clean_reply,
        "approved_at": now_iso(), "approved_by": approver.strip() or "manual_approver",
        "note": note.strip(), "status": "queued",
        "publication": {"attempts": 0, "published_at": "", "external_response_id": ""},
    }
    approvals.append(record)
    payload["updated_at"] = record["approved_at"]
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a human-approved review reply; never publishes")
    parser.add_argument("review_id")
    parser.add_argument("--reply", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    args = parser.parse_args()
    payload = read_approvals(args.approvals)
    record = approve_review(read_reviews(args.reviews), payload, args.review_id, args.reply, args.approver, args.note)
    args.approvals.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"queued {record['approval_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
