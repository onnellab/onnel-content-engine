#!/usr/bin/env python3
"""Post approved social drafts through a selectable adapter.

The mock adapter updates the manifest without calling external APIs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from approve_social_post import project_root_for_manifest, write_manifest
from publishing_adapters import AdapterError, require_adapter_ready
from validate_social_posts import DEFAULT_MANIFEST_PATH, SocialValidationError, validate_social_posts


UTC = timezone.utc


class SocialPostingError(ValueError):
    """Raised when approved social drafts cannot be posted."""


URL_RE = re.compile(r"https?://[^\s<>()]+")
TRAILING_URL_PUNCTUATION = ".,;:!?"


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
        raise SocialPostingError(f"social manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def approved_posts(manifest: dict[str, object], platform: str | None = None) -> list[dict[str, object]]:
    posts = manifest.get("posts")
    if not isinstance(posts, list):
        raise SocialPostingError("social manifest has no posts list")
    selected = [
        post
        for post in posts
        if isinstance(post, dict)
        and post.get("status") == "approved"
        and (platform is None or post.get("platform") == platform)
    ]
    seen: set[tuple[object, object, object, object]] = set()
    for post in selected:
        key = (post.get("topic_id"), post.get("platform"), post.get("language"), post.get("template_id"))
        if key in seen:
            raise SocialPostingError(f"duplicate approved social draft: {key}")
        seen.add(key)
    return selected


def mock_post_url(post: dict[str, object]) -> str:
    return (
        "https://example.com/mock-social/"
        f"{post['platform']}/{post['language']}/{post['topic_id']}/{post['template_id']}"
    )


def x_payload(post: dict[str, object], project_root: Path) -> dict[str, object]:
    draft_path = project_root / str(post["draft_path"])
    return {"text": draft_path.read_text(encoding="utf-8").strip()}


def json_post(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SocialPostingError(f"HTTP {error.code} from {url}: {detail}") from error


def form_post(url: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict[str, object]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SocialPostingError(f"HTTP {error.code} from {url}: {detail}") from error


def binary_post(url: str, data: bytes, content_type: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    request_headers = {"Content-Type": content_type}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SocialPostingError(f"HTTP {error.code} from {url}: {detail}") from error


def bluesky_service_url() -> str:
    return os.environ.get("BLUESKY_SERVICE", "https://bsky.social").rstrip("/")


def bluesky_post_url(handle: str, uri: str) -> str:
    rkey = uri.rstrip("/").split("/")[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def x_post_url(post_id: str) -> str:
    return f"https://x.com/i/web/status/{post_id}"


def x_basic_auth_header() -> str:
    credentials = f"{os.environ['X_CLIENT_ID']}:{os.environ['X_CLIENT_SECRET']}".encode("utf-8")
    return f"Basic {base64.b64encode(credentials).decode('ascii')}"


def x_refresh_token() -> str:
    token_file = os.environ.get("X_REFRESH_TOKEN_FILE", "").strip()
    if token_file:
        path = Path(token_file)
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
    return os.environ["X_REFRESH_TOKEN"]


def persist_x_refresh_token(refresh_token: str, previous_refresh_token: str) -> None:
    if refresh_token == previous_refresh_token:
        return
    token_file = os.environ.get("X_REFRESH_TOKEN_FILE", "").strip()
    if token_file:
        path = Path(token_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{refresh_token}\n", encoding="utf-8")
        return
    print("X OAuth returned a rotated refresh token. Update X_REFRESH_TOKEN in your secret store.", file=sys.stderr)


def refresh_x_access_token() -> tuple[str, str]:
    current_refresh_token = x_refresh_token()
    response = form_post(
        "https://api.x.com/2/oauth2/token",
        {
            "grant_type": "refresh_token",
            "refresh_token": current_refresh_token,
            "client_id": os.environ["X_CLIENT_ID"],
        },
        {"Authorization": x_basic_auth_header()},
    )
    access_token = response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise SocialPostingError("X OAuth refresh response did not include access_token")
    refresh_token = response.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        refresh_token = current_refresh_token
    persist_x_refresh_token(refresh_token, current_refresh_token)
    return access_token, refresh_token


def post_x_text(post: dict[str, object], project_root: Path) -> tuple[str, str]:
    access_token, _refresh_token = refresh_x_access_token()
    response = json_post(
        "https://api.x.com/2/tweets",
        x_payload(post, project_root),
        {"Authorization": f"Bearer {access_token}"},
    )
    errors = response.get("errors")
    if errors:
        raise SocialPostingError(f"X API errors: {errors}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise SocialPostingError("X response did not include data")
    post_id = data.get("id")
    if not isinstance(post_id, str) or not post_id:
        raise SocialPostingError("X response did not include post id")
    return post_id, x_post_url(post_id)


def bluesky_link_facets(text: str) -> list[dict[str, object]]:
    facets: list[dict[str, object]] = []
    for match in URL_RE.finditer(text):
        uri = match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        if not uri:
            continue
        start = match.start()
        end = start + len(uri)
        facets.append(
            {
                "index": {
                    "byteStart": len(text[:start].encode("utf-8")),
                    "byteEnd": len(text[:end].encode("utf-8")),
                },
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#link",
                        "uri": uri,
                    }
                ],
            }
        )
    return facets


def bluesky_external_card_metadata(post: dict[str, object], project_root: Path) -> dict[str, object]:
    draft_path = project_root / str(post["draft_path"])
    lines = [line.strip() for line in draft_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    non_url_lines = [line for line in lines if not URL_RE.fullmatch(line)]
    title = non_url_lines[0] if non_url_lines else str(post["slug"])
    description = non_url_lines[1] if len(non_url_lines) > 1 else title
    return {
        "uri": str(post["canonical_url"]),
        "title": title[:300],
        "description": description[:300],
        "thumb_path": str(post["card_asset_path"]),
    }


def upload_bluesky_card_thumb(post: dict[str, object], project_root: Path, service: str, access_jwt: str) -> dict[str, object]:
    card_path = project_root / str(post["card_asset_path"])
    response = binary_post(
        f"{service}/xrpc/com.atproto.repo.uploadBlob",
        card_path.read_bytes(),
        "image/png",
        {"Authorization": f"Bearer {access_jwt}"},
    )
    blob = response.get("blob")
    if not isinstance(blob, dict) or not blob:
        raise SocialPostingError("Bluesky uploadBlob response did not include blob")
    return blob


def bluesky_external_embed(
    post: dict[str, object],
    project_root: Path,
    service: str,
    access_jwt: str,
) -> dict[str, object]:
    metadata = bluesky_external_card_metadata(post, project_root)
    return {
        "$type": "app.bsky.embed.external",
        "external": {
            "uri": metadata["uri"],
            "title": metadata["title"],
            "description": metadata["description"],
            "thumb": upload_bluesky_card_thumb(post, project_root, service, access_jwt),
        },
    }


def bluesky_record(
    text: str,
    language: str,
    created_at: str,
    embed: dict[str, object] | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": created_at,
        "langs": [language],
    }
    facets = bluesky_link_facets(text)
    if facets:
        record["facets"] = facets
    if embed:
        record["embed"] = embed
    return record


def build_bluesky_record_for_post(
    post: dict[str, object],
    project_root: Path,
    created_at: str,
    embed: dict[str, object] | None = None,
) -> dict[str, object]:
    draft_path = project_root / str(post["draft_path"])
    text = draft_path.read_text(encoding="utf-8").strip()
    return bluesky_record(text, str(post["language"]), created_at, embed)


def post_bluesky_text(post: dict[str, object], project_root: Path, timestamp: str) -> tuple[str, str]:
    handle = os.environ["BLUESKY_HANDLE"]
    password = os.environ["BLUESKY_APP_PASSWORD"]
    service = bluesky_service_url()
    session = json_post(
        f"{service}/xrpc/com.atproto.server.createSession",
        {"identifier": handle, "password": password},
    )
    access_jwt = session.get("accessJwt")
    if not isinstance(access_jwt, str) or not access_jwt:
        raise SocialPostingError("Bluesky createSession response did not include accessJwt")
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    embed = bluesky_external_embed(post, project_root, service, access_jwt)
    response = json_post(
        f"{service}/xrpc/com.atproto.repo.createRecord",
        {
            "repo": handle,
            "collection": "app.bsky.feed.post",
            "record": build_bluesky_record_for_post(post, project_root, created_at, embed),
        },
        {"Authorization": f"Bearer {access_jwt}"},
    )
    uri = response.get("uri")
    if not isinstance(uri, str) or not uri:
        raise SocialPostingError("Bluesky createRecord response did not include uri")
    return uri, bluesky_post_url(handle, uri)


def post_social_drafts(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    platform: str | None = None,
    adapter: str = "mock",
    dry_run: bool = False,
    verbose: bool = False,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    project_root = project_root_for_manifest(manifest_path)
    validate_social_posts(manifest_path, project_root)
    manifest = load_manifest(manifest_path)
    if adapter != "mock" and platform is None and adapter in {"bluesky", "x", "linkedin"}:
        platform = adapter
    posts = approved_posts(manifest, platform)
    timestamp = (now or datetime.now(ZoneInfo("Asia/Seoul"))).replace(microsecond=0).isoformat()
    if dry_run:
        if verbose:
            for post in posts:
                draft_path = project_root / str(post["draft_path"])
                text = draft_path.read_text(encoding="utf-8").strip()
                print(
                    json.dumps(
                        {
                            "adapter": adapter,
                            "platform": post["platform"],
                            "topic_id": post["topic_id"],
                            "language": post["language"],
                            "handle": os.environ.get("BLUESKY_HANDLE", "") if adapter == "bluesky" else "",
                            "text": text,
                            "record": bluesky_record(
                                text,
                                str(post["language"]),
                                timestamp,
                            )
                            if adapter == "bluesky"
                            else {},
                            "payload": x_payload(post, project_root) if adapter == "x" else {},
                            "external_card": bluesky_external_card_metadata(post, project_root)
                            if adapter == "bluesky"
                            else {},
                        },
                        ensure_ascii=False,
                    )
                )
        return posts
    try:
        require_adapter_ready(adapter, "social")
    except AdapterError as error:
        raise SocialPostingError(str(error)) from error
    for post in posts:
        post["last_attempt_at"] = timestamp
        try:
            if adapter == "mock":
                post_id = f"mock-{post['topic_id']}-{post['platform']}-{post['language']}-{post['template_id']}"
                posted_url = mock_post_url(post)
            elif adapter == "x":
                if post.get("platform") != "x":
                    raise SocialPostingError(f"adapter x cannot post platform {post.get('platform')}")
                post_id, posted_url = post_x_text(post, project_root)
            elif adapter == "bluesky":
                if post.get("platform") != "bluesky":
                    raise SocialPostingError(f"adapter bluesky cannot post platform {post.get('platform')}")
                post_id, posted_url = post_bluesky_text(post, project_root, timestamp)
            else:
                raise SocialPostingError(f"adapter {adapter} is not implemented yet")
            post["status"] = "posted"
            post["posted_at"] = timestamp
            post["post_id"] = post_id
            post["posted_url"] = posted_url
            post["error"] = ""
            post["error_type"] = ""
        except Exception as error:
            post["status"] = "failed"
            post["error"] = str(error)
            post["error_type"] = classify_posting_error(error)
            post["retry_count"] = int(post.get("retry_count") or 0) + 1
            write_manifest(manifest_path, manifest)
            raise
    write_manifest(manifest_path, manifest)
    return posts


def main() -> int:
    parser = argparse.ArgumentParser(description="Post approved social drafts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--platform", choices=("x", "linkedin", "bluesky"))
    parser.add_argument("--adapter", default="mock", choices=("mock", "bluesky", "x", "linkedin"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Print dry-run payload details")
    args = parser.parse_args()
    try:
        posts = post_social_drafts(args.manifest, args.platform, args.adapter, args.dry_run, args.verbose)
    except (SocialPostingError, SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social posting failed: {error}", file=sys.stderr)
        return 1
    action = "would post" if args.dry_run else "posted"
    print(f"{action} {len(posts)} approved social draft(s)")
    for post in posts:
        print(f"{post['topic_id']} {post['platform']} {post['language']} {post['template_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
