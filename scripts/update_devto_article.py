#!/usr/bin/env python3
"""Update an existing Dev.to article from the syndication manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from approve_syndication_draft import write_manifest
from post_syndication_drafts import FOREM_API_ACCEPT, ONNELLAB_USER_AGENT, SyndicationPostingError, devto_payload, load_manifest
from validate_syndication_drafts import SyndicationValidationError, project_root_for_manifest, validate_syndication_drafts


DEFAULT_MANIFEST_PATH = Path("generated/syndication/manifest.json")


def put_json(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SyndicationPostingError(f"HTTP {error.code} from {url}: {detail}") from error


def selected_devto_draft(manifest: dict[str, object], topic_id: str, language: str) -> dict[str, object]:
    drafts = manifest.get("drafts")
    if not isinstance(drafts, list):
        raise SyndicationPostingError("syndication manifest has no drafts list")
    for draft in drafts:
        if (
            isinstance(draft, dict)
            and draft.get("platform") == "devto"
            and draft.get("topic_id") == topic_id
            and draft.get("language") == language
        ):
            return draft
    raise SyndicationPostingError(f"Dev.to draft not found: {topic_id} {language}")


def update_devto_article(manifest_path: Path, topic_id: str, language: str) -> dict[str, object]:
    validate_syndication_drafts(manifest_path)
    project_root = project_root_for_manifest(manifest_path)
    manifest = load_manifest(manifest_path)
    draft = selected_devto_draft(manifest, topic_id, language)
    post_id = str(draft.get("post_id") or "").strip()
    if not post_id:
        raise SyndicationPostingError(f"Dev.to draft has no post_id: {topic_id} {language}")
    api_key = os.environ.get("DEVTO_API_KEY", "").strip()
    if not api_key:
        raise SyndicationPostingError("missing credentials for devto: DEVTO_API_KEY")
    payload = devto_payload(draft, project_root)
    article = payload.get("article")
    if not isinstance(article, dict) or article.get("published") is not True:
        raise SyndicationPostingError("Dev.to update payload is not public")
    response = put_json(
        f"https://dev.to/api/articles/{post_id}",
        payload,
        {"api-key": api_key, "Accept": FOREM_API_ACCEPT, "User-Agent": ONNELLAB_USER_AGENT},
    )
    timestamp = datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()
    draft["status"] = "posted"
    draft["posted_at"] = timestamp
    draft["last_attempt_at"] = timestamp
    draft["post_id"] = str(response.get("id") or post_id)
    draft["posted_url"] = str(response.get("url") or draft.get("posted_url") or "")
    draft["error"] = ""
    draft["error_type"] = ""
    write_manifest(manifest_path, manifest)
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description="Update an existing Dev.to article from generated syndication content")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--topic-id", default="TOPIC-0001")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    try:
        draft = update_devto_article(args.manifest, args.topic_id, args.language)
    except (SyndicationPostingError, SyndicationValidationError, OSError, json.JSONDecodeError) as error:
        print(f"Dev.to update failed: {error}", file=sys.stderr)
        return 1
    print(f"updated devto article {draft['post_id']} {draft['posted_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
