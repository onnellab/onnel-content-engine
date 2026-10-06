#!/usr/bin/env python3
"""Verify the public /ops/ deployment without storing page contents or credentials."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTED = ROOT / "generated/manual-publish/index.html"
DEFAULT_OUTPUT = ROOT / "data/ops_live_verification.json"
REQUIRED_ROBOTS = "noindex,nofollow,noarchive,nosnippet,noimageindex"


def fetch(url: str, timeout: int = 20) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "ONNELLAB-Ops-Live-Verifier/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()

def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sitemap_locations(body: bytes, base_url: str) -> list[str]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    if root.tag.rsplit("}", 1)[-1] != "sitemapindex":
        return []
    urls = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
            continue
        url = urllib.parse.urljoin(base_url + "/", node.text.strip())
        parsed = urllib.parse.urlsplit(url)
        base = urllib.parse.urlsplit(base_url)
        if parsed.scheme == "https" and parsed.netloc == base.netloc:
            urls.append(url)
    return urls


def has_hidden_nav_link(html: str) -> bool:
    return bool(re.search(
        r'href=["\'][^"\']*(?:/ops/|/manual-publish/)[^"\']*["\']',
        html,
        flags=re.I,
    ))


def verify_once(expected: bytes, base_url: str, fetcher=fetch) -> dict[str, object]:
    base_url = base_url.rstrip("/")
    checks: dict[str, bool] = {}
    status, live = fetcher(base_url + "/ops/")
    checks["ops_http_200"] = status == 200
    checks["ops_exact_deployed_bytes"] = status == 200 and digest(live) == digest(expected)
    text = live.decode("utf-8", errors="replace")

    for bot in ("robots", "googlebot", "naverbot", "yeti"):
        checks[f"{bot}_meta"] = bool(re.search(
            rf'<meta\s+name=["\']{bot}["\']\s+content=["\']{re.escape(REQUIRED_ROBOTS)}["\']',
            text,
            flags=re.I,
        ))

    robots_status, robots = fetcher(base_url + "/robots.txt")
    robots_text = robots.decode("utf-8", errors="replace")
    checks["robots_http_200"] = robots_status == 200
    checks["robots_disallow_ops"] = "Disallow: /ops/" in robots_text
    checks["robots_disallow_legacy"] = "Disallow: /manual-publish/" in robots_text

    sitemap_status, sitemap, sitemap_url = 404, b"", ""
    for path in ("/sitemap.xml", "/sitemap-index.xml", "/sitemap-0.xml"):
        candidate_status, candidate_body = fetcher(base_url + path)
        if candidate_status == 200:
            sitemap_status, sitemap = candidate_status, candidate_body
            sitemap_url = base_url + path
            break
    sitemap_bodies = [sitemap] if sitemap_status == 200 else []
    if sitemap_status == 200:
        for child in sitemap_locations(sitemap, base_url):
            if child == sitemap_url:
                continue
            child_status, child_body = fetcher(child)
            if child_status == 200:
                sitemap_bodies.append(child_body)
    sitemap_text = b"\n".join(sitemap_bodies).decode("utf-8", errors="replace")
    checks["sitemap_available"] = sitemap_status == 200
    checks["ops_absent_from_sitemap"] = "/ops/" not in sitemap_text
    checks["legacy_absent_from_sitemap"] = "/manual-publish/" not in sitemap_text

    home_status, home = fetcher(base_url + "/")
    checks["homepage_http_200"] = home_status == 200
    checks["hidden_from_navigation"] = not has_hidden_nav_link(
        home.decode("utf-8", errors="replace")
    )
    legacy_status, _ = fetcher(base_url + "/manual-publish/")
    checks["legacy_route_absent"] = legacy_status in {404, 410}

    return {
        "state": "verified" if all(checks.values()) else "failed",
        "expected_sha256": digest(expected),
        "live_sha256": digest(live) if status == 200 else "",
        "checks": checks,
        "http": {
            "ops": status,
            "robots": robots_status,
            "sitemap": sitemap_status,
            "homepage": home_status,
            "legacy": legacy_status,
        },
    }


def run(
    expected_path: Path, output: Path, base_url: str, attempts: int, interval: float,
    deployment_sha: str = "",
) -> dict[str, object]:
    expected = expected_path.read_bytes()
    result: dict[str, object] = {}
    for attempt in range(1, attempts + 1):
        try:
            result = verify_once(expected, base_url)
        except (OSError, ValueError, ET.ParseError) as error:
            result = {
                "state": "failed",
                "checks": {},
                "error": f"live_ops_verification_error:{type(error).__name__}",
            }
        result["attempt"] = attempt
        if result.get("state") == "verified":
            break
        if attempt < attempts:
            time.sleep(interval)

    payload = {
        "schema_version": 1,
        "kind": "onnellab_ops_live_verification",
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "base_url": base_url.rstrip("/"),
        "deployment_sha": deployment_sha.strip(),
        **result,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default="https://onnellab.com")
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--deployment-sha", default="")
    args = parser.parse_args()
    if args.attempts < 1 or args.interval < 0:
        parser.error("attempts must be >= 1 and interval must be >= 0")
    payload = run(
        args.expected, args.output, args.base_url, args.attempts, args.interval,
        deployment_sha=args.deployment_sha,
    )
    print(json.dumps({
        "state": payload.get("state"),
        "attempt": payload.get("attempt"),
        "checks": payload.get("checks", {}),
    }, ensure_ascii=False))
    return 0 if payload.get("state") == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
