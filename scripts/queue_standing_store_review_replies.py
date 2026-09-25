#!/usr/bin/env python3
"""Queue owner-authorized scheduled store-review replies without publishing them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from store_review_approvals import (
    DEFAULT_APPROVALS,
    DEFAULT_REVIEWS,
    approve_review,
    now_iso,
    read_approvals,
    read_reviews,
)
from store_review_responses import generate_reply, review_text

APPROVER = "owner_standing_scheduled_policy_2026-09-24"
NOTE = (
    "Daily Ops standing authorization dated 2026-09-24; "
    "canonical repository reply template."
)


def eligible(review: dict[str, str]) -> bool:
    review_id = review.get("review_id", "").strip()
    return bool(
        review_id
        and not review_id.startswith("report-")
        and review.get("review_kind") != "rating_only"
        and review.get("status") == "pending"
        and not review.get("developer_reply")
        and review_text(review)
    )


def queue_replies(
    reviews: dict[str, dict[str, str]],
    payload: dict[str, object],
) -> tuple[list[dict[str, str]], bool]:
    approvals = payload.get("approvals", [])
    if not isinstance(approvals, list):
        raise ValueError("approval file must contain an approvals list")
    queued: list[dict[str, str]] = []
    changed = False

    for review_id in sorted(reviews):
        review = reviews[review_id]
        if not eligible(review):
            continue
        existing = next(
            (
                item
                for item in approvals
                if isinstance(item, dict) and item.get("review_id") == review_id
            ),
            None,
        )
        if isinstance(existing, dict):
            status = str(existing.get("status", ""))
            if status == "published":
                continue
            if status == "failed":
                existing["status"] = "queued"
                existing["retry_queued_at"] = now_iso()
                payload["updated_at"] = existing["retry_queued_at"]
                changed = True
            if existing.get("status") == "queued":
                queued.append({
                    "approval_id": str(existing.get("approval_id", "")),
                    "review_id": review_id,
                    "app_slug": str(existing.get("app_slug", "")),
                    "platform": str(existing.get("platform", "")),
                    "reply": str(existing.get("reply", "")),
                    "source": "existing_durable_record",
                })
            continue

        draft = generate_reply(review)
        reply = draft["suggested_reply"]
        if review.get("platform") == "android" and len(reply) > 350:
            raise ValueError(f"android standing reply exceeds publisher limit: {review_id}")
        record = approve_review(
            reviews,
            payload,
            review_id,
            reply,
            APPROVER,
            NOTE,
        )
        queued.append({
            "approval_id": str(record["approval_id"]),
            "review_id": review_id,
            "app_slug": str(record.get("app_slug", "")),
            "platform": str(record.get("platform", "")),
            "reply": str(record["reply"]),
            "source": "new_standing_approval",
        })
        changed = True

    return queued, changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    args = parser.parse_args()

    reviews = read_reviews(args.reviews)
    payload = read_approvals(args.approvals)
    queued, changed = queue_replies(reviews, payload)
    if changed:
        args.approvals.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": "queued" if queued else "idle",
        "changed": changed,
        "queued": queued,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
