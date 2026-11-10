"""Exact owner-approved estimate continuation by the existing GUI producer only."""
from datetime import datetime
from decimal import Decimal
import os
from zoneinfo import ZoneInfo

from short_video_credentials import CredentialError
from short_video_pipeline import canonical, digest
import aether_paid_guard as paid
from aether_sleep_contract import CONCEPTS, PROPOSED_SLOTS

PROJECT = "aether-inn-music"
SERVICE = "com.onnellab.aether-daily-local"


def request_path():
    return paid.AETHER_ROOT.parent / "daily-aether" / "sleep-today-requests" / "20261110.json"


def request_binding():
    from aether_sleep_plan import build_plan
    return {"schema_version": 1, "kind": "owner_requested_sleep_estimate",
            "activation_slot": PROPOSED_SLOTS[0], "activation_concept": CONCEPTS[0][0],
            "project_id": PROJECT, "model": "lyria-3-pro-preview",
            "concepts": [{"concept_id": row["id"], "title": row["title"], "slot": slot,
                          "prompt_sha256": digest(row["prompt"])}
                         for row, slot in zip(build_plan()["drafts"], PROPOSED_SLOTS)],
            "candidate_count_per_concept": 1, "maximum_requests": 3,
            "approved_total_cap_usd": "0.50", "paid_retry_allowed": False,
            "estimate_accepted": True}


def pending_request(*, now=None):
    from aether_sleep_guard import private_read
    path = request_path()
    if not path.exists():
        return False
    if paid._json(private_read(path)) != request_binding():
        raise CredentialError("sleep_request_changed")
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    return (current.tzinfo is not None
            and current.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat() == PROPOSED_SLOTS[0])


def gui_requested(*, now=None):
    return os.environ.get("XPC_SERVICE_NAME") == SERVICE and pending_request(now=now)


def record_request(*, now=None):
    from short_video_private_permissions import private_path_permissions
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if current.tzinfo is None or current.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat() != PROPOSED_SLOTS[0]:
        raise CredentialError("sleep_request_date_invalid")
    path = request_path()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise CredentialError("sleep_request_unsafe")
    path.parent.mkdir(mode=0o700, parents=False, exist_ok=True)
    if not private_path_permissions(path.parent):
        raise CredentialError("sleep_request_unsafe")
    if path.exists():
        pending_request(now=now)
        return {"status": "already_requested"}
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(request_binding()))
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"status": "requested", "slot": PROPOSED_SLOTS[0], "concept_id": CONCEPTS[0][0]}


def load_cost_estimate(project, *, expected_sha256=None, now=None):
    if project != PROJECT or not gui_requested(now=now):
        raise CredentialError("sleep_estimate_scope_invalid")
    source = paid.load_paid_proof(project, now=now)
    base = paid._decimal(source["provider_base_price_usd"])
    estimate = base * Decimal("1.10")
    if base != Decimal("0.08") or estimate * 3 > Decimal("0.50"):
        raise CredentialError("sleep_estimated_budget_exceeded")
    evidence = {
        "evidence_kind": "owner_approved_official_price_estimate",
        "cost_basis": "official_provider_base_plus_assumed_korea_vat",
        "request_binding": request_binding(), "provider_proof_sha256": source["proof_sha256"],
        "provider_base_usd": str(base), "assumed_korea_vat_rate": "0.10",
        "estimated_per_request_usd": str(estimate), "estimated_pilot_total_usd": str(estimate * 3),
        "approved_total_cap_usd": "0.50",
        # Legacy ledger field is a budget allocation, NOT a verified all-in price.
        # Three allocations total .499999999998; actual charges remain unknown.
        "all_in_reserved_usd": "0.166666666666",
        "reservation_basis": "pilot_budget_allocation_not_verified_charge",
        "actual_account_tax_fx_and_fees_verified": False, "gross_cost_verified": False,
        "invoice_facts_independently_verified": False, "final_billed_cost_usd": None,
        "checked_at": source["checked_at"], "expires_at": source["expires_at"],
    }
    sha = digest(evidence)
    if expected_sha256 is not None and sha != expected_sha256:
        raise CredentialError("sleep_cost_estimate_changed")
    return {**evidence, "proof_sha256": sha}
