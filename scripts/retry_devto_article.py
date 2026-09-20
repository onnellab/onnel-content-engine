#!/usr/bin/env python3
"""Retry one failed Dev.to syndication draft with duplicate-safe reconciliation."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from approve_syndication_draft import write_manifest
from post_syndication_drafts import (
    FOREM_API_ACCEPT,
    ONNELLAB_USER_AGENT,
    SyndicationPostingError,
    classify_posting_error,
    devto_payload,
    load_manifest,
    post_devto_draft,
)
from topic_management import TopicError, _require_current_published_topic
from update_devto_article import put_json, selected_devto_draft
from validate_syndication_drafts import (
    SyndicationValidationError,
    project_root_for_manifest,
    validate_syndication_drafts,
)

DEFAULT_MANIFEST = Path("generated/syndication/manifest.json")
API = "https://dev.to/api"


def normalized_url(value: object) -> str:
    return str(value or "").strip().rstrip("/")


def get_json(url: str, api_key: str = "") -> object:
    headers = {"Accept": FOREM_API_ACCEPT, "User-Agent": ONNELLAB_USER_AGENT}
    if api_key:
        headers["api-key"] = api_key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SyndicationPostingError(f"HTTP {error.code} from Dev.to") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise SyndicationPostingError("Dev.to verification request failed") from error


def authenticated_articles(api_key: str) -> list[dict[str, object]]:
    articles: list[dict[str, object]] = []
    for page in range(1, 101):
        query = urllib.parse.urlencode({"per_page": "100", "page": str(page)})
        payload = get_json(f"{API}/articles/me/all?{query}", api_key)
        if not isinstance(payload, list):
            raise SyndicationPostingError("Dev.to article inventory was not a list")
        page_items = [item for item in payload if isinstance(item, dict)]
        articles.extend(page_items)
        if len(page_items) < 100:
            return articles
    raise SyndicationPostingError("Dev.to article inventory exceeded pagination limit")


def public_article(post_id: str) -> dict[str, object]:
    payload = get_json(f"{API}/articles/{urllib.parse.quote(post_id, safe='')}")
    if not isinstance(payload, dict):
        raise SyndicationPostingError("Dev.to article verification was not an object")
    return payload


def verify_public_article(article: dict[str, object], canonical_url: str) -> tuple[str, str]:
    if normalized_url(article.get("canonical_url")) != normalized_url(canonical_url):
        raise SyndicationPostingError("Dev.to verification canonical URL mismatch")
    posted_url = str(article.get("url") or "").strip()
    published_at = str(article.get("published_at") or "").strip()
    if not posted_url or not published_at:
        raise SyndicationPostingError("Dev.to verification did not confirm a published URL and timestamp")
    return str(article.get("id") or ""), posted_url


def retry_devto_article(manifest_path: Path, topic_id: str, language: str = "en") -> dict[str, object]:
    validate_syndication_drafts(manifest_path)
    project_root = project_root_for_manifest(manifest_path)
    manifest = load_manifest(manifest_path)
    draft = selected_devto_draft(manifest, topic_id, language)
    if draft.get("status") not in {"failed", "draft", "approved"}:
        raise SyndicationPostingError(f"Dev.to draft is not retryable: {topic_id} {language}")
    try:
        _require_current_published_topic(project_root, draft)
    except TopicError as error:
        raise SyndicationPostingError("current published topic authority check failed") from error
    api_key = os.environ.get("DEVTO_API_KEY", "").strip()
    if not api_key:
        raise SyndicationPostingError("missing credentials for devto: DEVTO_API_KEY")
    canonical_url = str(draft.get("canonical_url") or "")
    try:
        matches = [item for item in authenticated_articles(api_key) if normalized_url(item.get("canonical_url")) == normalized_url(canonical_url)]
        if len(matches) > 1:
            raise SyndicationPostingError("multiple Dev.to articles matched the canonical URL")
        if not matches and str(draft.get("post_id") or "").strip():
            raise SyndicationPostingError("saved Dev.to post id has no canonical match")
        if len(matches) == 1:
            article = matches[0]
            post_id = str(article.get("id") or "").strip()
            if not post_id:
                raise SyndicationPostingError("matched Dev.to article has no id")
            draft["post_id"] = post_id
            if article.get("published_at"):
                verified_id, posted_url = verify_public_article(public_article(post_id), canonical_url)
            else:
                payload = devto_payload(draft, project_root)
                response = put_json(
                    f"{API}/articles/{urllib.parse.quote(post_id, safe='')}", payload,
                    {"api-key": api_key, "Accept": FOREM_API_ACCEPT, "User-Agent": ONNELLAB_USER_AGENT},
                )
                verified_id = str(response.get("id") or post_id)
                draft["post_id"] = verified_id
                write_manifest(manifest_path, manifest)
                verified_id, posted_url = verify_public_article(public_article(verified_id), canonical_url)
            draft["post_id"], draft["posted_url"] = verified_id, posted_url
        else:
            post_id, _ = post_devto_draft(draft, project_root)
            post_id = str(post_id)
            draft["post_id"] = post_id
            write_manifest(manifest_path, manifest)
            verified_id, posted_url = verify_public_article(public_article(post_id), canonical_url)
            draft["post_id"], draft["posted_url"] = verified_id, posted_url
        timestamp = datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()
        draft.update({"status": "posted", "posted_at": timestamp, "last_attempt_at": timestamp, "error": "", "error_type": ""})
        write_manifest(manifest_path, manifest)
        return draft
    except Exception as error:
        error_type = classify_posting_error(error)
        timestamp = datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()
        draft.update({"status": "failed", "last_attempt_at": timestamp, "error": f"Dev.to retry failed ({error_type})", "error_type": error_type, "retry_count": int(draft.get("retry_count") or 0) + 1})
        write_manifest(manifest_path, manifest)
        raise SyndicationPostingError(f"Dev.to retry failed ({error_type})") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry one selected Dev.to article safely")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    try:
        draft = retry_devto_article(args.manifest, args.topic_id, args.language)
    except (SyndicationPostingError, SyndicationValidationError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"posted Dev.to {draft['topic_id']} {draft['post_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
