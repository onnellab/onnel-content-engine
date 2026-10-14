#!/usr/bin/env python3
"""Verify public app-detail HTML and exact artwork bytes after existing deployment.

The checked-in manifest remains staged_not_published. This separately retained
receipt is the only deployed_verified claim; a successful git push is not one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

LOCALES = {"en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class Gallery(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.images: list[str] = []
        self.dimensions: list[list[int] | None] = []
        self.identity: list[tuple[str | None, str | None]] = []

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        attrs = dict(attributes)
        if tag == "main" and "data-product-slug" in attrs:
            self.identity.append((attrs.get("data-product-slug"), attrs.get("data-product-locale")))
        in_gallery = any(gallery for _, gallery in self.stack) or "data-screenshot-row" in attrs
        if tag == "img" and in_gallery:
            if not attrs.get("src") or attrs.get("srcset"):
                raise ValueError("Expected exact static screenshot src without transformed variants")
            self.images.append(str(attrs["src"]))
            width, height = attrs.get("width") or "", attrs.get("height") or ""
            self.dimensions.append([int(width), int(height)] if all(
                re.fullmatch(r"[1-9][0-9]*", value) for value in (width, height)) else None)
        if tag not in VOID:
            self.stack.append((tag, in_gallery))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def public_get(url: str, *, deadline: float | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ONNELLAB artwork verifier",
                                                   "Cache-Control": "no-cache"})
    remaining = 30 if deadline is None else min(30, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Artwork deployment verification deadline elapsed")
    with urllib.request.urlopen(request, timeout=remaining) as response:
        if urllib.parse.urlsplit(response.url).netloc != urllib.parse.urlsplit(url).netloc:
            raise ValueError("Unexpected cross-origin redirect")
        value = bytearray()
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Artwork deployment verification deadline elapsed")
            chunk = response.read1(64 * 1024)
            if not chunk:
                return bytes(value)
            value.extend(chunk)
            if len(value) > 24 * 1024 * 1024:
                raise ValueError("Unexpected oversized public asset")


def verify_app(expected: dict, base: str, fetch=public_get) -> dict:
    slug = expected["app_slug"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Unsafe app slug")
    if expected.get("status") != "staged_not_published" or not expected.get("assets"):
        raise ValueError("Expected staged, nonempty artwork evidence")
    candidate = expected["candidate_sha256"]
    if not re.fullmatch(r"[a-f0-9]{64}", candidate):
        raise ValueError("Invalid candidate hash")
    receipt_url = f"{base}/release-artwork/{slug}.json"
    public_receipt = json.loads(fetch(receipt_url))
    if canonical(public_receipt) != canonical(expected):
        raise ValueError("Public artwork manifest differs from the reviewed/staged candidate")
    grouped: dict[str, list[dict]] = {}
    for asset in expected["assets"]:
        locale = asset["locale"]
        path = asset["site_path"]
        if (locale not in LOCALES or asset["kind"] != "android" or
                Path(path).is_absolute() or ".." in Path(path).parts or
                not path.startswith(locale + "/") or not re.fullmatch(r"[A-Za-z0-9_./-]+\.png", path) or
                not re.fullmatch(r"[a-f0-9]{64}", asset["sha256"])):
            raise ValueError("Invalid public screenshot mapping")
        grouped.setdefault(locale, []).append(asset)
    pages, verified = [], []
    for locale, assets in sorted(grouped.items()):
        assets.sort(key=lambda item: item["index"])
        if [item["index"] for item in assets] != list(range(1, len(assets) + 1)):
            raise ValueError("Non-contiguous public gallery indices")
        page_path = f"/apps/{slug}/" + (f"{locale.lower()}/" if locale != "en" else "")
        page_url = base + page_path
        html = fetch(page_url)
        gallery = Gallery()
        gallery.feed(html.decode("utf-8"))
        routes = [f"/app-assets/{slug}/assets/screenshots/{asset['site_path']}?v={asset['sha256']}" for asset in assets]
        images = []
        for source in gallery.images:
            url = urllib.parse.urlsplit(urllib.parse.urljoin(base + "/", source))
            if url.scheme != "https" or url.netloc != urllib.parse.urlsplit(base).netloc or url.fragment:
                raise ValueError("Unexpected screenshot origin or fragment")
            images.append(url.path + ("?" + url.query if url.query else ""))
        if gallery.identity != [(slug, locale)] or images != routes:
            raise ValueError(f"Live {locale} app-detail gallery does not show the complete reviewed image set/order/hash URLs")
        if gallery.dimensions != [asset["size"] for asset in assets]:
            raise ValueError(f"Live {locale} HTML screenshot dimensions differ from reviewed artwork")
        pages.append({"url": page_url, "sha256": digest(html), "gallery_count": len(routes),
                      "gallery_dimensions": gallery.dimensions})
        for asset, route in zip(assets, routes):
            raw = fetch(base + route)
            if digest(raw) != asset["sha256"]:
                raise ValueError(f"Live screenshot hash mismatch: {locale}/{asset['index']}")
            if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or list(struct.unpack(">II", raw[16:24])) != asset["size"]:
                raise ValueError("Live screenshot dimensions differ from reviewed artwork")
            verified.append({"url": base + route, "sha256": digest(raw), "size": asset["size"]})
    return {"app_slug": slug, "status": "deployed_verified", "candidate_sha256": candidate,
            "source_commit": expected["source_commit"], "version": expected["version"],
            "public_manifest_sha256": digest(canonical(public_receipt)),
            "pages": pages, "assets": verified,
            "verified_at": datetime.now(timezone.utc).isoformat()}


def verify_report(staging: dict, base: str, timeout: float, interval: float,
                  fetch=public_get, sleep=time.sleep, monotonic=time.monotonic) -> dict:
    output = {"schema_version": 1, "status": "pending", "apps": []}
    pending = []
    for app in staging["apps"]:
        if app["status"] == "staged_not_published":
            pending.append(app)
        else:
            output["apps"].append({"app_slug": app["app_slug"], "status": "blocked",
                                   "reason": app.get("reason", "No verified artwork candidate")})
    deadline = monotonic() + timeout
    errors = {}
    def bounded_fetch(url: str) -> bytes:
        if monotonic() >= deadline:
            raise TimeoutError("Artwork deployment verification deadline elapsed")
        return public_get(url, deadline=deadline) if fetch is public_get else fetch(url)
    while pending:
        retry = []
        for app in pending:
            try:
                output["apps"].append(verify_app(app["expected"], base, bounded_fetch))
            except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as error:
                retry.append(app)
                errors[app["app_slug"]] = str(error)
        pending = retry
        if not pending or monotonic() >= deadline:
            break
        sleep(min(interval, max(0, deadline - monotonic())))
    for app in pending:
        output["apps"].append({"app_slug": app["app_slug"], "status": "deployment_unverified",
                               "reason": errors[app["app_slug"]]})
    output["status"] = ("failed" if any(app["status"] != "deployed_verified" for app in output["apps"])
                        else "deployed_verified" if output["apps"] else "no_public_store_confirmed_releases")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="https://onnellab.com")
    parser.add_argument("--deployment-sha", required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--interval", type=float, default=20)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        parser.error("base-url must be an HTTPS origin")
    if args.timeout < 0 or args.interval <= 0:
        parser.error("timeout must be nonnegative and interval must be positive")
    output = {"schema_version": 1, "status": "failed", "apps": []}
    try:
        output = verify_report(json.loads(args.staging_report.read_text()), base, args.timeout, args.interval)
    except (OSError, ValueError, KeyError, TypeError) as error:
        output["reason"] = str(error)
    output["expected_site_commit"] = args.deployment_sha
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"homepage artwork: {output['status']}")
    return 1 if output["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
