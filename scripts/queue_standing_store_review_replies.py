#!/usr/bin/env python3
"""Compatibility entrypoint: notify the owner; never queue or publish replies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from store_review_approvals import DEFAULT_APPROVALS, DEFAULT_REVIEWS, now_iso, read_approvals, read_reviews
from store_review_policy import POLICY_CHANGED_AT, require_owner_approval, require_owner_message_reference, review_fingerprint
from store_review_responses import review_text

DEFAULT_NOTIFICATIONS = DEFAULT_APPROVALS.with_name("store_review_notifications.json")


def eligible(review: dict[str, str]) -> bool:
    # Report-only text reviews still deserve an owner notification.
    return bool(review.get("review_id") and review.get("review_kind") != "rating_only"
                and review.get("status") == "pending" and not review.get("developer_reply")
                and review_text(review))


def queue_replies(reviews: dict, payload: dict) -> tuple[list, bool]:
    """Quarantine legacy records, preserve audit data, always return no replies."""
    approvals = payload.get("approvals")
    if not isinstance(approvals, list):
        raise ValueError("approval file must contain an approvals list")
    changed = False
    for record in approvals:
        if not isinstance(record, dict) or record.get("status") not in {"queued", "failed"}:
            continue
        try:
            require_owner_approval(record)
        except ValueError:
            record["previous_status"] = record["status"]
            record["status"] = "awaiting_owner_approval"
            record["approval_invalidated_at"] = now_iso()
            record["approval_invalidation_reason"] = "notify_first_owner_per_review_policy_2026-10-14"
            changed = True
    if changed:
        payload["updated_at"] = now_iso()
    # Even an explicit approval is never automatically consumed by this command.
    return [], changed


def prepare_notifications(reviews: dict, payload: dict) -> tuple[list, bool]:
    records = payload.get("notifications")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("notification file must contain a notifications object list")
    existing = {row.get("notification_id"): row for row in records}
    active_ids = set()
    changed = False
    for review in reviews.values():
        if not eligible(review):
            continue
        identity = "store-review-" + review_fingerprint(review)
        active_ids.add(identity)
        if identity in existing and existing[identity].get("status") == "superseded" and not existing[identity].get("delivery_reference"):
            existing[identity]["status"] = "pending"
            changed = True
        if identity not in existing:
            row = {key: review.get(key, "") for key in (
                "review_id", "app_id", "app_slug", "app_name", "platform", "rating",
                "title", "body", "created_at", "updated_at", "reviewer_language", "territory",
            )}
            row.update({"notification_id": identity, "status": "pending", "detected_at": now_iso(),
                        "delivery_reference": "", "owner_approval_required": True})
            records.append(row)
            changed = True
    for row in records:
        if row.get("status") == "pending" and row.get("notification_id") not in active_ids:
            row["status"] = "superseded"
            changed = True
    if changed:
        payload["updated_at"] = now_iso()
    return [row for row in records if row.get("status") == "pending"], changed


def acknowledge_notification(payload: dict, identity: str, reference: str) -> None:
    require_owner_message_reference("chatgpt", reference.strip())
    row = next((item for item in payload["notifications"] if item.get("notification_id") == identity), None)
    if row is None or row.get("status") not in {"pending", "notified"}:
        raise ValueError("a pending or already-notified notification ID is required")
    if row.get("status") == "notified":
        if row.get("delivery_reference") != reference.strip():
            raise ValueError("notification already has a different delivery receipt")
        return
    row.update({"status": "notified", "notified_at": now_iso(), "delivery_channel": "chatgpt", "delivery_reference": reference.strip()})
    payload["updated_at"] = now_iso()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    parser.add_argument("--notifications", type=Path, default=DEFAULT_NOTIFICATIONS)
    parser.add_argument("--ack-notification")
    parser.add_argument("--delivery-reference", default="")
    args = parser.parse_args()
    reviews = read_reviews(args.reviews)
    approvals = read_approvals(args.approvals)
    queued, approval_changed = queue_replies(reviews, approvals)
    notifications = json.loads(args.notifications.read_text()) if args.notifications.exists() else {
        "schema_version": 1, "policy_changed_at": POLICY_CHANGED_AT, "updated_at": "", "notifications": [],
    }
    pending, notification_changed = prepare_notifications(reviews, notifications)
    if args.ack_notification:
        acknowledge_notification(notifications, args.ack_notification, args.delivery_reference)
        notification_changed = True
        pending = [row for row in notifications["notifications"] if row.get("status") == "pending"]
    if approval_changed:
        args.approvals.write_text(json.dumps(approvals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if notification_changed:
        args.notifications.write_text(json.dumps(notifications, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "awaiting_owner_notification" if pending else "idle", "mode": "notify_only",
                      "changed": approval_changed or notification_changed, "queued": queued,
                      "notifications": pending, "notification_delivery": "owner_chat_only",
                      "publication_allowed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

