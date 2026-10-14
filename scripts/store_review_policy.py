"""Fail-closed owner-per-review approval policy, effective 2026-10-14."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

POLICY_CHANGED_AT = "2026-10-14T06:14:53+00:00"
APPROVAL_TYPE = "explicit_owner_per_review_v1"
REVIEW_FIELDS = ("review_id", "app_id", "platform", "title", "body", "rating", "updated_at")
APPROVAL_FIELDS = (
    "approval_type", "review_id", "app_id", "platform", "reply", "approved_at",
    "approved_by", "approval_channel", "approval_reference", "review_content_sha256",
)


def fingerprint(values: list[str]) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def review_fingerprint(review: dict) -> str:
    return fingerprint([str(review.get(key, "")) for key in REVIEW_FIELDS])


def approval_fingerprint(record: dict) -> str:
    return fingerprint([str(record.get(key, "")) for key in APPROVAL_FIELDS])


def require_owner_message_reference(channel: str, reference: str) -> None:
    # A syntactically valid ID is not proof: the caller must verify the exact
    # owner-chat message with the channel tool before writing this receipt.
    if channel != "chatgpt" or not re.fullmatch(r"(?:[A-Za-z0-9_-]+~[A-Za-z0-9_-]+~CalpicoMessage~)?Sentinel_[0-9a-f]{32}", reference):
        raise ValueError("a verified owner chatgpt message reference is required")


def require_owner_approval(record: dict, review: dict | None = None) -> None:
    """Evidence is an owner message/confirmation reference, never a draft or policy.

    The caller must have actually verified that reference. This local binding
    detects stale/tampered scope; it does not authenticate arbitrary input.
    """
    if record.get("approval_type") != APPROVAL_TYPE:
        raise ValueError("explicit per-review owner approval is required; standing/legacy approvals are invalid")
    if record.get("status") != "queued":
        raise ValueError("owner approval must be queued")
    actor = str(record.get("approved_by", "")).strip()
    reference = str(record.get("approval_reference", "")).strip()
    if not actor or any(word in actor.casefold() for word in ("standing", "automatic", "generated")):
        raise ValueError("an explicit owner approval actor is required")
    require_owner_message_reference(str(record.get("approval_channel", "")), reference)
    try:
        approved_at = datetime.fromisoformat(str(record.get("approved_at", "")).replace("Z", "+00:00"))
        if approved_at.tzinfo is None or approved_at < datetime.fromisoformat(POLICY_CHANGED_AT):
            raise ValueError("approval predates the notify-first policy")
    except (TypeError, ValueError) as error:
        raise ValueError("a new dated per-review owner approval is required") from error
    if not all(str(record.get(key, "")).strip() for key in ("review_id", "app_id", "reply")):
        raise ValueError("owner approval scope is incomplete")
    if record.get("platform") not in {"ios", "android"}:
        raise ValueError("unsupported review platform")
    if len(str(record.get("review_content_sha256", ""))) != 64:
        raise ValueError("owner approval must bind the reviewed content")
    if record.get("approval_sha256") != approval_fingerprint(record):
        raise ValueError("owner approval does not match the exact review and reply")
    if review is not None:
        if any(str(record.get(key, "")) != str(review.get(key, "")) for key in ("review_id", "app_id", "platform")):
            raise ValueError("owner approval target does not match the current review")
        if review.get("status") != "pending" or review.get("developer_reply") or review.get("review_kind") == "rating_only":
            raise ValueError("review is no longer a pending text review")
        if review_fingerprint(review) != record["review_content_sha256"]:
            raise ValueError("review changed after owner approval; notify and approve again")
