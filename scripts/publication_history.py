"""Read publication evidence without rewriting receipts or historical URLs.

Legacy done records can lack a post permalink. They still prevent reposting and
copy replacement, but must not be promoted to a verified posted manifest item.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

REMOTE_BROWSER_PLATFORMS = frozenset({"x", "linkedin", "medium"})
RECEIPT_PROVENANCE_FIELDS = (
    'published_at_precision', 'observed_at', 'observed_at_precision',
    'observation_source', 'browser_ui_timestamp', 'browser_ui_timezone',
    'draft_sha256', 'posted_body_sha256', 'account',
    'draft_hash_normalization', 'posted_body_hash_normalization',
    'body_evidence_kind', 'observed_body', 'observed_body_sha256',
    'observed_body_hash_normalization', 'observed_body_normalization', 'post_id', 'source_draft_path',
    'observed_short_url', 'canonical_destination_verified_at',
)



def _approved_linkedin_lead_adjustment(done: dict, receipt: dict, source: str, post: dict) -> bool:
    """Verify declared opening-only edits with full-body hashes and unchanged draft tail.

    This is receipt integrity, not an independent public observation; the caller
    still verifies author, post identity, specific permalink, and freshness.
    """
    if post.get('platform') != 'linkedin':
        return False
    body = receipt.get('submitted_body')
    if not isinstance(body, str) or not body or '\r' in body or body.endswith('\n'):
        return False
    old_head, old_sep, old_tail = source.removesuffix('\n').partition('\n\n')
    new_head, new_sep, new_tail = body.partition('\n\n')
    if not old_sep or not new_sep or not old_head or not old_tail:
        return False
    if new_tail != old_tail or new_head == old_head:
        return False
    if not (30 <= len(new_head) <= 200 and new_head.endswith('.') and '\n' not in new_head):
        return False
    if receipt.get('copy_adjustment') != (
            'Routine first-sentence direct answer preserving the approved article and remaining draft.'):
        return False
    if receipt.get('approval_source') != (
            "Owner's X/LinkedIn browser publication automation authorizes overdue valid drafts "
            'and routine fact-preserving wording improvements.'):
        return False
    if receipt.get('submitted_source_characters') != len(body):
        return False
    if not receipt.get('source_draft_path') or receipt['source_draft_path'] != post.get('draft_path'):
        return False
    if not receipt.get('canonical_url') or receipt['canonical_url'] != post.get('canonical_url'):
        return False
    if not receipt['canonical_url'].startswith('https://onnellab.com/blog/'):
        return False
    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
    return all(record.get('posted_body_sha256') == digest for record in (done, receipt))


def body_evidence_matches(done: dict, receipt: dict, source: str, post: dict) -> bool:
    """Check the declared evidence, never equate a rendered body with source bytes.

    The legacy contract proves a submitted body identical to the current draft.
    A declared LinkedIn opening-only edit must hash-bind the submitted body while
    preserving all later paragraphs. Recovered X observations instead bind the retained, normalized public body
    to the exact account/post and the independently verified canonical target.
    Their draft digest is context only, not proof of the missing submission.
    Identity, specific permalink, receipt status and observation freshness must
    also be checked by the caller.
    """
    draft_hash = hashlib.sha256(source.encode('utf-8')).hexdigest()
    if any(record.get('draft_sha256') != draft_hash for record in (done, receipt)):
        return False
    kind = receipt.get('body_evidence_kind', 'submitted_source')
    if done.get('body_evidence_kind', 'submitted_source') != kind:
        return False
    if kind == 'submitted_source':
        if any(record.get('observed_body_sha256') for record in (done, receipt)):
            return False
        digest = hashlib.sha256(source.removesuffix('\n').encode('utf-8')).hexdigest()
        if all(record.get('posted_body_sha256') == digest for record in (done, receipt)):
            return True
        return _approved_linkedin_lead_adjustment(done, receipt, source, post)
    if kind != 'observed_public_body' or post.get('platform') != 'x':
        return False
    fields = ('observed_body', 'observed_body_sha256', 'observed_body_hash_normalization',
              'observed_body_normalization',
              'observed_at', 'observation_source',
              'account', 'post_id', 'source_draft_path', 'canonical_url',
              'observed_short_url', 'canonical_destination_verified_at')
    if any(not isinstance(receipt.get(field), str) or not receipt[field]
           or done.get(field) != receipt[field] for field in fields):
        return False
    # An observation cannot simultaneously claim to recover unknown source bytes.
    if any(record.get(field) for record in (done, receipt)
           for field in ('posted_body_sha256', 'posted_body_hash_normalization', 'submitted_body')):
        return False
    body = receipt['observed_body']
    if receipt['observed_body_normalization'] != 'utf8_whitespace_collapsed_urls_preserved_v1':
        return False
    if body != ' '.join(body.split()) or any(ord(c) < 32 for c in body):
        return False
    if hashlib.sha256(body.encode('utf-8')).hexdigest() != receipt['observed_body_sha256']:
        return False
    if receipt['account'] != '@onnellab' or not receipt['post_id'].isdigit():
        return False
    url = f"https://x.com/onnellab/status/{receipt['post_id']}"
    if receipt.get('posted_url') != url or done.get('posted_url') != url:
        return False
    if receipt['source_draft_path'] != post.get('draft_path') or receipt['canonical_url'] != post.get('canonical_url'):
        return False
    if not receipt['canonical_url'].startswith('https://onnellab.com/blog/'):
        return False
    short_url = receipt['observed_short_url']
    if not re.fullmatch(r'https://t\.co/[A-Za-z0-9]+', short_url) or short_url not in body.split():
        return False
    try:
        observed = datetime.fromisoformat(receipt['observed_at'].replace('Z', '+00:00'))
        destination = datetime.fromisoformat(receipt['canonical_destination_verified_at'].replace('Z', '+00:00'))
        verified = datetime.fromisoformat(done['verified_at'].replace('Z', '+00:00'))
        return all(value.tzinfo is not None for value in (observed, destination, verified)) and observed <= destination <= verified
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def specific_permalink(platform: str, value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            return False
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
    except ValueError:
        return False
    if platform == "x":
        return host in {"x.com", "twitter.com"} and bool(re.fullmatch(r"/(?:[^/]+|i/web)/status/\d+", path))
    if platform == "linkedin":
        return host == "linkedin.com" and bool(re.fullmatch(r"/(?:feed/update/urn:li:(?:activity|share|ugcPost):\d+|posts/[^/]+)", path))
    if platform == "medium":
        return host == "medium.com" and bool(re.fullmatch(r"/(?!feed/|p/|me/)[^/]+/[^/]+-[0-9a-f]{6,}", path))
    return False


def publication_key(item: dict[str, object], template: str | None = None) -> str:
    return "::".join(str(value) for value in (item.get("topic_id", ""), item.get("platform", ""), item.get("language", ""), template or item.get("template_id", "")))


def publication_history(project_root: Path) -> dict[str, dict[str, object]]:
    """Join exact item identities; first valid existing URL wins over an inbox URL."""
    history: dict[str, dict[str, object]] = {}

    def add(key: object, record: object) -> None:
        if not isinstance(key, str) or not isinstance(record, dict):
            raise ValueError("malformed publication evidence")
        identity = key.split("::")
        if len(identity) != 4 or not all(identity):
            raise ValueError("malformed publication manual_key")
        if identity[1] not in REMOTE_BROWSER_PLATFORMS:
            return  # Hashnode history is audit-only, never distribution input.
        for field, expected in zip(("topic_id", "platform", "language", "template_id"), identity):
            if record.get(field) and record[field] != expected:
                raise ValueError(f"publication identity mismatch: {key}")
        incoming = dict(record)
        incoming["_valid_permalink"] = specific_permalink(identity[1], record.get("posted_url"))
        previous = history.get(key)
        if previous is None or (not previous["_valid_permalink"] and incoming["_valid_permalink"]):
            history[key] = incoming

    state_path = project_root / "data" / "manual_publish_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("done"), dict):
            raise ValueError("malformed manual publication state")
        for key, record in state["done"].items():
            add(key, record)
    inbox_path = project_root / "data" / "remote_browser_publications.json"
    if inbox_path.exists():
        inbox = json.loads(inbox_path.read_text(encoding="utf-8"))
        if not isinstance(inbox, dict) or inbox.get("schema_version") != 1 or not isinstance(inbox.get("records"), list):
            raise ValueError("malformed remote publication inbox")
        for record in inbox["records"]:
            if not isinstance(record, dict):
                raise ValueError("malformed remote publication record")
            if record.get("status") in {"new", "processed"}:
                add(record.get("manual_key"), record)
    return history


def preserve_publication(item: dict[str, object], history: dict[str, dict[str, object]], template: str | None = None) -> dict[str, object]:
    """Return a copy with evidence joined; never replace an existing posted URL."""
    item = dict(item)
    evidence = history.get(publication_key(item, template))
    if evidence is not None:
        if (evidence.get('body_evidence_kind') == 'observed_public_body'
                and evidence.get('canonical_url') != item.get('canonical_url')):
            raise ValueError('publication canonical URL mismatch')
        item["_publication_recorded"] = True
        if evidence["_valid_permalink"]:
            if not item.get("posted_url"):
                item["posted_url"] = evidence["posted_url"]
            if specific_permalink(str(item.get("platform", "")), item.get("posted_url")):
                item["status"] = "posted"
                for field in RECEIPT_PROVENANCE_FIELDS:
                    if field in evidence:
                        item[field] = evidence[field]
                if evidence.get('body_evidence_kind') == 'observed_public_body':
                    item.pop('posted_body_sha256', None)
                    item.pop('posted_body_hash_normalization', None)
                if evidence.get('published_at_precision') == 'unknown':
                    item['posted_at'] = ''
                elif not item.get("posted_at"):
                    item["posted_at"] = evidence.get("published_at") or evidence.get("marked_at") or ""
    if specific_permalink(str(item.get("platform", "")), item.get("posted_url")):
        item["_publication_recorded"] = True
    return item


def require_history_items(history: dict[str, dict[str, object]], keys: set[str], platforms: set[str]) -> None:
    missing = sorted(key for key in history if key.split("::")[1] in platforms and key not in keys)
    if missing:
        raise ValueError("cannot preserve publication evidence without previous manifest item: " + ", ".join(missing))
