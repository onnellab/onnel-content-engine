#!/usr/bin/env python3
"""Reconcile remote Chrome publication permalinks into dashboard done state."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from publication_history import specific_permalink, RECEIPT_PROVENANCE_FIELDS
from distribution_policy import channel_excluded

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = ROOT / "data" / "remote_browser_publications.json"
DEFAULT_STATE = ROOT / "data" / "manual_publish_state.json"
DEFAULT_SOCIAL = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION = ROOT / "generated" / "syndication" / "manifest.json"
REMOTE_BROWSER_PLATFORMS = {"x", "linkedin"}
PROVENANCE_FIELDS = RECEIPT_PROVENANCE_FIELDS

class RemotePublicationError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def receipt_provenance(record: dict[str, Any]) -> dict[str, str]:
    result = {}
    for field in PROVENANCE_FIELDS:
        if field not in record:
            continue
        value = record[field]
        if not isinstance(value, str) or len(value) > 512 or any(ord(c) < 32 for c in value):
            raise RemotePublicationError(f'invalid receipt provenance: {field}')
        if field.endswith('_sha256') and not re.fullmatch(r'[0-9a-f]{64}', value):
            raise RemotePublicationError(f'invalid receipt provenance: {field}')
        result[field] = value
    if result.get('published_at_precision') == 'unknown' and record.get('published_at') not in (None, ''):
        raise RemotePublicationError('unknown publication time must not contain published_at')
    return result


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RemotePublicationError(f"expected JSON object: {path}")
    return payload


def key(topic_id: object, platform: object, language: object, template_id: object) -> str:
    return "::".join(map(str, (topic_id, platform, language, template_id)))


def known_items(social: Path, syndication: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for post in load_json(social).get("posts", []):
        if not isinstance(post, dict) or post.get("is_variant"):
            continue
        platform = str(post.get("platform", ""))
        if platform not in REMOTE_BROWSER_PLATFORMS:
            continue
        manual_key = key(post.get("topic_id", ""), platform, post.get("language", ""), post.get("template_id", ""))
        result[manual_key] = {"platform": platform, "topic_id": str(post.get("topic_id", "")), "language": str(post.get("language", "")), "template_id": str(post.get("template_id", ""))}
    for draft in load_json(syndication).get("drafts", []):
        if not isinstance(draft, dict):
            continue
        platform = str(draft.get("platform", ""))
        if platform not in REMOTE_BROWSER_PLATFORMS:
            continue
        manual_key = key(draft.get("topic_id", ""), platform, draft.get("language", ""), "markdown")
        result[manual_key] = {"platform": platform, "topic_id": str(draft.get("topic_id", "")), "language": str(draft.get("language", "")), "template_id": "markdown"}
    return result


def normalized_permalink(platform: str, value: str) -> str:
    raw = value.strip()
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as error:
        raise RemotePublicationError(f"invalid published URL: {raw}") from error
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RemotePublicationError(f"published URL must be http(s): {raw}")
    if not specific_permalink(platform, raw):
        raise RemotePublicationError(f"not a specific {platform} public post permalink: {raw}")
    # fragments never identify a different post; preserve meaningful query strings.
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    os.replace(temp, path)


def reconcile(inbox_path: Path = DEFAULT_INBOX, state_path: Path = DEFAULT_STATE, social: Path = DEFAULT_SOCIAL, syndication: Path = DEFAULT_SYNDICATION) -> int:
    inbox = load_json(inbox_path)
    if inbox.get("schema_version") != 1 or not isinstance(inbox.get("records"), list):
        raise RemotePublicationError("remote browser publication inbox is malformed")
    state = load_json(state_path)
    if not isinstance(state.get("done"), dict):
        raise RemotePublicationError("manual publish state is malformed")
    known = known_items(social, syndication)
    updates: list[tuple[dict[str, Any], dict[str, str], str]] = []
    seen_new: set[str] = set()
    for record in inbox["records"]:
        if not isinstance(record, dict) or record.get("status") != "new":
            continue
        if channel_excluded(record.get('platform')) or any(f'::{p}::' in str(record.get('manual_key', '')) for p in ('medium', 'hashnode')):
            continue  # Preserve old/pending receipts without processing excluded channels.
        manual_key = str(record.get("manual_key", "")).strip()
        if not manual_key or manual_key in seen_new:
            raise RemotePublicationError(f"missing or duplicate new manual_key: {manual_key!r}")
        seen_new.add(manual_key)
        item = known.get(manual_key)
        if not item:
            raise RemotePublicationError(f"unknown remote publication item: {manual_key}")
        platform = str(record.get("platform", "")).strip()
        if platform != item["platform"]:
            raise RemotePublicationError(f"platform mismatch for {manual_key}: {platform}")
        permalink = normalized_permalink(platform, str(record.get("posted_url", "")))
        previous = state["done"].get(manual_key, {})
        if not isinstance(previous, dict):
            raise RemotePublicationError(f"malformed existing publication: {manual_key}")
        previous_url = str(previous.get("posted_url", ""))
        if specific_permalink(platform, previous_url) and normalized_permalink(platform, previous_url) != permalink:
            raise RemotePublicationError(f"conflicting existing publication permalink: {manual_key}")
        receipt_provenance(record)  # Validate every record before changing either file.
        updates.append((record, item, permalink))
    if not updates:
        return 0
    processed_at = now_iso()
    for record, item, permalink in updates:
        manual_key = str(record["manual_key"])
        provenance = receipt_provenance(record)
        published_at = '' if provenance.get('published_at_precision') == 'unknown' else (str(record.get("published_at", "")).strip() or processed_at)
        previous = state["done"].get(manual_key, {})
        if not specific_permalink(item["platform"], previous.get("posted_url", "")):
            state["done"][manual_key] = {
                "topic_id": item["topic_id"], "platform": item["platform"], "language": item["language"], "template_id": item["template_id"],
                "marked_at": processed_at, "marked_by": "chatgpt_remote_browser", "posted_url": permalink,
                "verified_at": processed_at, "verification_method": "remote_chrome_permalink", "verification_confidence": "browser_permalink",
                "published_at": published_at,
                **provenance,
            }
        record["status"] = "processed"
        record["processed_at"] = processed_at
        record["posted_url"] = permalink
    state["updated_at"] = processed_at
    write_atomic(state_path, state)
    write_atomic(inbox_path, inbox)
    return len(updates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    try:
        count = reconcile(args.inbox, args.state)
    except (OSError, json.JSONDecodeError, RemotePublicationError) as error:
        print(f"Remote publication reconciliation failed: {error}")
        return 1
    print(f"reconciled {count} remote browser publication(s)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
