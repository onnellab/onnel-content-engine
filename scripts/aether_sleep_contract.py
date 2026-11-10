"""Strict sleep pilot identities, publication dates and pure budget arithmetic.

Execution belongs to the existing daily runner and durable SingleQueue adapter.
This module alone grants neither paid dispatch nor media review.
"""
from __future__ import annotations

from datetime import datetime
import os
from decimal import Decimal
from zoneinfo import ZoneInfo

from aether_sleep_plan import amount

SERIES = "aether_inn_sleep"
SOURCE_KIND = "purpose_composed_sleep"
KST = ZoneInfo("Asia/Seoul")
CONCEPTS = (
    ("sleep_moonlit_guestroom", "Moonlit Guestroom"),
    ("sleep_stillwater_sanctuary", "Stillwater Sanctuary"),
    ("sleep_cloudrest_chamber", "Cloudrest Chamber"),
)
# Fixed pilot dates; runtime cost, provenance and review gates still apply.
PROPOSED_SLOTS = ("2026-11-10", "2026-11-13", "2026-11-16")


def runtime_enabled() -> bool:
    """Deployment alone must never activate the pilot."""
    from aether_sleep_request import gui_requested
    return os.environ.get("AETHER_SLEEP_PILOT_ENABLED") == "1" or gui_requested()


def require_activation() -> None:
    if not runtime_enabled():
        from short_video_credentials import CredentialError
        raise CredentialError("sleep_pilot_disabled")


def today_exception_valid(now: datetime, concept_id: str, slot: str) -> bool:
    """Date-bounded owner request, never inherited by ordinary fantasy singles."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("sleep_timezone_required")
    return (now.astimezone(KST).date().isoformat() == slot == "2026-11-10"
            and concept_id == CONCEPTS[0][0])


def validate_identity(job: dict) -> None:
    """Validate a prospective contract without admitting it to SingleQueue."""
    if not isinstance(job, dict):
        raise ValueError("sleep_identity_invalid")
    expected = dict(CONCEPTS)
    if (job.get("profile") != "aether_inn" or job.get("series") != SERIES
            or job.get("source_kind") != SOURCE_KIND
            or job.get("concept_id") not in expected
            or job.get("title") != expected.get(job.get("concept_id"))
            or type(job.get("duration_seconds")) is not int
            or job["duration_seconds"] != 1800):
        raise ValueError("sleep_identity_invalid")


def validate_budget_reservations(reservations: list) -> Decimal:
    """Fail-closed accounting math; caller must supply complete durable history.

Reservations are never released automatically, even for failures or uncertain
requests. This pure validator does not assert account-specific price evidence.
"""
    if not isinstance(reservations, list) or len(reservations) > 3:
        raise ValueError("sleep_request_limit")
    seen = set()
    total = Decimal(0)
    for row in reservations:
        if not isinstance(row, dict) or row.get("concept_id") not in dict(CONCEPTS):
            raise ValueError("sleep_reservation_invalid")
        if row["concept_id"] in seen or type(row.get("request_count")) is not int or row["request_count"] != 1:
            raise ValueError("sleep_paid_retry_forbidden")
        seen.add(row["concept_id"])
        cost = amount(row.get("all_in_reserved_usd"))
        if cost <= 0:
            raise ValueError("sleep_reservation_invalid")
        total += cost
    if total > Decimal("0.50"):
        raise ValueError("sleep_all_in_budget_exceeded")
    return total

