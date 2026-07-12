#!/usr/bin/env python3
"""Post approved syndication drafts through a selectable adapter."""

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
from evaluate_syndication_drafts import DEFAULT_MANIFEST_PATH, frontmatter
from publishing_adapters import AdapterError, require_adapter_ready
from validate_syndication_drafts import SyndicationValidationError, project_root_for_manifest, validate_syndication_drafts


class SyndicationPostingError(ValueError):
    """Raised when approved syndication drafts cannot be posted."""


def classify_posting_error(error: Exception) -> str:
    message = str(error).lower()
    if "missing credentials" in message or "401" in message or "unauthorized" in message:
        return "auth"
    if "403" in message or "forbidden" in message or "permission" in message:
        return "permission"
    if "429" in message or "rate limit" in message or "too many requests" in message:
        return "rate_limited"
    if "400" in message or "422" in message or "validation" in message or "invalid" in message:
        return "validation"
    if "500" in message or "502" in message or "503" in message or "504" in message:
        return "server"
    return "transient"


def load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SyndicationPostingError(f"syndication manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def approved_drafts(manifest: dict[str, object], platform: str | None = None) -> list[dict[str, object]]:
    drafts = manifest.get("drafts")
    if not isinstance(drafts, list):
        raise SyndicationPostingError("syndication manifest has no drafts list")
    selected = [
        draft
        for draft in drafts
        if isinstance(draft, dict)
        and draft.get("status") == "approved"
        and draft.get("platform") != "medium"
        and (platform is None or draft.get("platform") == platform)
    ]
    seen: set[tuple[object, object, object]] = set()
    for draft in selected:
        key = (draft.get("topic_id"), draft.get("platform"), draft.get("language"))
        if key in seen:
            raise SyndicationPostingError(f"duplicate approved syndication draft: {key}")
        seen.add(key)
    return selected


def mock_post_url(draft: dict[str, object]) -> str:
    return f"https://example.com/mock-syndication/{draft['platform']}/{draft['language']}/{draft['topic_id']}"


def json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SyndicationPostingError(f"HTTP {error.code} from {url}: {detail}") from error


def markdown_body_without_frontmatter(content: str) -> str:
    if not content.startswith("---\n"):
        return content.strip()
    end = content.find("\n---\n", 4)
    if end == -1:
        return content.strip()
    return content[end + len("\n---\n") :].strip()


def devto_payload(draft: dict[str, object], project_root: Path) -> dict[str, object]:
    draft_path = project_root / str(draft["draft_path"])
    content = draft_path.read_text(encoding="utf-8")
    metadata = frontmatter(content)
    title = metadata.get("title")
    if not title:
        raise SyndicationPostingError(f"Dev.to draft has no title: {draft_path}")
    return {
        "article": {
            "title": title,
            "body_markdown": markdown_body_without_frontmatter(content),
            "published": metadata.get("published", "false").lower() == "true",
            "canonical_url": str(draft["canonical_url"]),
            "tags": metadata.get("tags", ""),
        }
    }


def post_devto_draft(draft: dict[str, object], project_root: Path) -> tuple[str, str]:
    api_key = os.environ["DEVTO_API_KEY"]
    response = json_post(
        "https://dev.to/api/articles",
        devto_payload(draft, project_root),
        {"api-key": api_key},
    )
    post_id = response.get("id")
    url = response.get("url")
    if not isinstance(post_id, int | str):
        raise SyndicationPostingError("Dev.to response did not include id")
    if not isinstance(url, str) or not url:
        url = f"https://dev.to/dashboard/{post_id}"
    return str(post_id), url


HASHNODE_CREATE_DRAFT_MUTATION = """
mutation CreateDraft($input: CreateDraftInput!) {
  createDraft(input: $input) {
    draft {
      id
    }
  }
}
""".strip()


def hashnode_tags(value: str) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    for tag in value.split(","):
        slug = tag.strip()
        if slug:
            tags.append({"slug": slug, "name": slug})
    return tags


def hashnode_payload(draft: dict[str, object], project_root: Path) -> dict[str, object]:
    draft_path = project_root / str(draft["draft_path"])
    content = draft_path.read_text(encoding="utf-8")
    metadata = frontmatter(content)
    title = metadata.get("title")
    if not title:
        raise SyndicationPostingError(f"Hashnode draft has no title: {draft_path}")
    publication_id = os.environ.get("HASHNODE_PUBLICATION_ID") or metadata.get("publication_id", "")
    input_payload: dict[str, object] = {
        "title": title,
        "publicationId": publication_id,
        "contentMarkdown": markdown_body_without_frontmatter(content),
        "slug": str(draft["slug"]),
        "originalArticleURL": str(draft["canonical_url"]),
        "tags": hashnode_tags(metadata.get("tags", "")),
        "settings": {
            "enableTableOfContent": True,
            "activateNewsletter": False,
        },
    }
    cover_image = metadata.get("cover_image")
    if cover_image:
        input_payload["coverImageOptions"] = {
            "coverImageURL": cover_image,
            "isCoverAttributionHidden": True,
        }
    return {"query": HASHNODE_CREATE_DRAFT_MUTATION, "variables": {"input": input_payload}}


def post_hashnode_draft(draft: dict[str, object], project_root: Path) -> tuple[str, str]:
    response = json_post(
        "https://gql.hashnode.com",
        hashnode_payload(draft, project_root),
        {"Authorization": os.environ["HASHNODE_TOKEN"]},
    )
    errors = response.get("errors")
    if errors:
        raise SyndicationPostingError(f"Hashnode GraphQL errors: {errors}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise SyndicationPostingError("Hashnode response did not include data")
    create_draft = data.get("createDraft")
    if not isinstance(create_draft, dict):
        raise SyndicationPostingError("Hashnode response did not include createDraft")
    draft_data = create_draft.get("draft")
    if not isinstance(draft_data, dict):
        raise SyndicationPostingError("Hashnode response did not include draft")
    draft_id = draft_data.get("id")
    if not isinstance(draft_id, str) or not draft_id:
        raise SyndicationPostingError("Hashnode response did not include draft id")
    return draft_id, f"https://hashnode.com/draft/{draft_id}"


def post_syndication_drafts(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    platform: str | None = None,
    adapter: str = "mock",
    dry_run: bool = False,
    verbose: bool = False,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    project_root = project_root_for_manifest(manifest_path)
    validate_syndication_drafts(manifest_path, project_root)
    manifest = load_manifest(manifest_path)
    if adapter != "mock" and platform is None and adapter in {"devto", "hashnode"}:
        platform = adapter
    drafts = approved_drafts(manifest, platform)
    timestamp = (now or datetime.now(ZoneInfo("Asia/Seoul"))).replace(microsecond=0).isoformat()
    if dry_run:
        if verbose:
            for draft in drafts:
                if adapter == "devto":
                    payload = devto_payload(draft, project_root)
                elif adapter == "hashnode":
                    payload = hashnode_payload(draft, project_root)
                else:
                    payload = {}
                print(
                    json.dumps(
                        {
                            "adapter": adapter,
                            "platform": draft["platform"],
                            "topic_id": draft["topic_id"],
                            "language": draft["language"],
                            "payload": payload,
                        },
                        ensure_ascii=False,
                    )
                )
        return drafts
    try:
        require_adapter_ready(adapter, "syndication")
    except AdapterError as error:
        raise SyndicationPostingError(str(error)) from error
    for draft in drafts:
        draft["last_attempt_at"] = timestamp
        try:
            if adapter == "mock":
                post_id = f"mock-{draft['topic_id']}-{draft['platform']}-{draft['language']}"
                posted_url = mock_post_url(draft)
            elif adapter == "devto":
                if draft.get("platform") != "devto":
                    raise SyndicationPostingError(f"adapter devto cannot post platform {draft.get('platform')}")
                post_id, posted_url = post_devto_draft(draft, project_root)
            elif adapter == "hashnode":
                if draft.get("platform") != "hashnode":
                    raise SyndicationPostingError(f"adapter hashnode cannot post platform {draft.get('platform')}")
                post_id, posted_url = post_hashnode_draft(draft, project_root)
            else:
                raise SyndicationPostingError(f"adapter {adapter} is not implemented yet")
            draft["status"] = "posted"
            draft["posted_at"] = timestamp
            draft["post_id"] = post_id
            draft["posted_url"] = posted_url
            draft["error"] = ""
            draft["error_type"] = ""
        except Exception as error:
            draft["status"] = "failed"
            draft["error"] = str(error)
            draft["error_type"] = classify_posting_error(error)
            draft["retry_count"] = int(draft.get("retry_count") or 0) + 1
            write_manifest(manifest_path, manifest)
            raise
    write_manifest(manifest_path, manifest)
    return drafts


def main() -> int:
    parser = argparse.ArgumentParser(description="Post approved syndication drafts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--platform", choices=("devto", "hashnode"))
    parser.add_argument("--adapter", default="mock", choices=("mock", "devto", "hashnode", "medium"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Print dry-run payload details")
    args = parser.parse_args()
    try:
        drafts = post_syndication_drafts(args.manifest, args.platform, args.adapter, args.dry_run, args.verbose)
    except (SyndicationPostingError, SyndicationValidationError, OSError, json.JSONDecodeError) as error:
        print(f"syndication posting failed: {error}", file=sys.stderr)
        return 1
    action = "would post" if args.dry_run else "posted"
    print(f"{action} {len(drafts)} approved syndication draft(s)")
    for draft in drafts:
        print(f"{draft['topic_id']} {draft['platform']} {draft['language']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
