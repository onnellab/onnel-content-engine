"""Aether-only gross-cost evidence and paid-request fences; never fetch or approve.

Evidence hashes establish byte integrity, NOT the truth of a billing assertion.
A reviewer must obtain current provider/account evidence separately. This module
does not create an active proof, accept terms, change billing, or read credentials.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from zoneinfo import ZoneInfo

from aether_cost_policy import ALLOWED_LYRIA_MODEL
from short_video_credentials import CredentialError
from short_video_private_permissions import private_path_permissions

AETHER_ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn"
PROOF_PATH = AETHER_ROOT / "lyria-paid-evidence" / "proof.json"
MAX_PROOF_AGE = timedelta(hours=24)
MAX_GROSS_USD = Decimal("0.08")
PRICE_URLS = {
    "https://cloud.google.com/vertex-ai/generative-ai/pricing",
    "https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing",
    "https://cloud.google.com/skus",
}
MODEL_URLS = {
    "https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/lyria/lyria-3",
    "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/lyria/lyria-3",
}
TERMS_URL = "https://cloud.google.com/terms/service-terms"


def utc_now():
    return datetime.now(timezone.utc)


def _time(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
            raise ValueError()
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CredentialError("aether_lyria_cost_proof_time_invalid") from None


def _decimal(value):
    # Strings only: no binary float rounding, booleans, NaN, exponents or infinities.
    try:
        if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,8})(?:\.\d{1,18})?", value):
            raise ValueError()
        result = Decimal(value)
        if not result.is_finite():
            raise ValueError()
        return result
    except (ValueError, InvalidOperation):
        raise CredentialError("aether_lyria_cost_proof_amount_invalid") from None


def _read(path, *, limit=2 * 1024 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise CredentialError("aether_lyria_evidence_integrity")
    return path.read_bytes()


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise CredentialError("aether_lyria_evidence_invalid") from None


def _source(root, descriptor, *, allowed_urls=None):
    if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256", "reference"}:
        raise CredentialError("aether_lyria_evidence_invalid")
    relative, expected, reference = (descriptor.get(key) for key in ("path", "sha256", "reference"))
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or Path(relative).is_absolute() or any(p in {"", ".", ".."} for p in relative.split("/"))
            or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected)
            or not isinstance(reference, str) or not 1 <= len(reference) <= 1024
            or any(ord(c) < 32 for c in reference)):
        raise CredentialError("aether_lyria_evidence_invalid")
    if allowed_urls is not None and reference.split("?", 1)[0] not in allowed_urls:
        raise CredentialError("aether_lyria_evidence_source_invalid")
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise CredentialError("aether_lyria_evidence_integrity")
    if hashlib.sha256(_read(current)).hexdigest() != expected:
        raise CredentialError("aether_lyria_evidence_integrity")


def require_generation_window(slot, *, now=None):
    current = now or utc_now()
    if current.tzinfo is None:
        raise CredentialError("aether_lyria_generation_window_closed")
    local = current.astimezone(ZoneInfo("Asia/Seoul"))
    if (not isinstance(slot, str) or slot != local.date().isoformat()
            or local.weekday() not in {1, 5} or local.hour >= 8):
        raise CredentialError("aether_lyria_generation_window_closed")


def load_paid_proof(project_id, *, expected_sha256=None, now=None):
    """Read an existing reviewed proof. Unknown total/rights always means HOLD."""
    path = PROOF_PATH
    if not path.exists():
        raise CredentialError("aether_lyria_cost_proof_missing")
    if (path.parent.is_symlink() or not private_path_permissions(path.parent)
            or not private_path_permissions(path)):
        raise CredentialError("aether_lyria_cost_proof_permissions")
    raw = _read(path, limit=64 * 1024)
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and sha != expected_sha256:
        raise CredentialError("aether_lyria_cost_proof_changed")
    proof = _json(raw)
    required = {"schema_version", "profile", "provider", "project_id", "model", "location",
                "candidate_count", "checked_at", "expires_at", "reviewer", "authority_reference",
                "pricing", "billing", "rights"}
    if (set(proof) != required or type(proof.get("schema_version")) is not int
            or proof["schema_version"] != 1 or proof.get("profile") != "aether_inn"
            or proof.get("provider") != "google_cloud" or proof.get("project_id") != project_id
            or proof.get("model") != ALLOWED_LYRIA_MODEL or proof.get("location") != "global"
            or type(proof.get("candidate_count")) is not int or proof["candidate_count"] != 1
            or proof.get("reviewer") != "dot"
            or not isinstance(proof.get("authority_reference"), str)
            or not 1 <= len(proof["authority_reference"]) <= 1024):
        raise CredentialError("aether_lyria_cost_proof_binding_invalid")
    checked, expires, current = _time(proof["checked_at"]), _time(proof["expires_at"]), now or utc_now()
    if current.tzinfo is None or not checked <= current < expires or not timedelta(0) < expires - checked <= MAX_PROOF_AGE:
        raise CredentialError("aether_lyria_cost_proof_expired")
    price, billing, rights = proof["pricing"], proof["billing"], proof["rights"]
    if (not isinstance(price, dict) or set(price) != {"unit", "currency", "unit_price", "source"}
            or price.get("unit") != "song" or not isinstance(price.get("currency"), str)
            or not re.fullmatch(r"[A-Z]{3}", price["currency"])):
        raise CredentialError("aether_lyria_cost_proof_pricing_invalid")
    if (not isinstance(billing, dict)
            or set(billing) != {"country", "currency", "tax_rate", "mandatory_fee_per_song",
                               "rounding_usd_upper_bound", "usd_per_currency_upper_bound",
                               "all_mandatory_costs_confirmed", "source", "fx_source"}
            or billing.get("currency") != price["currency"]
            or not isinstance(billing.get("country"), str) or not re.fullmatch(r"[A-Z]{2}", billing["country"])
            or billing.get("all_mandatory_costs_confirmed") is not True):
        raise CredentialError("aether_lyria_billing_evidence_incomplete")
    if (not isinstance(rights, dict)
            or set(rights) != {"commercial_use_allowed", "output_distribution_allowed",
                               "existing_agreement_confirmed", "agreement_reference", "model_source", "terms_source"}
            or any(rights.get(key) is not True for key in (
                "commercial_use_allowed", "output_distribution_allowed", "existing_agreement_confirmed"))
            or not isinstance(rights.get("agreement_reference"), str)
            or not 1 <= len(rights["agreement_reference"]) <= 1024):
        raise CredentialError("aether_lyria_commercial_rights_unverified")
    _source(path.parent, price["source"], allowed_urls=PRICE_URLS)
    _source(path.parent, billing["source"])
    _source(path.parent, rights["model_source"], allowed_urls=MODEL_URLS)
    _source(path.parent, rights["terms_source"], allowed_urls={TERMS_URL})
    unit, tax, fee, fx, rounding = (_decimal(value) for value in (
        price["unit_price"], billing["tax_rate"], billing["mandatory_fee_per_song"],
        billing["usd_per_currency_upper_bound"], billing["rounding_usd_upper_bound"]))
    if unit <= 0 or fx <= 0 or tax > 1:
        raise CredentialError("aether_lyria_cost_proof_amount_invalid")
    if price["currency"] == "USD":
        if fx != 1 or billing["fx_source"] is not None:
            raise CredentialError("aether_lyria_fx_unverified")
    else:
        if billing["fx_source"] is None:
            raise CredentialError("aether_lyria_fx_unverified")
        _source(path.parent, billing["fx_source"])
    # Conservative: include mandatory fees in the taxable base; never subtract
    # credits or anticipated VAT recovery, and never round a cost down to cents.
    with localcontext() as context:
        context.prec = 120  # exceeds all products of bounded 27-digit inputs
        total = (unit + fee) * (1 + tax) * fx + rounding
    if not 0 < total <= MAX_GROSS_USD:
        raise CredentialError("aether_lyria_gross_spend_limit")
    if not checked <= (now or utc_now()) < expires:
        raise CredentialError("aether_lyria_cost_proof_expired")
    return {"proof_sha256": sha, "gross_cost_upper_bound_usd": str(total),
            "checked_at": proof["checked_at"], "expires_at": proof["expires_at"]}


def require_no_unsettled_intents(*, single_root=None, extra_roots=(), current_intent=None):
    """Queue FINAL/stale/rejected flags never erase a possibly charged request.

    Only the exact already-validated current intent may be excluded by the
    request adapter while it transitions to dispatch. No state is changed here.
    """
    singles = Path(single_root) if single_root is not None else AETHER_ROOT / "singles"
    roots = [(singles / "jobs", True), (AETHER_ROOT / "lyria", False),
             *((Path(root), False) for root in extra_roots)]
    budget = [10000]

    def directory_exists(path):
        # exists()/glob() may swallow PermissionError on supported Python
        # versions. Only a real FileNotFoundError means an absent optional root.
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            return False
        except OSError:
            raise CredentialError("aether_lyria_generation_manifest_unreadable") from None
        if not stat.S_ISDIR(mode):  # includes symlinks and replacement files
            raise CredentialError("aether_lyria_generation_manifest_invalid")
        return True

    def child_directories(path):
        if not directory_exists(path):
            return []
        result = []
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    budget[0] -= 1
                    if budget[0] < 0:
                        raise CredentialError("aether_lyria_generation_manifest_scan_incomplete")
                    mode = entry.stat(follow_symlinks=False).st_mode
                    if stat.S_ISLNK(mode):
                        raise CredentialError("aether_lyria_generation_manifest_invalid")
                    if stat.S_ISDIR(mode):
                        result.append(Path(entry.path))
        except OSError:
            raise CredentialError("aether_lyria_generation_manifest_unreadable") from None
        return sorted(result)

    # Check the intermediate directories, not just the final jobs/lyria root.
    directory_exists(AETHER_ROOT)
    directory_exists(singles)
    seen = set()
    for root, jobs in roots:
        run_directories = ([run for job in child_directories(root)
                            for run in child_directories(job / "lyria")]
                           if jobs else child_directories(root))
        for run in run_directories:
            manifest = run / "manifest.json"
            # Force a successful read of the run directory as well. No glob
            # omission, unreadable subtree or missing manifest proves no charge.
            child_directories(run)
            resolved = manifest.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if current_intent is not None and resolved == Path(current_intent).resolve():
                continue
            try:
                data = _json(_read(manifest))
                state = data.get("state")
                if state in {"request_started", "prepared"}:
                    raise CredentialError("aether_lyria_generation_uncertain")
                if state == "not_sent" and data.get("dispatch_started") is False:
                    continue
                if state != "generated" or not isinstance(data.get("candidates"), list) or len(data["candidates"]) != 1:
                    raise CredentialError("aether_lyria_generation_manifest_invalid")
                candidate = data["candidates"][0]
                source = Path(candidate.get("file", ""))
                # Never follow arbitrary paths supplied by a malformed manifest.
                if source.parent != manifest.parent or source.is_symlink():
                    raise CredentialError("aether_lyria_generation_manifest_invalid")
                if hashlib.sha256(_read(source, limit=64 * 1024 * 1024)).hexdigest() != candidate.get("sha256"):
                    raise CredentialError("aether_lyria_generation_manifest_invalid")
            except CredentialError:
                raise
            except (OSError, ValueError, TypeError, AttributeError):
                raise CredentialError("aether_lyria_generation_manifest_invalid") from None


@contextmanager
def paid_request_lock():
    """Serialize Aether charge intent creation; this creates no scheduler."""
    if AETHER_ROOT.is_symlink():
        raise CredentialError("aether_lyria_paid_root_unsafe")
    AETHER_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not private_path_permissions(AETHER_ROOT):
        raise CredentialError("aether_lyria_paid_root_unsafe")
    fd = os.open(AETHER_ROOT / "lyria-paid.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CredentialError("aether_lyria_paid_request_busy") from None
        yield
    finally:
        os.close(fd)
