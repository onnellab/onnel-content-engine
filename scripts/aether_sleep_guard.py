"""Private, fail-closed account-cost receipts and irreversible sleep reservations.

No evidence collector or price assumptions live here. A real account-specific
quote/upper-bound receipt must be provisioned separately; public base pricing is
not an all-in receipt. No retry or reservation release is supported.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
import fcntl
import hashlib
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import aether_paid_guard as paid
from short_video_credentials import CredentialError
from short_video_private_permissions import private_path_permissions
from aether_sleep_plan import build_plan

ROOT = paid.AETHER_ROOT / 'sleep-pilot-20261109'
PROOF_PATH = ROOT / 'account-all-in-receipt.json'
from aether_sleep_contract import PROPOSED_SLOTS as SLOTS
MODEL = 'lyria-3-pro-preview'


def concept(concept_id):
    rows = build_plan()['drafts']
    for row in rows:
        if row['id'] == concept_id:
            return row
    raise CredentialError('sleep_identity_invalid')


def identity(scope, project, prompt, *, now=None):
    if (not isinstance(scope, dict) or set(scope) != {'concept_id', 'job_id', 'slot'}
            or not isinstance(scope.get('job_id'), str)
            or not re.fullmatch('[0-9a-f]{24}', scope['job_id'])
            or not isinstance(project, str)
            or not re.fullmatch('[a-z][a-z0-9-]{4,28}[a-z0-9]', project)):
        raise CredentialError('sleep_identity_invalid')
    from aether_sleep_contract import require_activation
    require_activation()
    row = concept(scope['concept_id'])
    rows = build_plan()['drafts']
    expected = SLOTS[[r['id'] for r in rows].index(row['id'])]
    current = now or paid.utc_now()
    if current.tzinfo is None:
        raise CredentialError('sleep_generation_window_closed')
    local = current.astimezone(ZoneInfo('Asia/Seoul'))
    if (scope['slot'] != expected or local.date().isoformat() != expected
            or (expected != SLOTS[0] and local.hour >= 8)):
        raise CredentialError('sleep_generation_window_closed')
    if prompt != row['prompt']:
        raise CredentialError('sleep_prompt_binding_invalid')
    return row


def private_read(path, *, limit=64 * 1024):
    path = Path(path)
    if (any(p.is_symlink() for p in (path, *path.parents))
            or not private_path_permissions(path.parent)
            or not private_path_permissions(path)):
        raise CredentialError('sleep_private_evidence_permissions')
    return paid._read(path, limit=limit)


def load_all_in_proof(project, *, expected_sha256=None, now=None):
    if not PROOF_PATH.exists():
        raise CredentialError('sleep_account_all_in_cost_unverified')
    raw = private_read(PROOF_PATH)
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise CredentialError('sleep_all_in_proof_changed')
    proof = paid._json(raw)
    # Receipt must identify the existing account/project, exact SKU, currency and
    # all unavoidable adjustments. An unpriced boolean such as verified=true is
    # deliberately insufficient. Keep original receipt bytes for audit.
    if (type(proof.get('schema_version')) is not int or proof['schema_version'] != 1
            or proof.get('kind') != 'google_cloud_account_all_in_upper_bound'
            or proof.get('project_id') != project or proof.get('model') != MODEL
            or proof.get('currency') != 'USD'
            or not isinstance(proof.get('account_reference'), str) or not proof['account_reference'].strip()
            or not isinstance(proof.get('receipt_reference'), str) or not proof['receipt_reference'].strip()
            or proof.get('coverage') != ['provider_base', 'tax', 'currency_conversion', 'mandatory_fees']):
        raise CredentialError('sleep_all_in_proof_invalid')
    checked, expires = paid._time(proof.get('checked_at')), paid._time(proof.get('expires_at'))
    current = now or paid.utc_now()
    if current.tzinfo is None or not checked <= current < expires or not timedelta(0) < expires-checked <= timedelta(hours=24):
        raise CredentialError('sleep_all_in_proof_expired')
    parts = [paid._decimal(proof.get(k)) for k in ('provider_base_usd', 'tax_upper_bound_usd', 'fx_upper_bound_usd', 'mandatory_fees_upper_bound_usd')]
    total = paid._decimal(proof.get('per_request_all_in_upper_bound_usd'))
    if parts[0] != Decimal('0.08') or sum(parts) != total or not 0 < total <= Decimal('0.50'):
        raise CredentialError('sleep_all_in_proof_invalid')
    # Retain a separately hashed original account receipt, not only a summary.
    receipt_hash = proof.get('source_sha256')
    if not isinstance(receipt_hash, str) or not re.fullmatch('[0-9a-f]{64}', receipt_hash):
        raise CredentialError('sleep_all_in_proof_invalid')
    source = private_read(PROOF_PATH.parent / ('account-receipt-' + receipt_hash + '.bin'), limit=2 * 1024 * 1024)
    if hashlib.sha256(source).hexdigest() != receipt_hash:
        raise CredentialError('sleep_all_in_proof_invalid')
    # A user or delegated reviewer checks the original receipt. This proves only
    # file integrity, exact bindings and arithmetic, never invoice authenticity.
    review = proof.get('review_attestation')
    fields = ('project_id', 'account_reference', 'model', 'currency',
              'provider_base_usd', 'tax_upper_bound_usd', 'fx_upper_bound_usd',
              'mandatory_fees_upper_bound_usd', 'per_request_all_in_upper_bound_usd')
    if (not isinstance(review, dict)
            or review.get('kind') != 'reviewed_account_upper_bound'
            or review.get('reviewer_kind') not in {'user', 'dot_delegated'}
            or review.get('source_sha256') != receipt_hash
            or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()
            or review.get('reviewed_values') != {key: proof[key] for key in fields}
            or not isinstance(review.get('source_references'), dict)
            or set(review['source_references']) != set(fields)
            or any(not isinstance(v, str) or not v.strip() for v in review['source_references'].values())
            or not checked <= paid._time(review.get('reviewed_at')) <= current):
        raise CredentialError('sleep_all_in_proof_invalid')
    return {'proof_sha256': digest, 'all_in_reserved_usd': str(total),
            'checked_at': proof['checked_at'], 'expires_at': proof['expires_at'],
            'evidence_kind': 'reviewed_account_upper_bound',
            'invoice_facts_independently_verified': False}


def load_cost_authorization(project, *, expected_sha256=None, now=None):
    """Explicit estimate mode never weakens the strict receipt validator."""
    from aether_sleep_request import gui_requested, load_cost_estimate
    if gui_requested(now=now):
        return load_cost_estimate(project, expected_sha256=expected_sha256, now=now)
    return load_all_in_proof(project, expected_sha256=expected_sha256, now=now)


def output_for(job_id):
    return paid.AETHER_ROOT / 'singles' / 'jobs' / job_id / 'lyria'


@contextmanager
def ledger_lock():
    if any(p.is_symlink() for p in (ROOT, *ROOT.parents)):
        raise CredentialError('sleep_ledger_unsafe')
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not private_path_permissions(ROOT):
        raise CredentialError('sleep_ledger_unsafe')
    fd = os.open(ROOT / 'ledger.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def ledger_rows():
    rows = []
    for path in sorted(ROOT.glob('reservation-*.json')):
        row = paid._json(private_read(path))
        if (row.get('concept_id') not in [r['id'] for r in build_plan()['drafts']]
                or path.name != 'reservation-' + row['concept_id'] + '.json'
                or type(row.get('request_count')) is not int or row['request_count'] != 1):
            raise CredentialError('sleep_ledger_invalid')
        rows.append(row)
    if len(rows) > 3 or len({r['concept_id'] for r in rows}) != len(rows):
        raise CredentialError('sleep_request_limit')
    if sum((paid._decimal(r.get('all_in_reserved_usd')) for r in rows), Decimal(0)) > Decimal('0.50'):
        raise CredentialError('sleep_all_in_budget_exceeded')
    if any(paid._decimal(r.get('all_in_reserved_usd')) <= 0 for r in rows):
        raise CredentialError('sleep_ledger_invalid')
    return rows


def require_remaining_budget(rows, proof):
    """Prove affordability of all remaining compositions, not just the next."""
    spent = sum((paid._decimal(r['all_in_reserved_usd']) for r in rows), Decimal(0))
    remaining = 3 - len(rows)
    unit = paid._decimal(proof['all_in_reserved_usd'])
    if unit <= 0 or remaining < 0 or spent + remaining * unit > Decimal('0.50'):
        raise CredentialError('sleep_full_pilot_budget_exceeded')


def require_affordable_pilot(proof):
    with ledger_lock():
        require_remaining_budget(ledger_rows(), proof)


def require_available(scope):
    with ledger_lock():
        rows = ledger_rows()
        if any(r['concept_id'] == scope['concept_id'] or r.get('job_id') == scope['job_id'] for r in rows):
            raise CredentialError('sleep_paid_retry_forbidden')
        if len(rows) >= 3:
            raise CredentialError('sleep_request_limit')


def reserve(scope, project, prompt, intent_path, intent_sha256, proof):
    row = identity(scope, project, prompt)
    if (Path(intent_path).parent.parent != output_for(scope['job_id'])
            or any(p.is_symlink() for p in (Path(intent_path), *Path(intent_path).parents))):
        raise CredentialError('sleep_output_binding_invalid')
    with ledger_lock():
        rows = ledger_rows()
        if any(r['concept_id'] == scope['concept_id'] or r.get('job_id') == scope['job_id'] for r in rows):
            raise CredentialError('sleep_paid_retry_forbidden')
        current = load_cost_authorization(project, expected_sha256=proof['proof_sha256'])
        require_remaining_budget(rows, current)
        if len(rows) >= 3 or sum((paid._decimal(r['all_in_reserved_usd']) for r in rows), paid._decimal(current['all_in_reserved_usd'])) > Decimal('0.50'):
            raise CredentialError('sleep_all_in_budget_exceeded')
        reservation = {**scope, **current, 'project_id': project, 'title': row['title'],
                       'model': MODEL, 'request_count': 1, 'intent_path': str(intent_path),
                       'intent_sha256': intent_sha256,
                       'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        path = ROOT / ('reservation-' + scope['concept_id'] + '.json')
        # Under flock, exclusive creation and fsync are durable before transport.
        import json
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(reservation, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(ROOT, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def require_dispatch(scope, project, prompt, intent_path, intent_sha256, intent, *, now=None):
    row = identity(scope, project, prompt, now=now)
    if (Path(intent_path).parent.parent != output_for(scope['job_id'])
            or any(p.is_symlink() for p in (Path(intent_path), *Path(intent_path).parents))
            or intent.get('sleep_scope') != scope or intent.get('title') != row['title']
            or intent.get('model') != MODEL or intent.get('project_id') != project
            or intent.get('prompt_sha256') != hashlib.sha256(prompt.encode()).hexdigest()
            or type(intent.get('candidate_count')) is not int or intent['candidate_count'] != 1):
        raise CredentialError('sleep_intent_binding_invalid')
    with ledger_lock():
        rows = ledger_rows()
        matching = [r for r in rows if r['concept_id'] == scope['concept_id']]
        if len(matching) != 1:
            raise CredentialError('sleep_reservation_missing')
        reserved = matching[0]
        for key, value in {**scope, 'project_id': project, 'model': MODEL, 'title': row['title'],
                           'intent_path': str(intent_path), 'intent_sha256': intent_sha256,
                           'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}.items():
            if reserved.get(key) != value:
                raise CredentialError('sleep_reservation_binding_invalid')
        proof = load_cost_authorization(project, expected_sha256=reserved['proof_sha256'], now=now)
        if proof['all_in_reserved_usd'] != reserved['all_in_reserved_usd']:
            raise CredentialError('sleep_reservation_binding_invalid')


def validate_generated_sleep(manifest_path, *, concept_id, job_id, slot):
    """Read-only recovery of one completed paid source, never charge permission."""
    path = Path(manifest_path)
    scope = {'concept_id': concept_id, 'job_id': job_id, 'slot': slot}
    row = concept(concept_id)
    if (not isinstance(job_id, str) or not re.fullmatch('[0-9a-f]{24}', job_id)
            or path.parent.parent != output_for(job_id) or path.name != 'manifest.json'):
        raise CredentialError('sleep_output_binding_invalid')
    manifest = paid._json(private_read(path))
    expected_slot = SLOTS[[r['id'] for r in build_plan()['drafts']].index(concept_id)]
    prompt_sha = hashlib.sha256(row['prompt'].encode()).hexdigest()
    if (slot != expected_slot or manifest.get('state') != 'generated'
            or manifest.get('sleep_scope') != scope or manifest.get('title') != row['title']
            or manifest.get('model') != MODEL or manifest.get('prompt_sha256') != prompt_sha
            or type(manifest.get('candidate_count')) is not int or manifest['candidate_count'] != 1
            or manifest.get('slot') != slot or not isinstance(manifest.get('candidates'), list)
            or len(manifest['candidates']) != 1):
        raise CredentialError('sleep_generated_manifest_invalid')
    with ledger_lock():
        reservations = [r for r in ledger_rows() if r['concept_id'] == concept_id]
        if len(reservations) != 1:
            raise CredentialError('sleep_reservation_missing')
        reservation = reservations[0]
        expected = {**scope, 'title': row['title'], 'model': MODEL, 'intent_path': str(path),
                    'project_id': manifest.get('project_id'), 'prompt_sha256': prompt_sha}
        if any(reservation.get(k) != v for k, v in expected.items()):
            raise CredentialError('sleep_reservation_binding_invalid')
        if (not isinstance(manifest.get('sleep_all_in_proof'), dict)
                or manifest['sleep_all_in_proof'].get('proof_sha256') != reservation.get('proof_sha256')):
            raise CredentialError('sleep_reservation_binding_invalid')
    if not path.with_name('dispatch.claim').is_file() or path.with_name('dispatch.claim').is_symlink():
        raise CredentialError('sleep_generated_manifest_invalid')
    candidate = manifest['candidates'][0]
    if not isinstance(candidate, dict) or not isinstance(candidate.get('file'), str):
        raise CredentialError('sleep_generated_manifest_invalid')
    audio = Path(candidate['file'])
    if audio.parent != path.parent or audio.name not in {'candidate-01.mp3', 'candidate-01.wav'}:
        raise CredentialError('sleep_generated_manifest_invalid')
    if any(p.is_symlink() for p in (audio, *audio.parents)) or not private_path_permissions(audio):
        raise CredentialError('sleep_generated_manifest_invalid')
    raw = paid._read(audio, limit=64 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != candidate.get('sha256') or len(raw) != candidate.get('bytes'):
        raise CredentialError('sleep_generated_manifest_invalid')
    return {**manifest, 'manifest': str(path)}
