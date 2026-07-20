#!/usr/bin/env python3
"""Verify externally published manual posts and update dashboard done state."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOCIAL_MANIFEST = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION_MANIFEST = ROOT / "generated" / "syndication" / "manifest.json"
DEFAULT_STATE = ROOT / "data" / "manual_publish_state.json"
DEFAULT_REPORT = ROOT / "data" / "manual_publication_verification_report.json"
PUBLIC_API_BSKY = "https://public.api.bsky.app"
ONNELLAB_USER_AGENT = "ONNELLAB content engine"
DEFAULT_X_USERNAME = "onnellab"
DEFAULT_X_PUBLIC_PROFILE_URL = "https://x.com/onnellab"
DEFAULT_LINKEDIN_PUBLIC_PROFILE_URL = "https://www.linkedin.com/in/onnel-lab-b5b9b0421/"
DEFAULT_MEDIUM_USERNAME = "onnellab.app"
DEFAULT_HASHNODE_BLOG_URL = "https://onnellab.hashnode.dev"


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
        username = os.environ.get("MEDIUM_USERNAME", "").strip().lstrip("@") or DEFAULT_MEDIUM_USERNAME
        return f"https://medium.com/feed/@{username}" if username else ""
    if platform == "hashnode":
        explicit = os.environ.get("HASHNODE_RSS_URL", "").strip()
        if explicit:
            return explicit
        blog_url = os.environ.get("HASHNODE_BLOG_URL", "").strip().rstrip("/") or DEFAULT_HASHNODE_BLOG_URL
        return f"{blog_url}/rss.xml" if blog_url else ""
    return ""


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if xml_local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def rss_item_url(item: ET.Element, fallback_url: str) -> str:
    link = child_text(item, {"link"})
    if link.startswith("http://") or link.startswith("https://"):
        return link
    guid = child_text(item, {"guid", "id"})
    if guid.startswith("http://") or guid.startswith("https://"):
        return guid
    return fallback_url


def rss_matching_item_url(text: str, canonical_url: str, slug: str, fallback_url: str) -> str:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return fallback_url if ((canonical_url and canonical_url in text) or (slug and slug in text)) else ""
    for element in root.iter():
        if xml_local_name(element.tag) not in {"item", "entry"}:
            continue
        haystack = "\n".join(value.strip() for value in element.itertext() if value and value.strip())
        if (canonical_url and canonical_url in haystack) or (slug and slug in haystack):
            return rss_item_url(element, fallback_url)
    return ""


def verify_rss(item: dict[str, Any], fetch_text: FetchText) -> Verification | None:
    platform = str(item.get("platform", ""))
    url = rss_url_for(platform)
    if not url:
        return None
    text = fetch_text(url, None)
    canonical_url = str(item.get("canonical_url", ""))
    slug = str(item.get("slug", ""))
    posted_url = rss_matching_item_url(text, canonical_url, slug, url)
    if posted_url:
        return result_for(item, posted_url, f"{platform}_rss", "medium")
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
        return f"https://x.com/{username}" if username else DEFAULT_X_PUBLIC_PROFILE_URL
    if platform == "linkedin":
        return (
            os.environ.get("LINKEDIN_PUBLIC_PROFILE_URL", "").strip()
            or os.environ.get("LINKEDIN_PROFILE_URL", "").strip()
            or DEFAULT_LINKEDIN_PUBLIC_PROFILE_URL
        )
    return ""


def public_activity_url(platform: str, profile_url: str) -> str:
    if platform != "linkedin":
        return profile_url
    parsed = urllib.parse.urlparse(profile_url)
    path = parsed.path.rstrip("/")
    if "/recent-activity" in path:
        return profile_url
    if path:
        return urllib.parse.urlunparse(parsed._replace(path=f"{path}/recent-activity/all/"))
    return profile_url


def public_post_url_from_visual_text(platform: str, text: str, fallback_url: str) -> str:
    patterns = {
        "x": r"https?://(?:x|twitter)\.com/[^/\s\"')]+/status/\d+",
        "linkedin": r"https?://(?:www\.)?linkedin\.com/(?:feed/update/urn:li:[^/\s\"')]+|posts/[^/\s\"')]+)",
    }
    pattern = patterns.get(platform)
    if not pattern:
        return fallback_url
    match = re.search(pattern, text)
    return match.group(0) if match else fallback_url


def playwright_page_text(url: str) -> str:
    script = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(5000);
  await page.evaluate(() => window.scrollTo(0, Math.min(document.body.scrollHeight, 1800)));
  await page.waitForTimeout(1200);
  console.log(await page.evaluate(() => {
    const bodyText = document.body ? document.body.innerText : '';
    const links = Array.from(document.querySelectorAll('a[href]'))
      .map((link) => link.href)
      .filter(Boolean)
      .join('\\n');
    return bodyText + '\\n' + links;
  }));
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
    verification_url = public_activity_url(platform, url)
    text = visual_text(verification_url)
    canonical_url = str(item.get("canonical_url", ""))
    title = first_line_from_draft(item)
    canonical_host = urllib.parse.urlparse(canonical_url).netloc
    has_title = bool(title and title in text)
    has_canonical_url = bool(canonical_url and canonical_url in text)
    has_canonical_card = bool(canonical_host and canonical_host in text and has_title)
    if has_title and (has_canonical_url or has_canonical_card):
        posted_url = public_post_url_from_visual_text(platform, text, verification_url)
        return result_for(item, posted_url, f"{platform}_public_page_visual", "low")
    print(
        f"checked {platform} public page but found no matching title plus canonical URL or domain: {verification_url}",
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
    report_path: Path = DEFAULT_REPORT,
    visual_public_pages: bool = False,
    dry_run: bool = False,
    now: datetime | None = None,
    fetch_json: FetchJson = fetch_json_url,
    fetch_text: FetchText = fetch_text_url,
    visual_text: VisualText = playwright_page_text,
    retry_attempts: int = 1,
    retry_delay_seconds: float = 0,
) -> list[Verification]:
    state = load_json(state_path) or {"version": 1, "updated_at": "", "done": {}}
    items = load_items(social_manifest, syndication_manifest)
    verifications: list[Verification] = []
    already_done_items: list[dict[str, Any]] = []
    pending_items: list[dict[str, Any]] = []
    for item in items:
        if already_done(item, state):
            already_done_items.append(item)
            continue
        pending_items.append(item)
    attempts = max(1, retry_attempts)
    for attempt in range(attempts):
        next_pending: list[dict[str, Any]] = []
        for item in pending_items:
            verification = verify_item(item, fetch_json, fetch_text, visual_text, visual_public_pages)
            if verification:
                verifications.append(verification)
            else:
                next_pending.append(item)
        pending_items = next_pending
        if pending_items and attempt + 1 < attempts and retry_delay_seconds > 0:
            time.sleep(retry_delay_seconds)
    timestamp = (now or datetime.now(ZoneInfo("Asia/Seoul"))).replace(microsecond=0).isoformat()
    if verifications and not dry_run:
        update_state(state, verifications, datetime.fromisoformat(timestamp))
        write_json(state_path, state)
    if not dry_run:
        write_json(report_path, verification_report(items, already_done_items, verifications, pending_items, state, visual_public_pages, timestamp))
    return verifications


def pending_reason(item: dict[str, Any], visual_public_pages: bool) -> str:
    platform = str(item.get("platform", ""))
    if platform in {"medium", "hashnode"} and not rss_url_for(platform):
        return "RSS URL not configured"
    if platform in {"x", "linkedin"} and not visual_public_pages:
        return "Public profile visual check disabled"
    if item.get("error"):
        return str(item.get("error"))
    return "No matching public post found"


def report_item(
    item: dict[str, Any],
    status: str,
    reason: str = "",
    verification: Verification | None = None,
    done_record: dict[str, Any] | None = None,
) -> dict[str, str]:
    done_record = done_record or {}
    return {
        "manual_key": str(item.get("manual_key", verification.manual_key if verification else "")),
        "topic_id": str(item.get("topic_id", verification.topic_id if verification else "")),
        "platform": str(item.get("platform", verification.platform if verification else "")),
        "language": str(item.get("language", verification.language if verification else "")),
        "template_id": str(item.get("template_id", verification.template_id if verification else "")),
        "status": status,
        "reason": reason,
        "posted_url": verification.posted_url if verification else str(done_record.get("posted_url") or item.get("posted_url", "")),
        "verification_method": verification.method if verification else str(done_record.get("verification_method", "")),
        "verification_confidence": verification.confidence if verification else str(done_record.get("verification_confidence", "")),
    }


def verification_report(
    items: list[dict[str, Any]],
    already_done_items: list[dict[str, Any]],
    verifications: list[Verification],
    pending_items: list[dict[str, Any]],
    state: dict[str, Any],
    visual_public_pages: bool,
    checked_at: str,
) -> dict[str, Any]:
    verified_by_key = {verification.manual_key: verification for verification in verifications}
    rows: list[dict[str, str]] = []
    done_state = state.get("done", {}) if isinstance(state.get("done"), dict) else {}
    rows.extend(report_item(item, "already_done", done_record=done_state.get(str(item.get("manual_key", "")), {})) for item in already_done_items)
    rows.extend(report_item({"manual_key": key}, "verified", verification=verification) for key, verification in verified_by_key.items())
    rows.extend(report_item(item, "pending", pending_reason(item, visual_public_pages)) for item in pending_items)
    return {
        "version": 1,
        "checked_at": checked_at,
        "visual_public_pages": visual_public_pages,
        "counts": {
            "checked": len(items),
            "already_done": len(already_done_items),
            "verified": len(verifications),
            "pending": len(pending_items),
        },
        "items": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify manual publications and update dashboard state")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--visual-public-pages", action="store_true", help="Use Playwright to inspect public Twitter/LinkedIn pages")
    parser.add_argument("--retry-attempts", type=int, default=1, help="Retry pending public checks before reporting them")
    parser.add_argument("--retry-delay-seconds", type=float, default=0, help="Delay between public check retries")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        verifications = verify_manual_publications(
            args.social_manifest,
            args.syndication_manifest,
            args.state,
            args.report,
            visual_public_pages=args.visual_public_pages,
            dry_run=args.dry_run,
            retry_attempts=args.retry_attempts,
            retry_delay_seconds=args.retry_delay_seconds,
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
