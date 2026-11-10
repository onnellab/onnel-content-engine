"""One owner-requested same-day single; no timer, account change or retry.

The exception is only for 2026-11-10 and this exact new title. The owner approved
using official estimated pricing ($0.08 base + assumed 10% Korea VAT = $0.088),
with a $0.10 all-in cap for this song only. Account tax/FX/fees and the invoice
remain unverified. Ordinary recurring price policy and the sleep pilot are not
changed. The exact source and estimate are bound through the paid request.
"""
from datetime import datetime
from decimal import Decimal
import hashlib
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from short_video_credentials import CredentialError
from short_video_pipeline import digest, load_json

SLOT = "2026-11-10"
TITLE = "Toward the Horizon of the New Kingdom"
LANE = "frontier_surge"
PROJECT = "aether-inn-music"
ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles"


def canonical_style():
    from aether_cover import lane_direction
    from aether_daily_local import COMMON_STYLE
    return lane_direction(LANE) + COMMON_STYLE


def require_target(slot, title, style, lane, *, now=None, active=True):
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if (slot != SLOT or title != TITLE or lane != LANE or style != canonical_style()
            or current.tzinfo is None
            or active and current.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat() != SLOT):
        raise CredentialError("aether_single_today_identity_or_date_invalid")


def job_id():
    return digest({"slot": SLOT, "title": TITLE, "style": canonical_style(), "lane": LANE})[:24]


def load_cost_estimate(*, expected_sha256=None, now=None):
    """Owner accepted an estimate, not a verified invoice, for this song only."""
    from aether_paid_guard import load_paid_proof
    source = load_paid_proof(PROJECT, now=now)
    base = Decimal(source["provider_base_price_usd"])
    vat = base * Decimal("0.10")
    total = base + vat
    if base > Decimal("0.08") or total > Decimal("0.10"):
        raise CredentialError("aether_single_today_estimated_budget_exceeded")
    estimate = {
        "kind": "owner_approved_official_price_estimate",
        "slot": SLOT, "title": TITLE, "project_id": PROJECT,
        "model": "lyria-3-pro-preview", "candidate_count": 1,
        "provider_base_usd": str(base), "assumed_korea_vat_rate": "0.10",
        "estimated_tax_usd": str(vat), "estimated_total_usd": str(total),
        "approved_all_in_cap_usd": "0.10",
        "tax_reference": "https://docs.cloud.google.com/billing/docs/resources/vat-overview",
        "cost_basis": "official_provider_base_plus_assumed_korea_vat",
        "actual_account_tax_fx_and_fees_verified": False,
        "gross_cost_verified": False, "final_billed_cost_usd": None,
        "provider_proof_sha256": source["proof_sha256"],
        "checked_at": source["checked_at"], "expires_at": source["expires_at"],
    }
    sha = digest(estimate)
    if expected_sha256 is not None and sha != expected_sha256:
        raise CredentialError("aether_single_today_cost_estimate_changed")
    return {**estimate, "proof_sha256": sha}


def scope_for(job):
    require_target(job["slot"], job["title"], job["style"], job["lane"])
    if job.get("id") != job_id() or job.get("source_kind", "new_lyria") != "new_lyria":
        raise CredentialError("aether_single_today_identity_or_date_invalid")
    proof = load_cost_estimate()
    return {"job_id": job["id"], "cost_estimate_sha256": proof["proof_sha256"]}


def require_generation(scope, slot, project, prompt, *, output_root=None, now=None):
    from lyria_generate import build_aether_prompt
    require_target(slot, TITLE, canonical_style(), LANE, now=now)
    if (not isinstance(scope, dict) or set(scope) != {"job_id", "cost_estimate_sha256"}
            or scope.get("job_id") != job_id() or project != PROJECT
            or prompt != build_aether_prompt(TITLE, canonical_style())):
        raise CredentialError("aether_single_today_generation_binding_invalid")
    expected_root = ROOT / "jobs" / job_id() / "lyria"
    if output_root is not None and Path(output_root) != expected_root:
        raise CredentialError("aether_single_today_output_binding_invalid")
    state = load_json(ROOT / "queue.json", limit=16 * 1024 * 1024)
    job = state.get("jobs", {}).get(job_id(), {})
    require_target(job.get("slot"), job.get("title"), job.get("style"), job.get("lane"), now=now)
    if (job.get("same_day_release") != scope
            or job.get("source_kind", "new_lyria") != "new_lyria"
            or digest(job.get("brief")) != job.get("payload_hash")):
        raise CredentialError("aether_single_today_generation_binding_invalid")
    return load_cost_estimate(expected_sha256=scope["cost_estimate_sha256"], now=now)


def claim_once(scope, output_root):
    """Run under existing paid lock, before any model request or manifest."""
    output_root = Path(output_root)
    if output_root != ROOT / "jobs" / job_id() / "lyria":
        raise CredentialError("aether_single_today_output_binding_invalid")
    folder = output_root.parent
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise CredentialError("aether_single_today_output_binding_invalid")
    if output_root.exists() and any(output_root.iterdir()):
        raise CredentialError("aether_single_today_paid_retry_forbidden")
    try:
        fd = os.open(folder / "same-day-generation.claim",
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise CredentialError("aether_single_today_paid_retry_forbidden") from None
    with os.fdopen(fd, "w") as stream:
        stream.write(scope["cost_estimate_sha256"])
        stream.flush()
        os.fsync(stream.fileno())


def request_path():
    return ROOT.parent.parent / "daily-aether" / "single-today-request-20261110.json"


def request_binding():
    return {"schema_version": 1, "kind": "owner_requested_single_today",
            "slot": SLOT, "title": TITLE, "lane": LANE, "job_id": job_id(),
            "project_id": PROJECT, "model": "lyria-3-pro-preview",
            "candidate_count": 1, "approved_all_in_cap_usd": "0.10",
            "estimate_accepted": True}


def pending_request(*, now=None):
    from aether_paid_guard import _read, _json
    from short_video_private_permissions import private_path_permissions
    path = request_path()
    if not path.exists():
        return False
    if (any(p.is_symlink() for p in (path, *path.parents))
            or not private_path_permissions(path.parent) or not private_path_permissions(path)):
        raise CredentialError("aether_single_today_request_unsafe")
    data = _json(_read(path, limit=16384))
    if data != request_binding():
        raise CredentialError("aether_single_today_request_changed")
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    return current.tzinfo is not None and current.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat() == SLOT


def record_request(*, now=None):
    """Request continuation by the existing GUI launchd owner, not a new runner."""
    from short_video_pipeline import canonical
    from short_video_private_permissions import private_path_permissions
    require_target(SLOT, TITLE, canonical_style(), LANE, now=now)
    path = request_path()
    if path.exists():
        if not pending_request(now=now):
            raise CredentialError("aether_single_today_identity_or_date_invalid")
        return {"status": "already_requested", "slot": SLOT, "title": TITLE}
    if (any(p.is_symlink() for p in (path.parent, *path.parent.parents))
            or not private_path_permissions(path.parent)):
        raise CredentialError("aether_single_today_request_unsafe")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(request_binding()))
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": "requested", "slot": SLOT, "title": TITLE}
