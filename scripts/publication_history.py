"""Read publication evidence without rewriting receipts or historical URLs.

Legacy done records can lack a post permalink. They still prevent reposting and
copy replacement, but must not be promoted to a verified posted manifest item.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

REMOTE_BROWSER_PLATFORMS = frozenset({"x", "linkedin", "medium"})
RECEIPT_PROVENANCE_FIELDS = (
    'published_at_precision', 'observed_at', 'observed_at_precision',
    'observation_source', 'browser_ui_timestamp', 'browser_ui_timezone',
    'draft_sha256', 'posted_body_sha256', 'account',
    'draft_hash_normalization', 'posted_body_hash_normalization',
)


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
        item["_publication_recorded"] = True
        if evidence["_valid_permalink"]:
            if not item.get("posted_url"):
                item["posted_url"] = evidence["posted_url"]
            if specific_permalink(str(item.get("platform", "")), item.get("posted_url")):
                item["status"] = "posted"
                for field in RECEIPT_PROVENANCE_FIELDS:
                    if field in evidence:
                        item[field] = evidence[field]
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
