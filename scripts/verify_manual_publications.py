#!/usr/bin/env python3
"""Verify externally published manual posts and update dashboard done state."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOCIAL_MANIFEST = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION_MANIFEST = ROOT / "generated" / "syndication" / "manifest.json"
DEFAULT_STATE = ROOT / "data" / "manual_publish_state.json"
PUBLIC_API_BSKY = "https://public.api.bsky.app"
ONNELLAB_USER_AGENT = "ONNELLAB content engine"
DEFAULT_X_USERNAME = "onnellab"


class PublicationVerificationError(ValueError):
    """Raised when publication verification cannot proceed."""


@dataclass(frozen=True)
class Verification:
    manual_key: str
    topic_id: str
    platform: str
    language: str
    template_id: str
    posted_url: str
    method: str
    confidence: str


FetchJson = Callable[[str, dict[str, str] | None], Any]
FetchText = Callable[[str, dict[str, str] | None], str]
VisualText = Callable[[str], str]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def request_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    base = {"User-Agent": ONNELLAB_USER_AGENT, "Accept": "application/json,text/html,application/rss+xml,*/*"}
    if headers:
        base.update(headers)
    return base


def fetch_json_url(url: str, headers: dict[str, str] | None = None) -> Any:
    request = urllib.request.Request(url, headers=request_headers(headers))
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text_url(url: str, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, headers=request_headers(headers))
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def item_key(item: dict[str, Any]) -> str:
    return "::".join(
        [
            str(item.get("topic_id", "")),
            str(item.get("platform", "")),
            str(item.get("language", "")),
            str(item.get("template_id", "")),
        ]
    )


def load_items(social_manifest: Path, syndication_manifest: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    social = load_json(social_manifest)
    for post in social.get("posts", []):
        if isinstance(post, dict) and not post.get("is_variant"):
            item = dict(post)
            item["kind"] = "social"
            item["manual_key"] = item_key(item)
            items.append(item)
    syndication = load_json(syndication_manifest)
    for draft in syndication.get("drafts", []):
        if isinstance(draft, dict):
            item = dict(draft)
            item["kind"] = "syndication"
            item["template_id"] = "markdown"
            item["manual_key"] = item_key(item)
            items.append(item)
    return items


def strings_in(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(strings_in(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(strings_in(item))
        return result
    return []


def bsky_post_url(handle: str, uri: str) -> str:
    rkey = uri.rstrip("/").split("/")[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def verify_bluesky(item: dict[str, Any], fetch_json: FetchJson) -> Verification | None:
    handle = os.environ.get("BLUESKY_HANDLE", "onnellab.bsky.social")
    query = urllib.parse.urlencode({"actor": handle, "limit": "100", "filter": "posts_with_replies"})
    data = fetch_json(f"{PUBLIC_API_BSKY}/xrpc/app.bsky.feed.getAuthorFeed?{query}", None)
    canonical_url = str(item.get("canonical_url", ""))
    for row in data.get("feed", []) if isinstance(data, dict) else []:
        post = row.get("post", {}) if isinstance(row, dict) else {}
        if canonical_url and canonical_url in "\n".join(strings_in(post)):
            uri = str(post.get("uri", ""))
            return result_for(item, bsky_post_url(handle, uri) if uri else canonical_url, "bluesky_author_feed", "high")
    return None


def verify_devto(item: dict[str, Any], fetch_json: FetchJson) -> Verification | None:
    username = os.environ.get("DEVTO_USERNAME", "onnellab")
    query = urllib.parse.urlencode({"username": username, "per_page": "100", "state": "all"})
    data = fetch_json(f"https://dev.to/api/articles?{query}", None)
    canonical_url = str(item.get("canonical_url", ""))
    for article in data if isinstance(data, list) else []:
        if not isinstance(article, dict):
            continue
        haystack = "\n".join(strings_in(article))
        if canonical_url and canonical_url in haystack:
            posted_url = str(article.get("url") or canonical_url)
            return result_for(item, posted_url, "devto_public_articles", "high")
    return None


def rss_url_for(platform: str) -> str:
    if platform == "medium":
        explicit = os.environ.get("MEDIUM_RSS_URL", "").strip()
        if explicit:
            return explicit
        username = os.environ.get("MEDIUM_USERNAME", "").strip().lstrip("@")
        return f"https://medium.com/feed/@{username}" if username else ""
    if platform == "hashnode":
        explicit = os.environ.get("HASHNODE_RSS_URL", "").strip()
        if explicit:
            return explicit
        blog_url = os.environ.get("HASHNODE_BLOG_URL", "").strip().rstrip("/")
        return f"{blog_url}/rss.xml" if blog_url else ""
    return ""


def verify_rss(item: dict[str, Any], fetch_text: FetchText) -> Verification | None:
    platform = str(item.get("platform", ""))
    url = rss_url_for(platform)
    if not url:
        return None
    text = fetch_text(url, None)
    canonical_url = str(item.get("canonical_url", ""))
    slug = str(item.get("slug", ""))
    if (canonical_url and canonical_url in text) or (slug and slug in text):
        return result_for(item, url, f"{platform}_rss", "medium")
    return None


def public_profile_url(platform: str) -> str:
    if platform == "x":
        explicit = os.environ.get("X_PUBLIC_PROFILE_URL", "").strip() or os.environ.get("TWITTER_PUBLIC_PROFILE_URL", "").strip()
        if explicit:
            return explicit
        username = (
            os.environ.get("X_USERNAME", "").strip().lstrip("@")
            or os.environ.get("TWITTER_USERNAME", "").strip().lstrip("@")
            or DEFAULT_X_USERNAME
        )
        return f"https://x.com/{username}" if username else ""
    if platform == "linkedin":
        return os.environ.get("LINKEDIN_PUBLIC_PROFILE_URL", "").strip() or os.environ.get("LINKEDIN_PROFILE_URL", "").strip()
    return ""


def playwright_page_text(url: str) -> str:
    script = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2500);
  console.log(await page.evaluate(() => document.body ? document.body.innerText : ''));
  await browser.close();
})().catch((error) => {
  console.error(String(error && error.stack || error));
  process.exit(2);
});
""".strip()
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", dir=ROOT, delete=False) as handle:
        handle.write(script)
        path = Path(handle.name)
    try:
        completed = subprocess.run(["node", str(path), url], check=True, text=True, capture_output=True, timeout=60)
        return completed.stdout
    finally:
        path.unlink(missing_ok=True)


