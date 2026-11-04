"""Provider-base price/terms evidence and durable one-request fences.

The source receipt verifies public provider conditions, not copyright ownership,
account-specific agreement acceptance, tax/FX or the final invoice. The source
collector and the paid transport are separate; this reader never authenticates.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
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
# The former hand-authored proof.json is retained on disk, never synthesized.
# This receipt is refreshed from official public documents by the local owner.
PROOF_PATH = AETHER_ROOT / "lyria-paid-evidence" / "public-sources" / "current.json"
MAX_PROOF_AGE = timedelta(hours=24)
MAX_BASE_PRICE_USD = Decimal("0.08")


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


def require_generation_window(slot, *, now=None):
    current = now or utc_now()
    if current.tzinfo is None:
        raise CredentialError("aether_lyria_generation_window_closed")
    local = current.astimezone(ZoneInfo("Asia/Seoul"))
    if (not isinstance(slot, str) or slot != local.date().isoformat()
            or local.weekday() not in {1, 5} or local.hour >= 8):
        raise CredentialError("aether_lyria_generation_window_closed")


def load_paid_proof(project_id, *, expected_sha256=None, now=None):
    """Read separately verifiable provider price and commercial-use sources.

    The owner's original Lyria-only $0.08/song instruction and 2026-11-04
    correction use the provider base-price basis. Tax/FX and final invoices are
    not claimed verified or zero. The former hand-authored gross-cost proof is
    not a prerequisite for this source-backed policy. No model request, account
    agreement acceptance, queue mutation or credential access occurs here.
    """
    from aether_lyria_rights import URLS, documented_permission, documented_price, SourceError

    if not isinstance(project_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project_id):
        raise CredentialError("aether_lyria_cost_proof_binding_invalid")
    path = PROOF_PATH
    if not path.exists():
        raise CredentialError("aether_lyria_provider_sources_missing")
    if (any(part.is_symlink() for part in (path, *path.parents))
            or not private_path_permissions(path.parent)
            or not private_path_permissions(path)):
        raise CredentialError("aether_lyria_cost_proof_permissions")
    raw = _read(path, limit=64 * 1024)
    # A public policy receipt does not itself bind an account. Bind its exact
    # bytes to the configured project here and retain that binding in the intent.
    sha = hashlib.sha256(raw + b"\x00" + project_id.encode("ascii")).hexdigest()
    if expected_sha256 is not None and sha != expected_sha256:
        raise CredentialError("aether_lyria_cost_proof_changed")
    proof = _json(raw)
    if (type(proof.get("schema_version")) is not int or proof["schema_version"] != 2
            or proof.get("kind") != "aether_public_provider_sources"
            or proof.get("model") != ALLOWED_LYRIA_MODEL
            or proof.get("provider_permission_documented") is not True
            or proof.get("generation_authorized") is not False):
        raise CredentialError("aether_lyria_cost_proof_binding_invalid")
    checked, expires = _time(proof.get("checked_at")), _time(proof.get("expires_at"))
    current = now or utc_now()
    if (current.tzinfo is None or not checked <= current < expires
            or not timedelta(0) < expires - checked <= MAX_PROOF_AGE):
        raise CredentialError("aether_lyria_cost_proof_expired")
    sources, texts = proof.get("sources"), {}
    if not isinstance(sources, dict) or set(sources) != set(URLS):
        raise CredentialError("aether_lyria_evidence_invalid")
    for name, url in URLS.items():
        source = sources[name]
        if (not isinstance(source, dict) or source.get("reference") != url
                or not isinstance(source.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
                or source.get("path") != f"{name}-{source['sha256']}.txt"):
            raise CredentialError("aether_lyria_evidence_source_invalid")
        source_bytes = _read(path.parent / source["path"])
        if hashlib.sha256(source_bytes).hexdigest() != source["sha256"]:
            raise CredentialError("aether_lyria_evidence_integrity")
        try:
            texts[name] = source_bytes.decode("utf-8")
        except UnicodeError:
            raise CredentialError("aether_lyria_evidence_invalid") from None
    try:
        documented_permission(texts)
        unit = _decimal(documented_price(texts["pricing"]))
    except SourceError as error:
        raise CredentialError(str(error)) from None
    if str(unit) != proof.get("provider_base_price_usd"):
        raise CredentialError("aether_lyria_evidence_invalid")
    if not 0 < unit <= MAX_BASE_PRICE_USD:
        raise CredentialError("aether_lyria_spend_limit")
    if not checked <= (now or utc_now()) < expires:
        raise CredentialError("aether_lyria_cost_proof_expired")
    return {"proof_sha256": sha, "evidence_kind": "provider_price_and_terms",
            "project_id": project_id, "provider_base_price_usd": str(unit),
            "cost_basis": "provider_base_excluding_tax_and_currency_adjustments",
            "gross_cost_verified": False, "final_billed_cost_usd": None,
            "account_agreement_verified": False, "copyright_ownership_certified": False,
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
