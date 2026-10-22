#!/usr/bin/env python3
"""Verify public app-detail/homepage HTML and exact selected artwork bytes.

The checked-in manifest remains staged_not_published. This separately retained
receipt is the only deployed_verified claim; a successful git push is not one.
An explicitly opted-in routine operational sync may retain a blocked_no_candidates
receipt without failing unrelated release/ops work; it never verifies artwork.
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
SOURCE_REASONS = {"android": "android_edited_available", "iphone_medium": "android_edited_absent"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def image_dimensions(attrs: dict[str, str | None]) -> list[int] | None:
    values = (attrs.get("width") or "", attrs.get("height") or "")
    return [int(value) for value in values] if all(
        re.fullmatch(r"[1-9][0-9]*", value) for value in values) else None


def is_static_product_icon(attrs: dict[str, str | None], slug: str) -> bool:
    icons = [f"/home-assets/app-icons/{slug}-{size}.webp" for size in (96, 192)]
    srcset = attrs.get("srcset") or ""
    variants = [item.split() for item in srcset.split(",")] if srcset else []
    return (attrs.get("data-home-artwork-icon") == "true" and attrs.get("src") in icons and
            (not variants or variants == [[icons[0], "96w"], [icons[1], "192w"]]) and
            not attrs.get("data-home-artwork-source") and not attrs.get("data-home-artwork-slug"))


def require_unique_attributes(attributes: list[tuple[str, str | None]]) -> None:
    names = [name for name, _ in attributes]
    if len(names) != len(set(names)):
        # Browsers keep the first duplicate attribute; dict(attributes) would
        # keep the last and could otherwise verify a src the browser never uses.
        raise ValueError("Duplicate HTML attributes in reviewed artwork scope")


class Gallery(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.images: list[str] = []
        self.dimensions: list[list[int] | None] = []
        self.identity: list[tuple[str | None, str | None]] = []

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        attrs = dict(attributes)
        in_gallery = any(gallery for _, gallery in self.stack) or "data-screenshot-row" in attrs
        if in_gallery or (tag == "main" and "data-product-slug" in attrs):
            require_unique_attributes(attributes)
        if tag == "main" and "data-product-slug" in attrs:
            self.identity.append((attrs.get("data-product-slug"), attrs.get("data-product-locale")))
        if in_gallery and tag in {"picture", "source"}:
            raise ValueError("Unexpected picture/source alternative in reviewed artwork")
        if tag == "img" and in_gallery:
            if any(ancestor == "picture" for ancestor, _ in self.stack):
                raise ValueError("Unexpected picture/source alternative in reviewed artwork")
            if not attrs.get("src") or attrs.get("srcset"):
                raise ValueError("Expected exact static screenshot src without transformed variants")
            self.images.append(str(attrs["src"]))
            self.dimensions.append(image_dimensions(attrs))
        if tag not in VOID:
            self.stack.append((tag, in_gallery))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


class HomeArtwork(HTMLParser):
    """Collect reviewed images and every matching featured container.

    The page contract distinguishes an uninstrumented/old homepage from a new
    homepage on which this app genuinely is not featured. A container is marked
    even when its images fall back to legacy originals, so that fallback fails
    verification rather than disappearing from the evidence.
    """
    def __init__(self, slug: str, locale: str) -> None:
        super().__init__()
        self.slug, self.locale = slug, locale
        self.stack: list[tuple[str, int | None]] = []
        self.identity: list[tuple[str | None, str | None]] = []
        self.containers: list[int] = []
        self.images: list[dict] = []

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        attrs = dict(attributes)
        container = self.stack[-1][1] if self.stack else None
        has_target_marker = any(name in {"data-home-featured-slug", "data-home-artwork-slug"} and value == self.slug
                                for name, value in attributes)
        if (container is not None or has_target_marker or
                (tag == "main" and "data-home-artwork-contract" in attrs)):
            require_unique_attributes(attributes)
        if tag == "main" and "data-home-artwork-contract" in attrs:
            self.identity.append((attrs.get("data-home-artwork-contract"), attrs.get("data-home-locale")))
        if attrs.get("data-home-featured-slug") == self.slug:
            if attrs.get("data-home-featured-locale") != self.locale:
                raise ValueError("Live homepage featured locale differs from reviewed artwork")
            container = len(self.containers)
            self.containers.append(0)
        if container is not None and tag in {"picture", "source"}:
            raise ValueError("Unexpected picture/source alternative in reviewed homepage artwork")
        if tag == "img" and (container is not None or attrs.get("data-home-artwork-slug") == self.slug):
            if any(ancestor == "picture" for ancestor, _ in self.stack):
                raise ValueError("Unexpected picture/source alternative in reviewed homepage artwork")
            # Product icons are not release screenshots. Only the explicitly
            # marked, known static icon path is exempt; marking a screenshot as
            # an icon cannot hide legacy/raw artwork from the verifier.
            # Preserve the homepage's existing 96w/192w responsive icon pair,
            # but do not exempt other srcset URLs or screenshot variants.
            if is_static_product_icon(attrs, self.slug):
                return
            if (attrs.get("data-home-artwork-source") != "reviewed" or
                    attrs.get("data-home-artwork-slug") != self.slug or
                    attrs.get("data-home-artwork-locale") != self.locale or
                    not re.fullmatch(r"[1-9][0-9]*", attrs.get("data-home-artwork-index") or "")):
                raise ValueError("Live homepage featured artwork is missing reviewed image identity or uses legacy originals")
            if not attrs.get("src") or attrs.get("srcset"):
                raise ValueError("Expected exact static homepage src without transformed variants")
            self.images.append({"source": attrs["src"], "index": int(str(attrs["data-home-artwork-index"])),
                                "size": image_dimensions(attrs)})
            if container is not None:
                self.containers[container] += 1
        if tag not in VOID:
            self.stack.append((tag, container))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def selected_assets(expected: dict) -> tuple[str, dict[str, list[dict]]]:
    """Validate one complete source set; freshness is established by staging."""
    if (not isinstance(expected.get("version"), str) or
            not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}\+[0-9]+", expected["version"]) or
            not isinstance(expected.get("source_commit"), str) or
            not re.fullmatch(r"[a-f0-9]{40,64}", expected["source_commit"])):
        raise ValueError("Invalid reviewed version/build/source commit")
    if not isinstance(expected["assets"], list):
        raise ValueError("Invalid public screenshot mapping")
    grouped: dict[str, list[dict]] = {}
    kinds, paths = set(), set()
    for asset in expected["assets"]:
        locale, path = asset["locale"], asset["site_path"]
        size = asset.get("size")
        if (locale not in LOCALES or asset["kind"] not in SOURCE_REASONS or
                not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts or
                not path.startswith(locale + "/") or not re.fullmatch(r"[A-Za-z0-9_./-]+\.png", path) or
                path in paths or not re.fullmatch(r"[a-f0-9]{64}", asset["sha256"]) or
                type(asset.get("index")) is not int or asset["index"] < 1 or
                not isinstance(size, list) or len(size) != 2 or
                any(type(value) is not int or value <= 0 for value in size) or
                ("version" in asset and asset["version"] != expected["version"]) or
                ("source_commit" in asset and asset["source_commit"] != expected["source_commit"])):
            raise ValueError("Invalid public screenshot mapping")
        paths.add(path)
        kinds.add(asset["kind"])
        grouped.setdefault(locale, []).append(asset)
    if len(kinds) != 1:
        raise ValueError("Public screenshots must use one uniform selected source")
    kind = next(iter(kinds))
    if "source_selection" in expected:
        selection = expected["source_selection"]
        if (not isinstance(selection, dict) or
                selection.get("policy") != "android-edited-then-iphone-edited" or
                selection.get("kind") != kind or selection.get("reason") != SOURCE_REASONS[kind]):
            raise ValueError("Invalid public artwork source_selection")
    elif kind != "android":
        raise ValueError("iPhone artwork requires explicit source_selection fallback evidence")
    counts = set()
    for assets in grouped.values():
        assets.sort(key=lambda item: item["index"])
        if [item["index"] for item in assets] != list(range(1, len(assets) + 1)):
            raise ValueError("Non-contiguous public gallery indices")
        counts.add(len(assets))
    if len(counts) != 1:
        raise ValueError("Incomplete public gallery index set across locales")
    return kind, grouped


def static_route(source: str, base: str, page_url: str) -> str:
    url = urllib.parse.urlsplit(urllib.parse.urljoin(page_url, source))
    if url.scheme != "https" or url.netloc != urllib.parse.urlsplit(base).netloc or url.fragment:
        raise ValueError("Unexpected screenshot origin or fragment")
    return url.path + ("?" + url.query if url.query else "")


def verify_image(raw: bytes, asset: dict) -> None:
    if digest(raw) != asset["sha256"]:
        raise ValueError(f"Live screenshot hash mismatch: {asset['locale']}/{asset['index']}")
    if (len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[8:16] != b"\x00\x00\x00\rIHDR" or
            list(struct.unpack(">II", raw[16:24])) != asset["size"]):
        raise ValueError("Live screenshot dimensions differ from reviewed artwork")


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
    kind, grouped = selected_assets(expected)
    receipt_url = f"{base}/release-artwork/{slug}.json"
    public_receipt = json.loads(fetch(receipt_url))
    if canonical(public_receipt) != canonical(expected):
        raise ValueError("Public artwork manifest differs from the reviewed/staged candidate")
    pages, homepages, verified = [], [], []
    for locale, assets in sorted(grouped.items()):
        page_path = f"/apps/{slug}/" + (f"{locale.lower()}/" if locale != "en" else "")
        page_url = base + page_path
        html = fetch(page_url)
        gallery = Gallery()
        gallery.feed(html.decode("utf-8"))
        routes = [f"/app-assets/{slug}/assets/screenshots/{asset['site_path']}?v={asset['sha256']}" for asset in assets]
        images = [static_route(source, base, page_url) for source in gallery.images]
        if gallery.identity != [(slug, locale)] or images != routes:
            raise ValueError(f"Live {locale} app-detail gallery does not show the complete reviewed image set/order/hash URLs")
        if gallery.dimensions != [asset["size"] for asset in assets]:
            raise ValueError(f"Live {locale} HTML screenshot dimensions differ from reviewed artwork")
        pages.append({"url": page_url, "sha256": digest(html), "gallery_count": len(routes),
                      "gallery_dimensions": gallery.dimensions})
        for asset, route in zip(assets, routes):
            raw = fetch(base + route)
            verify_image(raw, asset)
            verified.append({"url": base + route, "sha256": digest(raw), "size": asset["size"]})
        home_url = base + "/" + (locale.lower() + "/" if locale != "en" else "")
        home_html = fetch(home_url)
        home = HomeArtwork(slug, locale)
        home.feed(home_html.decode("utf-8"))
        if home.identity != [("1", locale)]:
            raise ValueError(f"Live {locale} homepage lacks the current artwork/locale contract")
        if any(count == 0 for count in home.containers):
            raise ValueError(f"Live {locale} homepage featured container has no reviewed artwork")
        home_images = []
        for image in home.images:
            index = image["index"]
            if index > len(assets):
                raise ValueError(f"Live {locale} homepage artwork index is absent from reviewed set")
            asset, route = assets[index - 1], routes[index - 1]
            if static_route(image["source"], base, home_url) != route:
                raise ValueError(f"Live {locale} homepage does not show the selected reviewed image/hash URL")
            if image["size"] != asset["size"]:
                raise ValueError(f"Live {locale} homepage HTML screenshot dimensions differ from reviewed artwork")
            # Fetch the actual featured src, rather than inferring publication
            # from its marker or from a successful app-detail fetch.
            raw = fetch(base + route)
            verify_image(raw, asset)
            home_images.append({"url": base + route, "index": index, "sha256": digest(raw), "size": asset["size"]})
        homepages.append({"url": home_url, "sha256": digest(home_html),
                          "featured_container_count": len(home.containers), "images": home_images})
    return {"app_slug": slug, "status": "deployed_verified", "candidate_sha256": candidate,
            "source_commit": expected["source_commit"], "version": expected["version"],
            "selected_source_kind": kind,
            "public_manifest_sha256": digest(canonical(public_receipt)),
            "pages": pages, "homepages": homepages, "assets": verified,
            "verified_at": datetime.now(timezone.utc).isoformat()}


def verify_report(staging: dict, base: str, timeout: float, interval: float,
                  fetch=public_get, sleep=time.sleep, monotonic=time.monotonic, *,
                  report_blocked_no_candidates: bool = False) -> dict:
    output = {"schema_version": 1, "status": "pending", "apps": []}
    if not isinstance(staging.get("apps"), list):
        raise ValueError("Invalid artwork staging report")
    pending = []
    for app in staging["apps"]:
        if app["status"] == "staged_not_published":
            pending.append(app)
        elif app["status"] == "blocked":
            output["apps"].append({"app_slug": app["app_slug"], "status": "blocked",
                                   "reason": app.get("reason", "No verified artwork candidate")})
        else:
            raise ValueError("Unknown artwork staging status")
    had_candidate = bool(pending)
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
    if any(app["status"] != "deployed_verified" for app in output["apps"]):
        # Require the exact stage report's internally consistent zero-candidate
        # counters. A malformed or tampered report is still a workflow failure,
        # even when the caller opted into routine evidence-only reporting.
        evidence_only = (report_blocked_no_candidates and not had_candidate
                         and bool(output["apps"])
                         and staging.get("status") == "blocked_no_candidates"
                         and type(staging.get("staged_count")) is int
                         and staging["staged_count"] == 0
                         and type(staging.get("blocked_count")) is int
                         and staging["blocked_count"] == len(output["apps"]))
        output["status"] = "blocked_no_candidates" if evidence_only else "failed"
    else:
        output["status"] = "deployed_verified" if output["apps"] else "no_public_store_confirmed_releases"
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="https://onnellab.com")
    parser.add_argument("--deployment-sha", required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--interval", type=float, default=20)
    parser.add_argument("--report-blocked-no-candidates", action="store_true",
                        help="For routine operational syncs only; retain blockers without claiming artwork publication")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        parser.error("base-url must be an HTTPS origin")
    if args.timeout < 0 or args.interval <= 0:
        parser.error("timeout must be nonnegative and interval must be positive")
    output = {"schema_version": 1, "status": "failed", "apps": []}
    try:
        output = verify_report(json.loads(args.staging_report.read_text()), base, args.timeout, args.interval,
                               report_blocked_no_candidates=args.report_blocked_no_candidates)
    except (OSError, ValueError, KeyError, TypeError) as error:
        output["reason"] = str(error)
    output["expected_site_commit"] = args.deployment_sha
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"homepage artwork: {output['status']}")
    if output["status"] == "blocked_no_candidates":
        print(f"::warning title=Release artwork evidence blocked::"
              f"{len(output['apps'])} public app(s) have no publishable reviewed candidate; "
              "blockers are retained in the run artifact. No artwork was verified.")
    return 1 if output["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