def verify_public_page(item: dict[str, Any], visual_text: VisualText) -> Verification | None:
    platform = str(item.get("platform", ""))
    url = public_profile_url(platform)
    if not url:
        print(f"skip {platform} public page verification: profile URL is not configured", file=sys.stderr)
        return None
    text = visual_text(url)
    canonical_url = str(item.get("canonical_url", ""))
    slug = str(item.get("slug", ""))
    title = first_line_from_draft(item)
    if (canonical_url and canonical_url in text) or (slug and slug in text) or (title and title in text):
        return result_for(item, url, f"{platform}_public_page_visual", "low")
    print(
        f"checked {platform} public page but found no matching canonical URL, slug, or title: {url}",
        file=sys.stderr,
    )
    return None


def first_line_from_draft(item: dict[str, Any]) -> str:
    draft_path = ROOT / str(item.get("draft_path", ""))
    if not draft_path.exists():
        return ""
    for line in draft_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().strip("#").strip()
        if stripped and not stripped.startswith("---"):
            return stripped
    return ""


def result_for(item: dict[str, Any], posted_url: str, method: str, confidence: str) -> Verification:
    return Verification(
        manual_key=str(item["manual_key"]),
        topic_id=str(item.get("topic_id", "")),
        platform=str(item.get("platform", "")),
        language=str(item.get("language", "")),
        template_id=str(item.get("template_id", "")),
        posted_url=posted_url,
        method=method,
        confidence=confidence,
    )


def verify_item(
    item: dict[str, Any],
    fetch_json: FetchJson = fetch_json_url,
    fetch_text: FetchText = fetch_text_url,
    visual_text: VisualText = playwright_page_text,
    visual_public_pages: bool = False,
) -> Verification | None:
    platform = item.get("platform")
    try:
        if platform == "bluesky":
            return verify_bluesky(item, fetch_json)
        if platform == "devto":
            return verify_devto(item, fetch_json)
        if platform in {"medium", "hashnode"}:
            return verify_rss(item, fetch_text)
        if platform in {"x", "linkedin"} and visual_public_pages:
            return verify_public_page(item, visual_text)
    except (urllib.error.URLError, TimeoutError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as error:
        print(f"skip {platform} verification after error: {error}", file=sys.stderr)
        return None
    return None


def already_done(item: dict[str, Any], state: dict[str, Any]) -> bool:
    if item.get("status") == "posted":
        return True
    return str(item.get("manual_key", "")) in state.get("done", {})


def update_state(state: dict[str, Any], verifications: list[Verification], now: datetime) -> dict[str, Any]:
    state.setdefault("version", 1)
    state.setdefault("done", {})
    timestamp = now.replace(microsecond=0).isoformat()
    for verification in verifications:
        state["done"][verification.manual_key] = {
            "topic_id": verification.topic_id,
            "platform": verification.platform,
            "language": verification.language,
            "template_id": verification.template_id,
            "marked_at": timestamp,
            "marked_by": "publication_verifier",
            "posted_url": verification.posted_url,
            "verified_at": timestamp,
            "verification_method": verification.method,
            "verification_confidence": verification.confidence,
        }
    state["updated_at"] = timestamp
    return state


def verify_manual_publications(
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    state_path: Path = DEFAULT_STATE,
    visual_public_pages: bool = False,
    dry_run: bool = False,
    now: datetime | None = None,
    fetch_json: FetchJson = fetch_json_url,
    fetch_text: FetchText = fetch_text_url,
    visual_text: VisualText = playwright_page_text,
) -> list[Verification]:
    state = load_json(state_path) or {"version": 1, "updated_at": "", "done": {}}
    items = load_items(social_manifest, syndication_manifest)
    verifications: list[Verification] = []
    for item in items:
        if already_done(item, state):
            continue
        verification = verify_item(item, fetch_json, fetch_text, visual_text, visual_public_pages)
        if verification:
            verifications.append(verification)
    if verifications and not dry_run:
        update_state(state, verifications, now or datetime.now(ZoneInfo("Asia/Seoul")))
        write_json(state_path, state)
    return verifications


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify manual publications and update dashboard state")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--visual-public-pages", action="store_true", help="Use Playwright to inspect public Twitter/LinkedIn pages")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        verifications = verify_manual_publications(
            args.social_manifest,
            args.syndication_manifest,
            args.state,
            visual_public_pages=args.visual_public_pages,
            dry_run=args.dry_run,
        )
    except (PublicationVerificationError, OSError, json.JSONDecodeError) as error:
        print(f"publication verification failed: {error}", file=sys.stderr)
        return 1
    for verification in verifications:
        action = "would verify" if args.dry_run else "verified"
        print(f"{action} {verification.manual_key} via {verification.method}: {verification.posted_url}")
    if not verifications:
        print("no new publications verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
