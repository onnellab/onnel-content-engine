#!/usr/bin/env python3
"""Build a hosted manual publishing dashboard from generated drafts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from evaluate_social_templates import evaluate_social_templates
from evaluate_syndication_drafts import evaluate_syndication_drafts


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS = ROOT / "data" / "topics.csv"
DEFAULT_SOCIAL_MANIFEST = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION_MANIFEST = ROOT / "generated" / "syndication" / "manifest.json"
DEFAULT_MANUAL_STATE = ROOT / "data" / "manual_publish_state.json"
DEFAULT_VERIFICATION_REPORT = ROOT / "data" / "manual_publication_verification_report.json"
DEFAULT_OUTPUT = ROOT / "generated" / "manual-publish" / "index.html"
DEFAULT_APP_RELEASES = ROOT / "data" / "app_releases.csv"
DEFAULT_APP_RELEASE_PUBLICATIONS = ROOT / "data" / "app_release_publications.csv"
DEFAULT_APP_RELEASE_SYNC_STATUS = ROOT / "data" / "app_release_sync_status.json"
DEFAULT_STORE_VERSIONS = ROOT / "data" / "store_versions.csv"
DEFAULT_APPS_REGISTRY = ROOT / "data" / "apps_registry.csv"
DEFAULT_APP_PRICING = ROOT / "data" / "app_pricing.csv"
DEFAULT_AI_PROVIDER_PRICING = ROOT / "data" / "ai_provider_pricing.csv"
DEFAULT_AI_PROVIDER_PRICING_STATUS = ROOT / "data" / "ai_provider_pricing_status.json"
DEFAULT_MELIVRA_AI_CREDIT_POLICY = ROOT / "data" / "melivra_ai_credit_policy.csv"
DEFAULT_FLUTTER_DEPENDENCY_VERSIONS = ROOT / "data" / "app_flutter_dependency_versions.csv"
DEFAULT_HOMEPAGE_REPO = Path(os.environ.get("ONNELLAB_HOMEPAGE_REPO", "/mnt/c/dev/onnellab.github.io"))
KST = ZoneInfo("Asia/Seoul")
VERSION_PART_RE = re.compile(r"\d+|[A-Za-z]+")


PLATFORM_LABELS = {
    "x": "Twitter",
    "linkedin": "LinkedIn",
    "bluesky": "Bluesky",
    "devto": "Dev.to",
    "hashnode": "Hashnode",
    "medium": "Medium",
}

SOCIAL_DUE_DELAYS_DAYS = {"x": 0, "linkedin": 1, "bluesky": 1}
SYNDICATION_DUE_DELAYS_DAYS = {"devto": 2, "hashnode": 3, "medium": 4}
AUTOMATED_PLATFORMS = {"bluesky", "devto"}
HASHNODE_SEO_DESCRIPTION_LIMIT = 160


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def release_sync_status_item(path: Path = DEFAULT_APP_RELEASE_SYNC_STATUS) -> dict[str, object]:
    if not path.exists():
        return {}
    return read_json(path)


def ai_provider_pricing_status_item(path: Path = DEFAULT_AI_PROVIDER_PRICING_STATUS) -> dict[str, object]:
    if not path.exists():
        return {}
    return read_json(path)


def verification_report_item(path: Path = DEFAULT_VERIFICATION_REPORT) -> dict[str, object]:
    if not path.exists():
        return {}
    return read_json(path)


def manual_state_item(path: Path = DEFAULT_MANUAL_STATE) -> dict[str, object]:
    if not path.exists():
        return {"done": {}, "updated_at": "", "version": 1}
    state = read_json(path)
    if not isinstance(state.get("done"), dict):
        state["done"] = {}
    state.setdefault("updated_at", "")
    state.setdefault("version", 1)
    return state


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    key: list[tuple[int, int | str]] = []
    for part in VERSION_PART_RE.findall(version):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)


def _release_id_to_int(release_id: str) -> int:
    if release_id.startswith("REL-"):
        try:
            return int(release_id.removeprefix("REL-"))
        except ValueError:
            return 0
    return 0


def latest_platform_release_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep only the latest row per app/platform by version then release_id."""
    latest: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("app_id", ""), row.get("platform", ""))
        current = latest.get(key)
        if not current:
            latest[key] = row
            continue
        if (version_key(row.get("version", "")) > version_key(current.get("version", ""))) or (
            version_key(row.get("version", "")) == version_key(current.get("version", ""))
            and _release_id_to_int(row.get("release_id", "")) > _release_id_to_int(current.get("release_id", ""))
        ):
            latest[key] = row
    return list(latest.values())


def read_topics(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["id"]: {key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)}


def read_text(path_value: str) -> str:
    path = ROOT / path_value
    if not path.exists():
        path = Path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def frontmatter_value(markdown: str, key: str) -> str:
    match = re.search(rf"^---\s*$([\s\S]*?)^---\s*$", markdown, re.MULTILINE)
    if not match:
        return ""
    value_match = re.search(rf"^{re.escape(key)}:\s*[\"']?(.+?)[\"']?\s*$", match.group(1), re.MULTILINE)
    return value_match.group(1).strip() if value_match else ""


def markdown_body(markdown: str) -> str:
    return re.sub(r"^---\s*$[\s\S]*?^---\s*", "", markdown, count=1, flags=re.MULTILINE).strip()


def trim_text_to_limit(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0].rstrip()
    return trimmed.rstrip(".,;:") or text[:limit].rstrip()


def medium_story_preview_subtitle(description: str) -> str:
    text = " ".join(description.split())
    if len(text) <= 140:
        return text
    rewrites = (
        ("very large TXT files", "large TXT files"),
        ("that avoids unnecessary lag", "that avoids lag"),
        ("when a focused local media converter is the right workflow", "when to use a focused local media converter"),
    )
    for old, new in rewrites:
        text = text.replace(old, new)
        if len(text) <= 140:
            return text
    return trim_text_to_limit(text, 140)


def medium_topic_label(value: str, limit: int = 25) -> str:
    text = " ".join(value.replace("-", " ").split())
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rstrip()
    if len(text) > limit and not text[limit : limit + 1].isspace() and " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0].rstrip()
    return trimmed.rstrip(".,;:")


def medium_topic_labels(values: list[str], limit: int = 25, max_topics: int = 5) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = medium_topic_label(value, limit)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= max_topics:
            break
    return labels


def hashnode_publish_fields(topic: dict[str, str] | None, draft_text: str) -> dict[str, str]:
    source_text = ""
    if topic and topic.get("canonical_path"):
        source_text = read_text(topic["canonical_path"])
    seo_description = trim_text_to_limit(frontmatter_value(source_text, "description"), HASHNODE_SEO_DESCRIPTION_LIMIT)
    return {
        "publish_title": frontmatter_value(draft_text, "title"),
        "publish_body": markdown_body(draft_text),
        "publish_tags": frontmatter_value(draft_text, "tags"),
        "publish_canonical_url": frontmatter_value(draft_text, "canonical_url"),
        "publish_cover_image": frontmatter_value(draft_text, "cover_image"),
        "seo_title": frontmatter_value(source_text, "title") or frontmatter_value(draft_text, "title"),
        "seo_description": seo_description,
    }


def syndication_publish_fields(
    topic: dict[str, str] | None, draft_text: str, canonical_url: str, platform: str
) -> dict[str, str]:
    source_text = ""
    if topic and topic.get("canonical_path"):
        source_text = read_text(topic["canonical_path"])
    title = frontmatter_value(source_text, "title") or frontmatter_value(draft_text, "title")
    description = frontmatter_value(source_text, "description")
    story_preview_subtitle = medium_story_preview_subtitle(description) if platform == "medium" else description
    language = topic.get("primary_language", "") if topic else ""
    slug = topic.get("slug", "") if topic else ""
    site_root = canonical_url.split("/blog/", 1)[0].rstrip("/") if "/blog/" in canonical_url else "https://onnellab.github.io"
    cover_image = f"{site_root}/blog-assets/{language}/{slug}/social-card.png" if language and slug else ""
    topics = [tag.strip() for tag in frontmatter_value(source_text, "tags").split("|") if tag.strip()]
    publish_tags = medium_topic_labels(topics) if platform == "medium" else topics[:5]
    return {
        "publish_title": title,
        "publish_body": "",
        "publish_tags": ", ".join(publish_tags),
        "publish_canonical_url": canonical_url,
        "publish_cover_image": cover_image,
        "seo_title": title,
        "seo_description": story_preview_subtitle,
    }


def parse_topic_datetime(value: str) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def due_at_for(topic: dict[str, str] | None, platform: str, kind: str) -> str:
    if not topic:
        return ""
    base = parse_topic_datetime(topic.get("published_at", "") or topic.get("scheduled_at", ""))
    if not base:
        return ""
    delays = SOCIAL_DUE_DELAYS_DAYS if kind == "social" else SYNDICATION_DUE_DELAYS_DAYS
    delay = delays.get(platform)
    if delay is None:
        return ""
    return (base + timedelta(days=delay)).isoformat()


def item_key(topic_id: object, platform: str, language: object, template_id: object) -> str:
    return "::".join([str(topic_id), platform, str(language), str(template_id)])


def publishing_mode(platform: str) -> str:
    return "automatic" if platform in AUTOMATED_PLATFORMS else "manual"


def public_release_notes_url(row: dict[str, str]) -> str:
    if row.get("release_type") != "notes_only":
        return ""
    app_slug = row.get("app_slug", "").strip()
    tag = row.get("tag", "").strip()
    if not app_slug or not tag:
        return ""
    version_slug = tag.removeprefix("v")
    return f"https://onnellab.github.io/release-notes/{app_slug}/{version_slug}/"


def app_release_items(releases_path: Path = DEFAULT_APP_RELEASES, publications_path: Path = DEFAULT_APP_RELEASE_PUBLICATIONS) -> list[dict[str, str]]:
    approvals = {
        row.get("release_id", ""): row
        for row in read_csv_rows(publications_path)
        if row.get("release_id")
    }
    items: list[dict[str, str]] = []
    for row in latest_platform_release_rows(read_csv_rows(releases_path)):
        release_id = row.get("release_id", "")
        approval = approvals.get(release_id, {})
        public_release = approval.get("public_release", "").lower() == "true"
        items.append(
            {
                "release_id": release_id,
                "app_id": row.get("app_id", ""),
                "app_slug": row.get("app_slug", ""),
                "app_name": row.get("app_name", ""),
                "repository": row.get("repository", ""),
                "tag": row.get("tag", ""),
                "version": row.get("version", ""),
                "platform": row.get("platform", ""),
                "release_type": row.get("release_type", ""),
                "release_channel": row.get("release_channel", ""),
                "status": row.get("status", ""),
                "release_url": public_release_notes_url(row) or row.get("release_url", ""),
                "released_at": row.get("released_at", ""),
                "release_date": row.get("release_date", ""),
                "public_release": "true" if public_release else "false",
                "approved_at": approval.get("approved_at", ""),
            }
        )
    return items


def store_status_items(store_versions_path: Path = DEFAULT_STORE_VERSIONS) -> list[dict[str, str]]:
    return [
        {
            "app_id": row.get("app_id", ""),
            "app_slug": row.get("app_slug", ""),
            "app_name": row.get("app_name", ""),
            "platform": row.get("platform", ""),
            "store_url": row.get("store_url", ""),
            "version": row.get("version", ""),
            "published_at": row.get("last_updated", ""),
            "release_notes": row.get("release_notes", ""),
            "checked_at": row.get("checked_at", ""),
            "status": row.get("status", ""),
            "notes": row.get("notes", ""),
        }
        for row in read_csv_rows(store_versions_path)
    ]


def flutter_dependency_status_items(path: Path = DEFAULT_FLUTTER_DEPENDENCY_VERSIONS) -> list[dict[str, str]]:
    return [
        {
            "app_id": row.get("app_id", ""),
            "app_slug": row.get("app_slug", ""),
            "package_type": row.get("package_type", ""),
            "package_name": row.get("package_name", ""),
            "declared_version": row.get("declared_version", ""),
            "resolved_version": row.get("resolved_version", ""),
            "flutter_constraint": row.get("flutter_constraint", ""),
            "status": row.get("status", ""),
            "source": row.get("source", ""),
        }
        for row in read_csv_rows(path)
    ]


def blog_status_items(topics_path: Path = DEFAULT_TOPICS) -> list[dict[str, str]]:
    return [
        {
            "topic_id": row.get("id", ""),
            "title": row.get("working_title", ""),
            "language": row.get("primary_language", ""),
            "status": row.get("status", ""),
            "published_url": row.get("published_url", ""),
            "scheduled_at": row.get("scheduled_at", ""),
            "published_at": row.get("published_at", ""),
            "updated_at": row.get("updated_at", ""),
        }
        for row in read_csv_rows(topics_path)
        if row.get("status", "") != "archived"
    ]


def app_name_index(apps_registry_path: Path = DEFAULT_APPS_REGISTRY) -> dict[str, str]:
    return {row.get("slug", ""): row.get("app_name", "") for row in read_csv_rows(apps_registry_path)}


def frontmatter_title(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("title:"):
            return stripped.removeprefix("title:").strip().strip("\"'")
    return ""


def app_display_name(slug: str, names: dict[str, str], app_dir: Path) -> str:
    return names.get(slug) or frontmatter_title(app_dir / "app.md") or slug


def read_app_meta(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line or line.startswith(" ") or line.startswith("\t"):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def format_price_value(value: str, currency: str) -> str:
    if not value:
        return ""
    try:
        number = float(value)
    except ValueError:
        return value
    if number == 0:
        return "Free"
    amount = f"{int(number):,}" if number.is_integer() else f"{number:,.2f}"
    return f"{amount} {currency}".strip()


def parse_float(value: str, fallback: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return fallback


def parse_int_from_product_name(value: str) -> int:
    matches = re.findall(r"\d+", value)
    return int(matches[-1]) if matches else 0


def read_melivra_ai_credit_policy(path: Path = DEFAULT_MELIVRA_AI_CREDIT_POLICY) -> dict[str, float]:
    rows = read_csv_rows(path)
    row = next((item for item in rows if item.get("app_slug") == "melivra"), rows[0] if rows else {})
    return {
        "script_credits_per_minute": parse_float(row.get("script_credits_per_minute", "6"), 6.0),
        "minimum_translation_credits_per_minute": parse_float(row.get("minimum_translation_credits_per_minute", "5"), 5.0),
        "gross_krw_per_100_credits": parse_float(row.get("gross_krw_per_100_credits", "1100"), 1100.0),
        "store_fee_rate": parse_float(row.get("store_fee_rate", "0.30"), 0.30),
        "krw_per_usd_estimate": parse_float(row.get("krw_per_usd_estimate", "1450"), 1450.0),
        "translation_usd_per_million_characters": parse_float(
            row.get("translation_usd_per_million_characters", "25.00"),
            25.0,
        ),
        "translation_characters_per_minute": parse_float(row.get("translation_characters_per_minute", "900"), 900.0),
        "provider_cost_safety_multiplier": parse_float(row.get("provider_cost_safety_multiplier", "1.8"), 1.8),
    }


def provider_price_by_unit(path: Path = DEFAULT_AI_PROVIDER_PRICING) -> dict[tuple[str, str], float]:
    prices: dict[tuple[str, str], float] = {}
    for row in read_csv_rows(path):
        price = parse_float(row.get("price_usd", ""))
        if price > 0:
            prices[(row.get("provider", ""), row.get("unit", ""))] = price
    return prices


def melivra_ai_credit_economics(
    credit_count: int,
    price_amount: float,
    currency: str,
    provider_prices: dict[tuple[str, str], float],
    policy: dict[str, float],
) -> dict[str, str]:
    if credit_count <= 0 or price_amount <= 0:
        return {}
    krw_per_usd = policy["krw_per_usd_estimate"]
    gross_usd = price_amount if currency == "USD" else price_amount / krw_per_usd
    net_usd = gross_usd * (1 - policy["store_fee_rate"])
    whisper_per_minute = provider_prices.get(("openai", "audio_minute"), 0.006)
    deepl_per_million = provider_prices.get(("deepl", "1m_characters"), policy["translation_usd_per_million_characters"])
    translation_cost_per_minute = policy["translation_characters_per_minute"] * deepl_per_million / 1_000_000
    script_credits = policy["script_credits_per_minute"]
    guarded_translation_credits = math.ceil(
        (
            translation_cost_per_minute
            * krw_per_usd
            * policy["provider_cost_safety_multiplier"]
            / ((policy["gross_krw_per_100_credits"] * (1 - policy["store_fee_rate"]) / 100))
        )
    )
    translation_credits = max(policy["minimum_translation_credits_per_minute"], guarded_translation_credits)
    provider_cost_per_credit = (whisper_per_minute + translation_cost_per_minute) / (script_credits + translation_credits)
    provider_cost_usd = provider_cost_per_credit * credit_count
    profit_usd = net_usd - provider_cost_usd
    margin_percent = (profit_usd / net_usd * 100) if net_usd else 0
    status = "profit" if profit_usd > 0 else "loss" if profit_usd < 0 else "even"
    return {
        "ai_credit_count": str(credit_count),
        "ai_net_revenue_usd": f"{net_usd:.2f}",
        "ai_provider_cost_usd": f"{provider_cost_usd:.2f}",
        "ai_profit_usd": f"{profit_usd:.2f}",
        "ai_margin_percent": f"{margin_percent:.1f}",
        "ai_margin_status": status,
        "ai_cost_basis": (
            f"OpenAI ${whisper_per_minute:.3f}/min + DeepL ${deepl_per_million:.2f}/1M chars, "
            f"{int(script_credits + translation_credits)} credits/min script+translation"
        ),
    }


def product_pricing_items(
    homepage_repo: Path = DEFAULT_HOMEPAGE_REPO,
    apps_registry_path: Path = DEFAULT_APPS_REGISTRY,
    app_pricing_path: Path = DEFAULT_APP_PRICING,
    ai_provider_pricing_path: Path = DEFAULT_AI_PROVIDER_PRICING,
    melivra_ai_credit_policy_path: Path = DEFAULT_MELIVRA_AI_CREDIT_POLICY,
) -> list[dict[str, str]]:
    registry = {row.get("slug", ""): row for row in read_csv_rows(apps_registry_path)}
    explicit_rows = read_csv_rows(app_pricing_path)
    provider_prices = provider_price_by_unit(ai_provider_pricing_path)
    melivra_policy = read_melivra_ai_credit_policy(melivra_ai_credit_policy_path)
    explicit_by_slug: dict[str, list[dict[str, str]]] = {}
    for row in explicit_rows:
        explicit_by_slug.setdefault(row.get("app_slug", ""), []).append(row)
    content_apps = homepage_repo / "src" / "content" / "apps"
    slugs = sorted(set(registry) | ({path.name for path in content_apps.iterdir() if path.is_dir()} if content_apps.exists() else set()))
    items: list[dict[str, str]] = []
    for slug in slugs:
        row = registry.get(slug, {})
        meta = read_app_meta(content_apps / slug / "app.md")
        app_name = row.get("app_name") or meta.get("title") or slug
        pricing = meta.get("pricing") or row.get("pricing_model", "")
        price = format_price_value(meta.get("price", ""), meta.get("priceCurrency", ""))
        official_site_path = row.get("official_site_path") or f"/apps/{slug}/"
        base = {
            "app_id": row.get("app_id", ""),
            "app_slug": slug,
            "app_name": app_name,
            "pricing_model": row.get("pricing_model", ""),
            "pricing": pricing,
            "official_site_path": official_site_path,
            "app_store_url": meta.get("appstore") or row.get("app_store_url", ""),
            "play_store_url": meta.get("googleplay") or row.get("play_store_url", ""),
            "checked_at": latest_git_time(homepage_repo, [content_apps / slug / "app.md"]) if homepage_repo.exists() else "",
        }
        explicit_products = explicit_by_slug.get(slug, [])
        for explicit in explicit_products:
            product_type = explicit.get("product_type", "")
            price_amount = parse_float(explicit.get("price", ""))
            currency = explicit.get("currency", "")
            item = {
                **base,
                "product_name": explicit.get("product_name", ""),
                "product_type": product_type,
                "price": format_price_value(explicit.get("price", ""), currency),
                "price_amount": explicit.get("price", ""),
                "currency": currency,
                "price_note": explicit.get("price_note", "Manual price registry"),
            }
            if slug == "melivra" and product_type == "ai_credit":
                item.update(
                    melivra_ai_credit_economics(
                        parse_int_from_product_name(explicit.get("product_name", "")),
                        price_amount,
                        currency,
                        provider_prices,
                        melivra_policy,
                    )
                )
            items.append(item)
        explicit_types = {item.get("product_type", "") for item in explicit_products}
        if "paid_download" not in explicit_types and price and price != "Free":
            items.append(
                {
                    **base,
                    "product_name": "Paid download",
                    "product_type": "paid_download",
                    "price": price,
                    "price_note": "Public landing page metadata",
                }
            )
        if "pro" not in explicit_types and ("optional pro" in pricing.lower() or "pro purchase" in pricing.lower()):
            items.append(
                {
                    **base,
                    "product_name": f"{app_name} Pro",
                    "product_type": "pro",
                    "price": "",
                    "price_note": "Store in-app purchase price not recorded locally",
                }
            )
        if slug == "melivra" and "ai_credit" not in explicit_types:
            items.append(
                {
                    **base,
                    "product_name": "Melivra AI Token",
                    "product_type": "ai_credit",
                    "price": "",
                    "price_note": "AI credit price not recorded locally",
                }
            )
    return sorted(items, key=lambda item: (item["app_name"].lower(), item["product_type"]))


def latest_file_mtime(paths: list[Path]) -> str:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return ""
    latest = max(path.stat().st_mtime for path in existing)
    return datetime.fromtimestamp(latest, tz=KST).isoformat()


def latest_git_time(repo: Path, paths: list[Path]) -> str:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return ""
    file_value = latest_file_mtime(existing)
    try:
        relative = [path.relative_to(repo).as_posix() for path in existing]
        completed = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cI", "--", *relative],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return file_value
    value = completed.stdout.strip()
    if not value:
        return file_value
    git_time = parse_topic_datetime(value)
    file_time = parse_topic_datetime(file_value)
    if git_time and file_time:
        return max(git_time, file_time).isoformat()
    return value or file_value


def current_verification_report(report: dict[str, object], items: list[dict[str, object]]) -> dict[str, object]:
    rows = report.get("items", [])
    if not isinstance(rows, list):
        return report
    current_keys = {str(item.get("manual_key", "")) for item in items}
    filtered_rows = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("manual_key", "")) in current_keys
    ]
    counts = {
        "checked": len(filtered_rows),
        "already_done": sum(1 for row in filtered_rows if row.get("status") == "already_done"),
        "verified": sum(1 for row in filtered_rows if row.get("status") == "verified"),
        "pending": sum(1 for row in filtered_rows if row.get("status") == "pending"),
    }
    return {**report, "counts": counts, "items": filtered_rows}


def homepage_status_items(homepage_repo: Path = DEFAULT_HOMEPAGE_REPO) -> list[dict[str, object]]:
    if not homepage_repo.exists():
        generated_html = ROOT / "generated" / "html"
        return [
            {
                "kind": "home",
                "slug": "home",
                "name": "ONNELLAB Home",
                "landing_updated_at": latest_file_mtime(
                    [
                        generated_html / "index.html",
                        generated_html / "blog" / "index.html",
                        generated_html / "sitemap.xml",
                    ]
                ),
                "screenshots_updated_at": "",
                "assets_updated_at": latest_file_mtime(list((ROOT / "generated" / "assets").glob("**/*"))),
                "screenshot_count": 0,
            }
        ]
    src = homepage_repo / "src"
    content_apps = src / "content" / "apps"
    names = app_name_index()
    items: list[dict[str, object]] = [
        {
            "kind": "home",
            "slug": "home",
            "name": "ONNELLAB Home",
            "landing_updated_at": latest_git_time(
                homepage_repo,
                [
                    src / "components" / "HomePage.astro",
                    src / "pages" / "index.astro",
                    src / "pages" / "ko" / "index.astro",
                ],
            ),
            "screenshots_updated_at": "",
            "assets_updated_at": latest_git_time(
                homepage_repo,
                [
                    homepage_repo / "public" / "favicon.svg",
                    homepage_repo / "public" / "favicon-32x32.png",
                    homepage_repo / "public" / "apple-touch-icon.png",
                ],
            ),
            "screenshot_count": 0,
        }
    ]
    if not content_apps.exists():
        return items
    for app_dir in sorted(path for path in content_apps.iterdir() if path.is_dir()):
        slug = app_dir.name
        landing_paths = [app_dir / "app.md", app_dir / "description-ko.md", app_dir / "description-en.md"]
        screenshot_paths = sorted((app_dir / "assets" / "screenshots").glob("**/*.png"))
        asset_paths = sorted((app_dir / "assets").glob("**/*"))
        asset_files = [path for path in asset_paths if path.is_file() and "screenshots" not in path.parts]
        items.append(
            {
                "kind": "app",
                "slug": slug,
                "name": app_display_name(slug, names, app_dir),
                "landing_updated_at": latest_git_time(homepage_repo, landing_paths),
                "screenshots_updated_at": latest_git_time(homepage_repo, screenshot_paths),
                "assets_updated_at": latest_git_time(homepage_repo, asset_files),
                "screenshot_count": len(screenshot_paths),
            }
        )
    return items


def asset_href(path_value: str) -> str:
    if not path_value:
        return ""
    if path_value.startswith("generated/assets/blog/"):
        return "/blog-assets/" + path_value.removeprefix("generated/assets/blog/")
    if path_value.startswith("generated/"):
        return "../" + path_value.removeprefix("generated/")
    return "../" + path_value


def compose_url(platform: str, text: str, canonical_url: str) -> str:
    if platform == "x":
        return "https://twitter.com/intent/tweet?text=" + quote(text)
    if platform == "bluesky":
        return "https://bsky.app/intent/compose?text=" + quote(text)
    if platform == "linkedin":
        return "https://www.linkedin.com/sharing/share-offsite/?url=" + quote(canonical_url)
    if platform == "devto":
        return "https://dev.to/new"
    if platform == "hashnode":
        return "https://hashnode.com/@onnellab"
    if platform == "medium":
        return "https://medium.com/new-story"
    return canonical_url


def social_items(manifest_path: Path, topics: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    manifest = read_json(manifest_path)
    items: list[dict[str, object]] = []
    for post in manifest.get("posts", []):
        if not isinstance(post, dict):
            continue
        platform = str(post.get("platform", ""))
        topic_id = post.get("topic_id", "")
        language = post.get("language", "")
        template_id = post.get("template_id", "")
        draft_path = str(post.get("draft_path", ""))
        text = read_text(draft_path)
        canonical_url = str(post.get("canonical_url", ""))
        card_asset_path = str(post.get("card_asset_path", ""))
        topic = topics.get(str(topic_id), {})
        items.append(
            {
                "kind": "social",
                "topic_id": topic_id,
                "title": topic.get("working_title", ""),
                "platform": platform,
                "publishing_mode": publishing_mode(platform),
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "language": language,
                "slug": post.get("slug", ""),
                "template_id": template_id,
                "manual_key": item_key(topic_id, platform, language, template_id),
                "is_variant": bool(post.get("is_variant")),
                "status": post.get("status", ""),
                "draft_path": draft_path,
                "canonical_url": canonical_url,
                "card_asset_path": card_asset_path,
                "card_asset_href": asset_href(card_asset_path),
                "text": text,
                "length": post.get("weighted_length") or len(text),
                "publish_title": "",
                "publish_body": "",
                "publish_tags": "",
                "publish_canonical_url": "",
                "publish_cover_image": "",
                "seo_title": "",
                "seo_description": "",
                "approved_at": post.get("approved_at", ""),
                "posted_url": post.get("posted_url", ""),
                "posted_at": post.get("posted_at", ""),
                "last_attempt_at": post.get("last_attempt_at", ""),
                "error_type": post.get("error_type", ""),
                "error": post.get("error", ""),
                "open_url": compose_url(platform, text, canonical_url),
                "due_at": due_at_for(topics.get(str(topic_id)), platform, "social"),
            }
        )
    return items


def syndication_items(manifest_path: Path, topics: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    manifest = read_json(manifest_path)
    items: list[dict[str, object]] = []
    for draft in manifest.get("drafts", []):
        if not isinstance(draft, dict):
            continue
        platform = str(draft.get("platform", ""))
        topic_id = draft.get("topic_id", "")
        language = draft.get("language", "")
        template_id = "markdown"
        draft_path = str(draft.get("draft_path", ""))
        text = read_text(draft_path)
        canonical_url = str(draft.get("canonical_url", ""))
        topic = topics.get(str(topic_id), {})
        fields = (
            hashnode_publish_fields(topic, text)
            if platform == "hashnode"
            else syndication_publish_fields(topic, text, canonical_url, platform)
        )
        items.append(
            {
                "kind": "syndication",
                "topic_id": topic_id,
                "title": topic.get("working_title", ""),
                "platform": platform,
                "publishing_mode": publishing_mode(platform),
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "language": language,
                "slug": draft.get("slug", ""),
                "template_id": template_id,
                "manual_key": item_key(topic_id, platform, language, template_id),
                "is_variant": False,
                "status": draft.get("status", ""),
                "draft_path": draft_path,
                "canonical_url": canonical_url,
                "card_asset_path": "",
                "card_asset_href": "",
                "text": text,
                "length": len(text),
                "publish_title": fields["publish_title"],
                "publish_body": fields["publish_body"],
                "publish_tags": fields["publish_tags"],
                "publish_canonical_url": fields["publish_canonical_url"],
                "publish_cover_image": fields["publish_cover_image"],
                "seo_title": fields["seo_title"],
                "seo_description": fields["seo_description"],
                "approved_at": draft.get("approved_at", ""),
                "posted_url": draft.get("posted_url", ""),
                "posted_at": draft.get("posted_at", ""),
                "last_attempt_at": draft.get("last_attempt_at", ""),
                "error_type": draft.get("error_type", ""),
                "error": draft.get("error", ""),
                "open_url": compose_url(platform, text, canonical_url),
                "due_at": due_at_for(topics.get(str(topic_id)), platform, "syndication"),
            }
        )
    return items


def html_document(
    items: list[dict[str, object]],
    manual_state: dict[str, object] | None = None,
    releases: list[dict[str, str]] | None = None,
    blog_items: list[dict[str, str]] | None = None,
    store_items: list[dict[str, str]] | None = None,
    flutter_dependency_items: list[dict[str, str]] | None = None,
    site_items: list[dict[str, object]] | None = None,
    pricing_items: list[dict[str, str]] | None = None,
    ai_provider_pricing_status: dict[str, object] | None = None,
    release_sync_status: dict[str, object] | None = None,
    verification_report: dict[str, object] | None = None,
    quality_report: dict[str, object] | None = None,
) -> str:
    manual_state = manual_state or {"done": {}, "updated_at": "", "version": 1}
    verification_report = current_verification_report(verification_report or {}, items)
    done_state = manual_state.get("done", {})
    done_keys = set(done_state) if isinstance(done_state, dict) else set()

    def item_is_done(item: dict[str, object]) -> bool:
        return item["status"] == "posted" or str(item.get("manual_key", "")) in done_keys

    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    manual_state_data = json.dumps(manual_state, ensure_ascii=False).replace("</", "<\\/")
    release_data = json.dumps(releases or [], ensure_ascii=False).replace("</", "<\\/")
    blog_data = json.dumps(blog_items or [], ensure_ascii=False).replace("</", "<\\/")
    store_data = json.dumps(store_items or [], ensure_ascii=False).replace("</", "<\\/")
    flutter_dependency_data = json.dumps(flutter_dependency_items or [], ensure_ascii=False).replace("</", "<\\/")
    site_data = json.dumps(site_items or [], ensure_ascii=False).replace("</", "<\\/")
    pricing_data = json.dumps(pricing_items or [], ensure_ascii=False).replace("</", "<\\/")
    ai_provider_pricing_status_data = json.dumps(ai_provider_pricing_status or {}, ensure_ascii=False).replace("</", "<\\/")
    release_sync_data = json.dumps(release_sync_status or {}, ensure_ascii=False).replace("</", "<\\/")
    verification_report_data = json.dumps(verification_report or {}, ensure_ascii=False).replace("</", "<\\/")
    quality_report_data = json.dumps(quality_report or {}, ensure_ascii=False).replace("</", "<\\/")
    total = len(items)
    manual = sum(
        1
        for item in items
        if item["publishing_mode"] == "manual"
        and not item["is_variant"]
        and not item_is_done(item)
        and item["status"] in {"draft", "failed", "approved"}
    )
    posted = sum(1 for item in items if not item["is_variant"] and item_is_done(item))
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ONNELLAB 게시 상태 대시보드</title>
  <meta name="theme-color" content="#fffaf5">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <meta name="googlebot" content="noindex,nofollow,noarchive">
  <meta name="naverbot" content="noindex,nofollow,noarchive">
  <meta name="yeti" content="noindex,nofollow,noarchive">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="ONNEL Dashboard">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <link rel="icon" href="/favicon.svg?v=20260712-ol-transparent-v2" type="image/svg+xml">
  <link rel="icon" href="/favicon-32x32.png?v=20260712-ol-transparent-v2" sizes="32x32" type="image/png">
  <link rel="manifest" href="./manifest.webmanifest">
  <link rel="apple-touch-icon" href="./icon-180.png?v=20260713-dashboard-bg">
  <style>
    :root {{
      --ink: #191714; --muted: #746f69; --line: #ddd4ca; --surface: #fffaf5; --panel: #ffffff;
      --blue: #2e6fbb; --blue-soft: #e8f1fb; --peach: #f4c3b4; --peach-soft: #fff0ea;
      --lilac: #d8cdf7; --lilac-soft: #f4f0ff; --sky: #cfe6ff; --sky-soft: #eef7ff;
      --ok: #2f7a52; --ok-soft: #edf8f1; --bad: #b3261e; --bad-soft: #fff0ee;
      --shadow: 0 14px 35px rgba(47, 38, 28, .08);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--surface); word-break: keep-all; overflow-wrap: normal; line-break: strict; }}
    code, pre, kbd, samp, input, textarea {{ word-break: normal; overflow-wrap: anywhere; line-break: auto; }}
    header {{ position: sticky; top: 0; z-index: 5; border-bottom: 1px solid rgba(221, 212, 202, .85); background: rgba(255, 250, 245, .94); backdrop-filter: blur(14px); }}
    .bar {{ max-width: 1180px; margin: 0 auto; padding: 14px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 800; letter-spacing: 0; color: inherit; text-decoration: none; }}
    .mark {{ width: 32px; height: 32px; display: block; object-fit: contain; }}
    .header-right {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
    .summary {{ display: flex; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }}
    .pill {{ min-height: 31px; border: 1px solid var(--line); padding: 6px 9px; background: rgba(255,255,255,.75); color: var(--muted); border-radius: 999px; }}
    .pill.is-active {{ border-color: var(--blue); background: var(--blue-soft); color: var(--blue); font-weight: 800; }}
    .lang {{ min-height: 31px; border-color: var(--line); background: var(--ink); color: #fff; padding: 6px 10px; border-radius: 999px; font-size: 12px; white-space: nowrap; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px 20px 56px; }}
    .overview {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }}
    .metric-card {{ border: 1px solid var(--line); background: var(--panel); color: var(--ink); padding: 14px; border-radius: 8px; box-shadow: var(--shadow); min-height: 88px; display: flex; flex-direction: column; justify-content: space-between; text-align: left; }}
    .metric-card:nth-child(1) {{ background: linear-gradient(135deg, var(--peach-soft), #fff); }}
    .metric-card:nth-child(2) {{ background: linear-gradient(135deg, var(--sky-soft), #fff); }}
    .metric-card:nth-child(3) {{ background: linear-gradient(135deg, var(--ok-soft), #fff); }}
    .metric-card:nth-child(4) {{ background: linear-gradient(135deg, var(--lilac-soft), #fff); }}
    .metric-card:nth-child(5) {{ background: linear-gradient(135deg, var(--blue-soft), #fff); }}
    .metric-card span {{ color: var(--muted); font-size: 12px; }}
    .metric-card strong {{ font-size: 28px; line-height: 1; letter-spacing: 0; }}
    .metric-card strong.state-line {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .metric-card strong > span:not(.state-subtext) {{ color: inherit; font-size: 28px; line-height: 1; }}
    .metric-card .spinner {{ width: 18px; height: 18px; border: 2px solid rgba(46,111,187,.22); border-top-color: var(--blue); border-radius: 999px; animation: spin .8s linear infinite; flex: 0 0 auto; }}
    .metric-card .state-subtext {{ font-size: 12px; font-weight: 800; color: var(--muted); line-height: 1.2; }}
    .metric-card.is-working {{ border-color: var(--blue); outline: 2px solid rgba(46,111,187,.14); }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .metric-card.is-active {{ border-color: var(--blue); outline: 2px solid rgba(46,111,187,.16); }}
    .metric-card:disabled {{ cursor: default; opacity: .72; transform: none; }}
    .atm-action {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 320px); gap: 14px; align-items: center; border: 1px solid var(--line); background: rgba(255,255,255,.86); border-radius: 8px; padding: 16px; margin-bottom: 14px; box-shadow: var(--shadow); }}
    .atm-action h1 {{ margin: 0 0 6px; font-size: 24px; line-height: 1.2; }}
    .atm-action p {{ margin: 0; color: var(--muted); font-size: 14px; line-height: 1.5; }}
    .atm-note {{ margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.45; }}
    .atm-action button {{ min-height: 66px; font-size: 20px; font-weight: 900; background: var(--blue); border-color: var(--blue); }}
    .atm-action button:disabled {{ opacity: .72; cursor: default; }}
    .atm-side {{ display: grid; gap: 8px; }}
    .atm-status-row {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .atm-status-row button {{ min-height: 46px; background: #fff; color: var(--ink); border-color: var(--line); padding: 8px; font-size: 12px; font-weight: 800; text-align: left; }}
    .atm-status-row button strong {{ display: block; margin-top: 3px; font-size: 15px; line-height: 1.1; }}
    .atm-status-row button strong > span:not(.state-subtext) {{ color: inherit; font-size: 15px; line-height: 1.1; }}
    .atm-status-row button .state-subtext {{ display: block; margin-top: 2px; font-size: 11px; color: var(--muted); }}
    .run-link {{ min-height: 34px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--line); border-radius: 999px; background: #fff; color: var(--blue); font-size: 12px; font-weight: 900; text-decoration: none; padding: 7px 10px; }}
    .run-link:hover {{ border-color: var(--blue); background: var(--blue-soft); }}
    .run-link[hidden] {{ display: none; }}
    .tool-panel {{ border: 1px solid var(--line); background: rgba(255,255,255,.86); border-radius: 8px; padding: 10px; margin-bottom: 14px; box-shadow: var(--shadow); }}
    .panel-summary {{ cursor: pointer; font-weight: 900; font-size: 15px; min-height: 36px; display: inline-flex; align-items: center; gap: 8px; width: fit-content; max-width: 100%; border: 1px solid var(--line); background: var(--panel); border-radius: 999px; padding: 7px 11px; margin-bottom: 10px; }}
    .panel-summary:hover {{ border-color: var(--blue); background: var(--blue-soft); }}
    .credential-panel {{ display: grid; gap: 10px; border: 1px solid var(--line); background: rgba(255,255,255,.86); border-radius: 8px; padding: 14px; margin-bottom: 14px; box-shadow: var(--shadow); }}
    .credential-head {{ display: flex; align-items: start; justify-content: space-between; gap: 12px; }}
    .credential-head h2 {{ margin: 0; font-size: 17px; }}
    .credential-head p {{ margin: 4px 0 0; color: var(--muted); font-size: 13px; line-height: 1.45; }}
    .credential-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
    .credential-grid label {{ display: grid; gap: 5px; color: var(--muted); font-size: 12px; font-weight: 800; }}
    .credential-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .credential-output {{ min-height: 78px; }}
    .quick-row {{ display: grid; grid-template-columns: minmax(180px, .9fr) minmax(220px, 1.2fr) auto; gap: 10px; align-items: center; }}
    .auth {{ display: grid; grid-template-columns: minmax(220px, 1fr) repeat(3, auto); gap: 8px; margin-top: 12px; }}
    .controls {{ display: grid; grid-template-columns: minmax(220px, 1fr) repeat(3, minmax(116px, 150px)); gap: 10px; margin-top: 8px; }}
    .secondary-controls {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }}
    .platform-status {{ margin-top: 18px; }}
    .platform-status summary {{ cursor: pointer; font-weight: 900; font-size: 16px; min-height: 40px; display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; width: fit-content; max-width: 100%; border: 1px solid var(--line); background: var(--panel); border-radius: 999px; padding: 8px 12px; }}
    .platform-status-summary {{ display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; }}
    .platform-count-badge {{ display: inline-flex; align-items: center; gap: 4px; min-height: 24px; padding: 3px 8px; border: 1px solid var(--line); border-radius: 999px; background: #fffdf9; color: var(--muted); font-size: 12px; font-weight: 800; text-decoration: none; }}
    .platform-count-badge b {{ color: var(--ink); font-size: 13px; line-height: 1; }}
    .platforms {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin: 8px 0 0; }}
    .platform-card {{ border: 1px solid var(--line); background: var(--panel); padding: 12px; border-radius: 8px; box-shadow: 0 8px 22px rgba(47, 38, 28, .05); }}
    .platform-card strong {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 15px; margin-bottom: 8px; }}
    .platform-card strong a {{ display: inline-flex; align-items: center; min-height: 34px; padding: 4px 8px; margin: -4px -8px; border-radius: 6px; color: inherit; text-decoration: none; }}
    .platform-card strong a:hover {{ background: var(--blue-soft); color: var(--blue); }}
    .platform-card strong .tag {{ flex: 0 0 auto; font-size: 11px; font-weight: 700; }}
    .tag.mode-manual {{ color: #fff; background: var(--bad); border-color: var(--bad); font-weight: 900; }}
    .tag.mode-automatic {{ color: var(--ok); background: var(--ok-soft); border-color: #b7d9c5; font-weight: 800; }}
    .platform-card > span {{ display: block; color: var(--muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }}
    .status-section {{ margin-top: 20px; border-top: 1px solid var(--line); padding-top: 16px; }}
    .status-section summary {{ cursor: pointer; font-weight: 900; font-size: 16px; min-height: 40px; display: inline-flex; align-items: center; gap: 8px; width: fit-content; max-width: 100%; border: 1px solid var(--line); background: var(--panel); border-radius: 999px; padding: 8px 12px; }}
    .platform-status summary:hover,
    .status-section summary:hover {{ border-color: var(--blue); background: var(--blue-soft); }}
    .release-head {{ display: flex; align-items: end; justify-content: space-between; gap: 12px; margin-bottom: 10px; }}
    .release-head h2 {{ margin: 0; font-size: 18px; }}
    .release-head h3 {{ margin: 0; font-size: 16px; }}
    .release-head.subhead {{ margin-top: 16px; }}
    .release-head span {{ color: var(--muted); font-size: 12px; }}
    .status-grid, .release-grid, .app-status-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }}
    .status-card, .release-card, .app-status-card {{ border: 1px solid var(--line); background: var(--panel); padding: 12px; border-radius: 8px; box-shadow: 0 8px 22px rgba(47, 38, 28, .05); }}
    .status-card strong,
    .release-card strong,
    .app-status-card strong {{ display: block; font-size: 15px; margin-bottom: 8px; }}
    .app-status-card strong a {{ display: inline-flex; align-items: center; min-height: 34px; padding: 4px 8px; margin: -4px -8px; border-radius: 6px; color: inherit; text-decoration: none; }}
    .app-status-card strong a:hover {{ background: var(--blue-soft); color: var(--blue); }}
    .status-card span,
    .release-card span,
    .app-status-card span {{ display: block; color: var(--muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }}
    .app-status-card {{ display: flex; flex-direction: column; gap: 10px; }}
    .app-status-card strong {{ margin-bottom: 0; }}
    .app-status-row {{ flex: 0 0 auto; border: 1px solid var(--line); border-radius: 8px; padding: 9px; background: #fffdf9; }}
    .app-status-row:only-of-type {{ flex: 1 1 auto; }}
    .app-status-row b {{ display: block; font-size: 13px; margin-bottom: 5px; }}
    .app-status-row.is-release {{ background: var(--lilac-soft); }}
    .app-status-row.is-store {{ background: var(--sky-soft); }}
    .app-status-row.is-ai-profit {{ background: var(--ok-soft); border-color: #b7d9c5; }}
    .app-status-row.is-ai-loss {{ background: var(--bad-soft); border-color: #efb5b0; }}
    .ai-margin-badge {{ display: inline-flex; width: fit-content; max-width: 100%; margin: 2px 0 5px; padding: 4px 7px; border: 1px solid #b7d9c5; border-radius: 999px; color: var(--ok); background: #fff; font-size: 12px; font-weight: 900; }}
    .app-status-row.is-ai-loss .ai-margin-badge {{ color: var(--bad); border-color: #efb5b0; }}
    input, select {{ width: 100%; min-height: 40px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); padding: 8px 10px; font: inherit; border-radius: 6px; }}
    input:focus, select:focus, textarea:focus {{ outline: 2px solid rgba(46,111,187,.2); border-color: var(--blue); }}
    input.needs-token {{ border-color: var(--blue); box-shadow: 0 0 0 3px rgba(46,111,187,.18); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; align-items: start; }}
    article {{ border: 1px solid var(--line); background: var(--panel); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow); }}
    article.is-due {{ border-color: #efb5b0; }}
    article.is-done {{ opacity: .78; }}
    .thumb {{ width: 100%; aspect-ratio: 1.91 / 1; object-fit: cover; display: block; border-bottom: 1px solid var(--line); background: #eee; }}
    .body {{ padding: 14px; }}
    .card-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
    .platform-badge {{ display: inline-flex; align-items: center; min-height: 30px; padding: 6px 10px; border-radius: 999px; border: 1px solid var(--line); background: var(--ink); color: #fff; font-size: 13px; font-weight: 800; text-decoration: none; }}
    .platform-badge.platform-x {{ background: #1da1f2; border-color: #1da1f2; }}
    .platform-badge.platform-linkedin {{ background: #0a66c2; border-color: #0a66c2; }}
    .platform-badge.platform-bluesky {{ background: #1685fe; border-color: #1685fe; }}
    .platform-badge.platform-devto {{ background: #171717; }}
    .platform-badge.platform-hashnode {{ background: #2962ff; border-color: #2962ff; }}
    .platform-badge.platform-medium {{ background: #1f1f1f; }}
    .meta {{ color: var(--muted); font-size: 12px; line-height: 1.35; margin-bottom: 10px; overflow-wrap: anywhere; }}
    .tag {{ font-size: 12px; border: 1px solid var(--line); padding: 4px 7px; color: var(--muted); background: #fff; border-radius: 999px; }}
    .tag.status-posted {{ color: var(--ok); border-color: #b7d9c5; background: var(--ok-soft); }}
    .tag.status-failed {{ color: var(--bad); border-color: #efb5b0; background: var(--bad-soft); }}
    .tag.status-approved {{ color: var(--blue); border-color: #acc9e7; background: var(--blue-soft); }}
    .tag.status-due {{ color: #fff; border-color: var(--bad); background: var(--bad); }}
    .tag.status-done {{ color: var(--ok); border-color: #b7d9c5; background: #f2fbf5; }}
    .tag.verification-automatic {{ color: var(--blue); border-color: #acc9e7; background: var(--blue-soft); }}
    .tag.verification-public {{ color: #6d4d00; border-color: #ead08a; background: #fff8df; }}
    .tag.verification-manual {{ color: var(--muted); border-color: var(--line); background: #fff; }}
    h2 {{ font-size: 17px; line-height: 1.35; margin: 0 0 6px; }}
    h2 a {{ color: inherit; text-decoration: none; border-radius: 6px; margin: -3px -5px; padding: 3px 5px; }}
    h2 a:hover, h2 a:focus-visible {{ color: var(--blue); background: var(--blue-soft); }}
    .subtitle {{ color: var(--muted); font-size: 12px; margin: 0 0 10px; overflow-wrap: anywhere; }}
    .card-summary {{ display: grid; gap: 8px; margin-bottom: 10px; }}
    .card-summary .note {{ margin-top: 0; }}
    .card-detail {{ display: none; margin-top: 10px; }}
    article.is-expanded .card-detail {{ display: block; }}
    .card-detail > button, .card-detail > a.button {{ width: 100%; display: block; margin-top: 8px; }}
    .copy-field {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: end; margin-bottom: 8px; }}
    .copy-field label {{ display: grid; gap: 5px; min-width: 0; color: var(--muted); font-size: 12px; font-weight: 800; }}
    .copy-field textarea {{ min-height: 54px; resize: vertical; }}
    .copy-field button {{ min-height: 54px; min-width: 82px; }}
    textarea {{ width: 100%; min-height: 170px; resize: vertical; border: 1px solid var(--line); padding: 11px; font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: var(--ink); background: #fff; border-radius: 6px; }}
    .actions {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }}
    .actions .primary {{ min-height: 48px; font-size: 16px; font-weight: 900; background: var(--blue); border-color: var(--blue); }}
    button, a.button {{ min-height: 38px; border: 1px solid var(--ink); background: var(--ink); color: #fff; padding: 8px 10px; font: inherit; text-decoration: none; text-align: center; cursor: pointer; border-radius: 6px; }}
    button:hover, a.button:hover {{ transform: translateY(-1px); }}
    button.secondary, a.secondary {{ background: #fff; color: var(--ink); border-color: var(--line); }}
    .note {{ margin-top: 8px; color: var(--muted); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }}
    .token-note {{ margin-top: 8px; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .error {{ margin-top: 10px; color: var(--bad); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; background: var(--bad-soft); border: 1px solid #efb5b0; border-radius: 6px; padding: 8px; }}
    .empty {{ border: 1px dashed var(--line); padding: 24px; color: var(--muted); background: var(--panel); text-align: left; border-radius: 8px; }}
    .empty strong {{ display: block; color: var(--ink); font-size: 18px; margin-bottom: 8px; }}
    .empty span {{ display: block; line-height: 1.55; }}
    @media (max-width: 900px) {{
      .overview {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 760px) {{
      .bar {{ align-items: flex-start; flex-direction: column; }}
      .header-right {{ width: 100%; justify-content: space-between; }}
      .atm-action {{ grid-template-columns: 1fr; padding: 14px; }}
      .atm-action h1 {{ font-size: 20px; }}
      .atm-action button {{ min-height: 60px; font-size: 18px; }}
      .quick-row {{ grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 8px; }}
      .quick-row button {{ padding-left: 8px; padding-right: 8px; font-size: 13px; white-space: nowrap; }}
      .auth, .controls {{ grid-template-columns: 1fr 1fr; }}
      .auth input, .controls input {{ grid-column: 1 / -1; }}
      .credential-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 520px) {{
      main {{ padding: 16px 12px 40px; }}
      .overview {{ grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin-bottom: 10px; }}
      .metric-card {{ min-height: 58px; padding: 9px; }}
      .metric-card span {{ font-size: 11px; line-height: 1.15; }}
      .metric-card strong {{ font-size: 22px; }}
      .metric-card strong > span:not(.state-subtext) {{ font-size: 22px; }}
      .platform-status summary {{ width: 100%; align-items: flex-start; flex-direction: column; gap: 8px; border-radius: 8px; }}
      .platform-status-summary {{ width: 100%; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }}
      .platform-count-badge {{ min-height: 34px; justify-content: space-between; padding: 6px 8px; font-size: 11px; }}
      .platform-count-badge b {{ font-size: 14px; }}
      .platforms {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
      .auth {{ grid-template-columns: 1fr 1fr; }}
      .auth input {{ grid-column: 1 / -1; }}
      .controls {{ grid-template-columns: 1fr; }}
      .controls input {{ grid-column: auto; }}
      .quick-row {{ grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; }}
      .quick-row button {{ min-height: 40px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <a class="brand" href="/" aria-label="ONNELLAB home"><img class="mark" src="/favicon.svg?v=20260712-ol-transparent-v2" alt="" width="32" height="32"><div id="app-title">ONNELLAB 수동 게시</div></a>
      <div class="header-right">
        <button id="lang-toggle" type="button" class="lang">English</button>
      </div>
    </div>
  </header>
  <main>
    <section class="overview" aria-label="Publish overview">
      <button class="metric-card" type="button" data-view="due"><span id="overview-due-label">오늘 할 일</span><strong class="due-count">0</strong></button>
      <button class="metric-card" type="button" data-view="manual"><span id="overview-manual-label">수동 대기</span><strong id="manual-count">{manual}</strong></button>
      <button class="metric-card" type="button" data-view="done"><span id="overview-posted-label">게시 완료</span><strong id="posted-count">{posted}</strong></button>
    </section>
    <section class="atm-action" aria-label="Primary verification action">
      <div>
        <h1 id="atm-title">게시 여부 확인</h1>
        <p id="atm-copy">X와 LinkedIn의 공개 게시물을 확인하고, 일치하는 수동 게시 항목만 완료로 표시합니다.</p>
        <div id="token-note" class="atm-note">GitHub 토큰 연결 후 동기화와 공개 확인을 실행할 수 있습니다.</div>
      </div>
      <div class="atm-side">
        <button id="verify-publications-primary" type="button">게시 확인 및 완료 반영</button>
        <div class="atm-status-row" aria-label="Sync and verification status">
          <button type="button" id="refresh-state-large"><span id="overview-sync-label">동기화</span><strong id="sync-state-large">...</strong></button>
          <button type="button" id="verify-publications-large"><span id="overview-verify-label">공개 확인</span><strong id="verify-state-large">...</strong></button>
        </div>
        <a id="verification-run-link" class="run-link" href="#" target="_blank" rel="noopener" hidden>실행 기록</a>
      </div>
    </section>
    <details class="tool-panel" aria-label="Publish controls">
      <summary id="filter-panel-title" class="panel-summary">검색 및 필터</summary>
      <div class="quick-row">
        <select id="platform"><option value="">모든 매체</option></select>
        <select id="visibility"><option value="due">게시 예정만</option><option value="active">진행 항목만</option><option value="all">완료 포함</option></select>
        <button id="toggle-variants" type="button" class="secondary">대안 보기</button>
      </div>
      <div class="controls">
        <input id="search" type="search" placeholder="토픽, 매체, 언어, 상태 검색">
        <select id="language"><option value="">모든 언어</option></select>
        <select id="status"><option value="">모든 상태</option></select>
        <select id="mode"><option value="manual">수동만</option><option value="automatic">자동화만</option><option value="">전체</option></select>
      </div>
      <div class="auth" id="sync-auth" hidden>
        <input id="token" type="password" autocomplete="off" placeholder="ONNELLAB_GITHUB_PAGES_TOKEN">
        <button id="save-token" type="button">동기화 연결</button>
        <button id="refresh-state" type="button" class="secondary">새로고침</button>
        <button id="enable-badge" type="button" class="secondary">뱃지 켜기</button>
      </div>
    </details>
    <details class="credential-panel" aria-label="Automated posting credentials">
      <summary id="credential-panel-title" class="panel-summary">자동 포스팅 연결</summary>
      <div class="credential-head">
        <div>
          <h2 id="credentials-title">자동 포스팅 연결</h2>
          <p id="credentials-copy">Bluesky 앱 패스워드와 Dev.to API key를 입력하면 로컬 env 파일에 넣을 값과 실행 명령을 만들 수 있습니다.</p>
        </div>
      </div>
      <div class="credential-grid">
        <label><span id="bluesky-handle-label">Bluesky handle</span><input id="bluesky-handle" type="text" autocomplete="username" value="onnellab.bsky.social"></label>
        <label><span id="bluesky-password-label">Bluesky 앱 패스워드</span><input id="bluesky-app-password" type="password" autocomplete="off"></label>
        <label><span id="devto-key-label">Dev.to API key</span><input id="devto-api-key" type="password" autocomplete="off"></label>
      </div>
      <div class="credential-actions">
        <button id="save-credentials" type="button">입력값 저장</button>
        <button id="copy-env-block" type="button" class="secondary">env 블록 복사</button>
        <button id="copy-secret-sync-command" type="button" class="secondary">GitHub secrets 동기화 명령 복사</button>
        <button id="copy-post-command" type="button" class="secondary">자동 포스팅 명령 복사</button>
        <button id="run-posting-now" type="button" class="secondary">지금 자동 포스팅 실행</button>
        <button id="clear-credentials" type="button" class="secondary">입력값 삭제</button>
      </div>
      <textarea id="credential-output" class="credential-output" readonly spellcheck="false"></textarea>
      <div id="posting-run-note" class="note">입력값 저장만으로는 자동 게시가 즉시 실행되지 않습니다. GitHub secrets 동기화 후 이 버튼으로 publishing workflow를 dry_run=false로 실행하세요.</div>
      <div id="credential-note" class="note">복사한 env 블록을 docs/environment variables.md에 붙여넣으면 기존 자동 포스팅 스크립트가 해당 값을 읽습니다.</div>
    </details>
    <div id="grid" class="grid"></div>
    <div id="empty" class="empty" hidden>현재 필터와 일치하는 초안이 없습니다.</div>
    <details class="platform-status" aria-label="Platform status">
      <summary><span id="platform-status-title">매체별 상태</span><span id="platform-status-summary" class="platform-status-summary"></span></summary>
      <div id="platform-summary" class="platforms"></div>
    </details>
    <details class="status-section" aria-label="Website asset status">
      <summary id="site-status-title">사이트 갱신 상태</summary>
      <div class="release-head">
        <span id="site-status-summary"></span>
      </div>
      <div id="site-status-grid" class="app-status-grid"></div>
    </details>
    <details class="status-section" aria-label="Publishing quality status">
      <summary id="quality-status-title">발행 품질 점검</summary>
      <div class="release-head">
        <span id="quality-status-summary"></span>
      </div>
      <div id="quality-status-grid" class="app-status-grid"></div>
    </details>
    <details class="status-section" aria-label="App operation status">
      <summary id="app-status-title">앱 운영 상태</summary>
      <div class="release-head">
        <span id="app-status-summary"></span>
      </div>
      <div id="app-status-grid" class="app-status-grid"></div>
    </details>
    <details class="status-section" aria-label="Paid product pricing status">
      <summary id="pricing-status-title">유료 제품 가격</summary>
      <div class="release-head">
        <span id="pricing-status-summary"></span>
      </div>
      <div id="pricing-status-grid" class="app-status-grid"></div>
    </details>
  </main>
  <script id="manual-data" type="application/json">{data}</script>
  <script id="manual-state-data" type="application/json">{manual_state_data}</script>
  <script id="release-data" type="application/json">{release_data}</script>
  <script id="blog-data" type="application/json">{blog_data}</script>
  <script id="store-data" type="application/json">{store_data}</script>
  <script id="flutter-dependency-data" type="application/json">{flutter_dependency_data}</script>
  <script id="site-data" type="application/json">{site_data}</script>
  <script id="pricing-data" type="application/json">{pricing_data}</script>
  <script id="ai-provider-pricing-status-data" type="application/json">{ai_provider_pricing_status_data}</script>
  <script id="release-sync-data" type="application/json">{release_sync_data}</script>
  <script id="verification-report-data" type="application/json">{verification_report_data}</script>
  <script id="quality-report-data" type="application/json">{quality_report_data}</script>
  <script>
    let items = JSON.parse(document.getElementById('manual-data').textContent);
    let releases = JSON.parse(document.getElementById('release-data').textContent);
    let blogItems = JSON.parse(document.getElementById('blog-data').textContent);
    let storeItems = JSON.parse(document.getElementById('store-data').textContent);
    let flutterDependencyItems = JSON.parse(document.getElementById('flutter-dependency-data').textContent);
    let siteItems = JSON.parse(document.getElementById('site-data').textContent);
    let pricingItems = JSON.parse(document.getElementById('pricing-data').textContent);
    let aiProviderPricingStatus = JSON.parse(document.getElementById('ai-provider-pricing-status-data').textContent);
    let releaseSyncStatus = JSON.parse(document.getElementById('release-sync-data').textContent);
    let verificationReport = JSON.parse(document.getElementById('verification-report-data').textContent);
    let qualityReport = JSON.parse(document.getElementById('quality-report-data').textContent);
    const stateRepo = 'onnellab/onnel-content-engine';
    const statePath = 'data/manual_publish_state.json';
    const reportPath = 'data/manual_publication_verification_report.json';
    const releasePublicationsPath = 'data/app_release_publications.csv';
    const stateBranch = 'main';
    const tokenKey = 'onnellab-manual-publish-token';
    const langKey = 'onnellab-manual-publish-lang';
    const credentialStorageKey = 'onnellab-publishing-credentials';
    const params = new URLSearchParams(window.location.search);
    const messages = {{
      ko: {{
        appTitle: 'ONNELLAB 게시 상태 대시보드',
        total: '전체',
        due: '예정',
        manual: '수동',
        posted: '게시됨',
        loading: '불러오는 중',
        syncing: '동기화 중',
        synced: '동기화됨',
        viewOnly: '보기 전용',
        syncError: '동기화 오류',
        saveError: '저장 오류',
        tokenPlaceholder: 'ONNELLAB_GITHUB_PAGES_TOKEN',
        advancedSummary: '상세 필터와 동기화',
        filterPanelTitle: '검색 및 필터',
        connectSync: '동기화 연결',
        refresh: '새로고침',
        verifyPublications: '공개 프로필 확인',
        verifyingPublications: '확인 실행 중',
        verificationStarted: '확인 시작됨',
        verificationQueued: '대기 중',
        verificationRunning: '실행 중',
        verificationCompleted: '완료',
        verificationRunLink: 'GitHub Actions 실행 기록',
        verificationChecked: '확인 항목',
        verificationAlreadyDone: '기존 완료',
        verificationNewDone: '신규 완료',
        verificationPending: '미확인',
        verificationNoReport: '확인 기록 없음',
        verificationReady: '실행',
        verificationTokenRequired: '토큰 필요',
        verificationFailed: '실패',
        verificationTimedOut: '확인 시간 초과 · 실행 기록에서 상태를 확인해 주세요',
        verificationRefreshIn: '자동 재확인',
        secondsShort: '초',
        tokenNeededNote: 'ONNELLAB_GITHUB_PAGES_TOKEN 입력 후 동기화와 공개 확인을 실행할 수 있습니다.',
        credentialsTitle: '자동 포스팅 연결',
        credentialPanelTitle: '자동 포스팅 연결',
        credentialsCopy: '저장은 이 브라우저에만 유지됩니다. 실제 자동 포스팅은 env 블록을 로컬 파일에 반영하거나 GitHub Actions secrets로 동기화해야 연결됩니다.',
        blueskyHandle: 'Bluesky handle',
        blueskyAppPassword: 'Bluesky 앱 패스워드',
        devtoApiKey: 'Dev.to API key',
        saveCredentials: '입력값 저장',
        clearCredentials: '입력값 삭제',
        copyEnvBlock: 'env 블록 복사',
        copyPostCommand: '자동 포스팅 명령 복사',
        copySecretSyncCommand: 'GitHub secrets 동기화 명령 복사',
        runPostingNow: '지금 자동 포스팅 실행',
        postingRunStarted: '자동 포스팅 실행 시작됨',
        postingRunHelp: '입력값 저장만으로는 자동 게시가 즉시 실행되지 않습니다. GitHub secrets 동기화 후 이 버튼으로 publishing workflow를 dry_run=false로 실행하세요.',
        credentialNote: '브라우저 저장은 자동 포스팅 실행 환경에 직접 전달되지 않습니다. env 블록을 docs/environment variables.md에 붙여넣은 뒤 secrets 동기화 명령을 실행하면 GitHub Actions 자동 포스팅에도 반영됩니다.',
        credentialsSaved: '저장됨',
        credentialsCleared: '삭제됨',
        missingCredentials: '필수값 누락',
        atmTitle: '게시 여부 확인',
        atmCopy: '공개 게시물을 확인해 일치 항목만 완료 표시합니다.',
        atmRun: '게시 확인 및 완료 반영',
        overviewVerify: '공개 확인',
        enableBadge: '뱃지 켜기',
        badgeReady: '뱃지 준비됨',
        searchPlaceholder: '토픽, 매체, 언어, 상태 검색',
        allPlatforms: '모든 매체',
        allLanguages: '모든 언어',
        allStatuses: '모든 상태',
        manualOnly: '수동만',
        automaticOnly: '자동화만',
        allModes: '전체',
        activeOnly: '진행 항목만',
        showDone: '완료 포함',
        dueOnly: '게시 예정만',
        empty: '현재 필터와 일치하는 초안이 없습니다.',
        emptyTitle: '지금 게시할 수동 항목이 없습니다',
        emptyNext: '다음 수동 게시 예정',
        emptyLatest: '최근 게시',
        noRecord: '기록 없음',
        none: '없음',
        today: '오늘',
        dayAgo: '일 전',
        daysAgo: '일 전',
        postedWord: '게시',
        waitingWord: '대기',
        failedWord: '실패',
        lastPosted: '최근 게시',
        lastUpdate: '최근 갱신',
        appStatusTitle: '앱 운영 상태',
        appStatusSummary: '앱별 묶음',
        flutterSdk: 'Flutter SDK',
        flutterDependencyVersions: 'Flutter/플러그인 버전',
        flutterPlugin: '플러그인',
        dependencyStatusLabel: '상태',
        dependencyResolved: '해결 버전',
        dependencyDeclared: '선언 버전',
        dependencySource: '출처',
        releaseTitle: 'GitHub에 올릴 릴리즈 후보',
        releaseSummary: '상태',
        releaseCandidate: '릴리즈 후보',
        plannedDate: '예정일',
        githubReleasedAt: 'GitHub 공개일',
        githubRelease: 'GitHub Release',
        approvePublicRelease: '공개 승인',
        publicReleaseApproved: '공개 승인됨',
        publicApprovalNote: 'Dashboard manual approval after public store release confirmation.',
        storeTitle: 'App Store / Play Store 현재 공개 버전',
        storeSummary: '현재 표시',
        currentVersion: '현재 버전',
        releasedDate: '현재 버전 게시일',
        releaseNotes: '출시 정보',
        releaseSyncStatus: 'GitHub Release 확인',
        releaseSyncSkipped: '토큰 없음으로 스킵',
        releaseSyncSynced: '확인 완료',
        releaseSyncNotFound: '릴리즈 없음',
        releaseSyncUnknown: '확인 기록 없음',
        checkedAt: '최근 확인',
        noStore: '스토어 없음',
        noRelease: '릴리즈 후보 없음',
        blogTitle: '블로그 상태',
        blogSummary: '상태',
        blogPlatformName: 'Blog',
        blogMode: '콘텐츠',
        platformStatusTitle: '매체별 상태',
        siteStatusTitle: '사이트 갱신 상태',
        pricingStatusTitle: '유료 제품 가격',
        pricingStatusSummary: '유료 다운로드, Pro, AI 크레딧',
        paidProduct: '유료 제품',
        paidDownload: '유료 다운로드',
        aiCredit: 'AI 크레딧',
        aiCreditMarginProfit: 'AI 원가 대비 흑자',
        aiCreditMarginLoss: 'AI 원가 대비 적자',
        aiCreditEconomics: 'AI 원가 비교',
        aiProviderCost: '예상 공급자 원가',
        aiNetRevenue: '수수료 차감 후 매출',
        aiPricingCheckChanged: 'AI 요금 변경 확인 필요',
        aiPricingCheckWarning: 'AI 요금 확인 경고',
        aiPricingManualOk: 'AI 요금 자동 확인 실패, 수동 확인 완료',
        aiPricingCheckedAt: 'AI 요금 확인',
        pricingModel: '가격 모델',
        priceLabel: '가격',
        priceCheckNeeded: '스토어 확인 필요',
        localPriceMetadata: '공개 랜딩 페이지 가격 메타데이터',
        iapPriceNotRecorded: '스토어 인앱 구매 가격이 로컬에 기록되어 있지 않음',
        aiCreditPriceNotRecorded: 'AI 크레딧 가격이 로컬에 기록되어 있지 않음',
        appsWord: '앱',
        appStore: 'App Store',
        playStore: 'Play Store',
        qualityStatusTitle: '발행 품질 점검',
        qualityStatusSummary: '템플릿 점수와 반복어 경고',
        socialQuality: '소셜 템플릿',
        syndicationQuality: '신디케이션',
        repetitionWarnings: '반복어 경고',
        copyRepetitionFixCommand: '반복어 수정 명령 복사',
        copyRepetitionWarnings: '경고 목록 복사',
        repetitionFixCommand: 'python3 scripts/fix_social_repetition.py',
        noWarnings: '경고 없음',
        qualityError: '점검 오류',
        siteStatusSummary: '메인 홈페이지와 앱 상세 페이지',
        mainHome: '메인 홈페이지',
        landingUpdated: '페이지 갱신',
        homePageUpdated: '메인 홈페이지 갱신',
        appPageUpdated: '앱 소개 페이지 갱신',
        screenshotsUpdated: '스크린샷 갱신',
        assetsUpdated: '아이콘/자산 갱신',
        screenshotCount: '스크린샷',
        latestPublished: '최근 게시',
        nextScheduled: '다음 게시 예정',
        publicApproved: '공개 승인',
        publicPending: '공개 미승인',
        completedAt: '게시 완료',
        copyMarkdown: '마크다운 복사',
        copyFormatted: '서식 본문 복사',
        copyPost: '게시글 복사',
        copy: '복사',
        publishTitle: '제목',
        publishBody: '본문',
        publishTags: '태그',
        tagItem: '태그',
        topics: '토픽',
        topic: '토픽',
        canonicalUrl: 'Canonical URL',
        coverImage: '커버 이미지',
        featuredImage: '대표 이미지 URL',
        storyPreviewSubtitle: 'Story preview 부제',
        seoTitle: 'SEO title',
        seoDescription: 'SEO description',
        copyBodyAndOpen: '본문 복사 후 열기',
        copyAndOpen: '복사 후 열기',
        copyFormattedAndOpen: '서식 복사 후 열기',
        markDone: '게시 완료 반영',
        undoDone: '완료 취소',
        copyImage: '이미지 복사',
        openImage: '이미지 열기',
        linkCardOnly: '링크 카드 사용',
        noImageAttach: '이미지 첨부 없이 링크 카드로 게시',
        showDetails: '상세 보기',
        hideDetails: '상세 숨기기',
        overviewDue: '오늘 할 일',
        overviewManual: '수동 대기',
        overviewPosted: '게시 완료',
        overviewSync: '동기화',
        dueTag: '예정',
        doneTag: '완료',
        automaticVerified: '자동 확인',
        publicVerified: '공개 페이지 확인',
        manualVerified: '직접 완료',
        verificationPendingReason: '확인 결과',
        variantTag: '대안',
        manualMode: '수동 게시 필요',
        automaticMode: '자동화 대상',
        showVariants: '대안 보기',
        hideVariants: '대안 숨기기',
        variantsCount: '개 대안',
        copied: '복사됨',
        imageCopied: '이미지 복사됨',
        opened: '열림',
        saving: '저장 중',
        saveFailed: '저장 실패',
        openImageFallback: '이미지 열기',
        length: '길이',
        dueAt: '게시 예정',
        dateLocale: 'ko-KR',
      }},
      en: {{
        appTitle: 'ONNELLAB Publish Status Dashboard',
        total: 'total',
        due: 'due',
        manual: 'manual',
        posted: 'posted',
        loading: 'loading',
        syncing: 'syncing',
        synced: 'synced',
        viewOnly: 'view only',
        syncError: 'sync error',
        saveError: 'save error',
        tokenPlaceholder: 'ONNELLAB_GITHUB_PAGES_TOKEN',
        advancedSummary: 'Advanced filters and sync',
        filterPanelTitle: 'Search and filters',
        connectSync: 'Connect sync',
        refresh: 'Refresh',
        verifyPublications: 'Check public profiles',
        verifyingPublications: 'Starting check',
        verificationStarted: 'Check started',
        verificationQueued: 'Queued',
        verificationRunning: 'Running',
        verificationCompleted: 'Completed',
        verificationRunLink: 'GitHub Actions run',
        verificationChecked: 'checked',
        verificationAlreadyDone: 'already done',
        verificationNewDone: 'newly done',
        verificationPending: 'unconfirmed',
        verificationNoReport: 'no check record',
        verificationReady: 'Run',
        verificationTokenRequired: 'Token needed',
        verificationFailed: 'Failed',
        verificationTimedOut: 'Check timed out · open the run log for its final status',
        verificationRefreshIn: 'auto refresh',
        secondsShort: 's',
        tokenNeededNote: 'Enter ONNELLAB_GITHUB_PAGES_TOKEN to run sync and public profile checks.',
        credentialsTitle: 'Automated posting connection',
        credentialPanelTitle: 'Automated posting connection',
        credentialsCopy: 'Saved inputs stay in this browser only. Automated posting is connected after you apply the env block locally or sync it to GitHub Actions secrets.',
        blueskyHandle: 'Bluesky handle',
        blueskyAppPassword: 'Bluesky app password',
        devtoApiKey: 'Dev.to API key',
        saveCredentials: 'Save inputs',
        clearCredentials: 'Clear inputs',
        copyEnvBlock: 'Copy env block',
        copyPostCommand: 'Copy posting command',
        copySecretSyncCommand: 'Copy GitHub secrets sync command',
        runPostingNow: 'Run automated posting now',
        postingRunStarted: 'Automated posting started',
        postingRunHelp: 'Saving inputs alone does not run posting immediately. Sync GitHub secrets, then use this button to run the publishing workflow with dry_run=false.',
        credentialNote: 'Browser storage is not passed to the posting runtime. Paste the env block into docs/environment variables.md, then run the secrets sync command to connect GitHub Actions automated posting.',
        credentialsSaved: 'Saved',
        credentialsCleared: 'Cleared',
        missingCredentials: 'Missing required values',
        atmTitle: 'Check published posts',
        atmCopy: 'Check public posts and mark matching items done.',
        atmRun: 'Check and mark done',
        overviewVerify: 'Public check',
        enableBadge: 'Enable badge',
        badgeReady: 'Badge ready',
        searchPlaceholder: 'Search topic, platform, language, status',
        allPlatforms: 'All platforms',
        allLanguages: 'All languages',
        allStatuses: 'All statuses',
        manualOnly: 'Manual only',
        automaticOnly: 'Automated only',
        allModes: 'All',
        activeOnly: 'Active only',
        showDone: 'Show done',
        dueOnly: 'Due only',
        empty: 'No drafts match the current filters.',
        emptyTitle: 'No manual items are due now',
        emptyNext: 'next manual publish',
        emptyLatest: 'latest posted',
        noRecord: 'no record',
        none: 'none',
        today: 'today',
        dayAgo: 'day ago',
        daysAgo: 'days ago',
        postedWord: 'posted',
        waitingWord: 'waiting',
        failedWord: 'failed',
        lastPosted: 'last posted',
        lastUpdate: 'last update',
        appStatusTitle: 'App operation status',
        appStatusSummary: 'grouped by app',
        flutterSdk: 'Flutter SDK',
        flutterDependencyVersions: 'Flutter/plugin versions',
        flutterPlugin: 'Plugin',
        dependencyStatusLabel: 'Status',
        dependencyResolved: 'Resolved',
        dependencyDeclared: 'Declared',
        dependencySource: 'Source',
        releaseTitle: 'GitHub Release candidates',
        releaseSummary: 'status',
        releaseCandidate: 'release candidate',
        plannedDate: 'planned date',
        githubReleasedAt: 'GitHub released',
        githubRelease: 'GitHub Release',
        approvePublicRelease: 'Approve public',
        publicReleaseApproved: 'public approved',
        publicApprovalNote: 'Dashboard manual approval after public store release confirmation.',
        storeTitle: 'Current App Store / Play Store versions',
        storeSummary: 'currently shown',
        currentVersion: 'current version',
        releasedDate: 'current version published',
        releaseNotes: 'release info',
        releaseSyncStatus: 'GitHub Release check',
        releaseSyncSkipped: 'skipped: no token',
        releaseSyncSynced: 'checked',
        releaseSyncNotFound: 'release not found',
        releaseSyncUnknown: 'no check record',
        checkedAt: 'last checked',
        noStore: 'no store',
        noRelease: 'no release candidate',
        blogTitle: 'Blog status',
        blogSummary: 'status',
        blogPlatformName: 'Blog',
        blogMode: 'Content',
        platformStatusTitle: 'Platform status',
        siteStatusTitle: 'Website update status',
        pricingStatusTitle: 'Paid product pricing',
        pricingStatusSummary: 'paid downloads, Pro, and AI credits',
        paidProduct: 'paid product',
        paidDownload: 'Paid download',
        aiCredit: 'AI credit',
        aiCreditMarginProfit: 'Profit vs AI cost',
        aiCreditMarginLoss: 'Loss vs AI cost',
        aiCreditEconomics: 'AI cost comparison',
        aiProviderCost: 'estimated provider cost',
        aiNetRevenue: 'net revenue after store fee',
        aiPricingCheckChanged: 'AI pricing review needed',
        aiPricingCheckWarning: 'AI pricing check warning',
        aiPricingManualOk: 'AI pricing manually verified after automatic check failed',
        aiPricingCheckedAt: 'AI pricing checked',
        pricingModel: 'pricing model',
        priceLabel: 'price',
        priceCheckNeeded: 'Check store',
        localPriceMetadata: 'Public landing page metadata',
        iapPriceNotRecorded: 'Store in-app purchase price not recorded locally',
        aiCreditPriceNotRecorded: 'AI credit price not recorded locally',
        appsWord: 'apps',
        appStore: 'App Store',
        playStore: 'Play Store',
        qualityStatusTitle: 'Publishing quality check',
        qualityStatusSummary: 'template scores and repeated phrase warnings',
        socialQuality: 'Social templates',
        syndicationQuality: 'Syndication',
        repetitionWarnings: 'repetition warnings',
        copyRepetitionFixCommand: 'Copy fix command',
        copyRepetitionWarnings: 'Copy warnings',
        repetitionFixCommand: 'python3 scripts/fix_social_repetition.py',
        noWarnings: 'no warnings',
        qualityError: 'quality check error',
        siteStatusSummary: 'home and app landing pages',
        mainHome: 'Main home',
        landingUpdated: 'page updated',
        homePageUpdated: 'home page updated',
        appPageUpdated: 'app page updated',
        screenshotsUpdated: 'screenshots updated',
        assetsUpdated: 'icon/assets updated',
        screenshotCount: 'screenshots',
        latestPublished: 'latest published',
        nextScheduled: 'next scheduled',
        publicApproved: 'public approved',
        publicPending: 'public pending',
        completedAt: 'posted',
        copyMarkdown: 'Copy markdown',
        copyFormatted: 'Copy formatted body',
        copyPost: 'Copy post',
        copy: 'Copy',
        publishTitle: 'Title',
        publishBody: 'Body',
        publishTags: 'Tags',
        tagItem: 'Tag',
        topics: 'Topics',
        topic: 'Topic',
        canonicalUrl: 'Canonical URL',
        coverImage: 'Cover image',
        featuredImage: 'Featured image URL',
        storyPreviewSubtitle: 'Story preview subtitle',
        seoTitle: 'SEO title',
        seoDescription: 'SEO description',
        copyBodyAndOpen: 'Copy body and open',
        copyAndOpen: 'Copy and open',
        copyFormattedAndOpen: 'Copy formatted and open',
        markDone: 'Apply publish completion',
        undoDone: 'Undo done',
        copyImage: 'Copy image',
        openImage: 'Open image',
        linkCardOnly: 'Link card only',
        noImageAttach: 'Post with the link card; do not attach the image',
        showDetails: 'Show details',
        hideDetails: 'Hide details',
        overviewDue: 'Due today',
        overviewManual: 'Waiting',
        overviewPosted: 'Posted',
        overviewSync: 'Sync',
        dueTag: 'due',
        doneTag: 'done',
        automaticVerified: 'Auto verified',
        publicVerified: 'Public page',
        manualVerified: 'Manual done',
        verificationPendingReason: 'check result',
        variantTag: 'variant',
        manualMode: 'Manual publish',
        automaticMode: 'Automated',
        showVariants: 'Show alternatives',
        hideVariants: 'Hide alternatives',
        variantsCount: 'alternatives',
        copied: 'Copied',
        imageCopied: 'Image copied',
        opened: 'Opened',
        saving: 'Saving',
        saveFailed: 'Save failed',
        openImageFallback: 'Open image',
        length: 'length',
        dueAt: 'due',
        dateLocale: 'en-US',
      }},
    }};
    let currentLang = ['ko', 'en'].includes(params.get('lang') || '') ? params.get('lang') : localStorage.getItem(langKey) || 'ko';
    if (!['ko', 'en'].includes(currentLang)) currentLang = 'ko';
    function t(key) {{
      return messages[currentLang][key] || messages.ko[key] || key;
    }}
    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    const dueCountEls = document.querySelectorAll('.due-count');
    const manualCountEl = document.getElementById('manual-count');
    const postedCountEl = document.getElementById('posted-count');
    const syncStateLarge = document.getElementById('sync-state-large');
    const filters = {{
      search: document.getElementById('search'),
      platform: document.getElementById('platform'),
      language: document.getElementById('language'),
      status: document.getElementById('status'),
      mode: document.getElementById('mode'),
      visibility: document.getElementById('visibility'),
    }};
    const tokenInput = document.getElementById('token');
    const credentialInputs = {{
      blueskyHandle: document.getElementById('bluesky-handle'),
      blueskyAppPassword: document.getElementById('bluesky-app-password'),
      devtoApiKey: document.getElementById('devto-api-key'),
    }};
    const credentialOutput = document.getElementById('credential-output');
    const syncAuthPanel = document.getElementById('sync-auth');
    const badgeButton = document.getElementById('enable-badge');
    const refreshButton = document.getElementById('refresh-state');
    const verifyButtonLarge = document.getElementById('verify-publications-large');
    const verifyButtonPrimary = document.getElementById('verify-publications-primary');
    const verifyStateLarge = document.getElementById('verify-state-large');
    const verificationRunLink = document.getElementById('verification-run-link');
    const syncButtonLarge = document.getElementById('refresh-state-large');
    const langToggle = document.getElementById('lang-toggle');
    const variantToggle = document.getElementById('toggle-variants');
    const viewButtons = document.querySelectorAll('[data-view]');
    const platformSummary = document.getElementById('platform-summary');
    const platformStatusSummary = document.getElementById('platform-status-summary');
    const appStatusGrid = document.getElementById('app-status-grid');
    const appStatusSummary = document.getElementById('app-status-summary');
    const siteStatusGrid = document.getElementById('site-status-grid');
    const siteStatusSummary = document.getElementById('site-status-summary');
    const pricingStatusGrid = document.getElementById('pricing-status-grid');
    const pricingStatusSummary = document.getElementById('pricing-status-summary');
    const qualityStatusGrid = document.getElementById('quality-status-grid');
    const qualityStatusSummary = document.getElementById('quality-status-summary');
    let remoteState = JSON.parse(document.getElementById('manual-state-data').textContent);
    remoteState.done ||= {{}};
    let remoteSha = '';
    let showVariants = false;
    let currentView = 'due';
    let verifyCountdownTimer = null;
    let verifyCountdownRemaining = 0;
    let latestVerificationRunUrl = '';
    const githubRequestTimeoutMs = 15000;

    tokenInput.value = localStorage.getItem(tokenKey) || '';

    function applyTranslations() {{
      document.documentElement.lang = currentLang;
      document.title = t('appTitle');
      document.getElementById('app-title').textContent = t('appTitle');
      document.getElementById('atm-title').textContent = t('atmTitle');
      document.getElementById('atm-copy').textContent = t('atmCopy');
      verifyButtonPrimary.textContent = t('atmRun');
      document.getElementById('overview-due-label').textContent = t('overviewDue');
      document.getElementById('overview-manual-label').textContent = t('overviewManual');
      document.getElementById('overview-posted-label').textContent = t('overviewPosted');
      document.getElementById('overview-sync-label').textContent = t('overviewSync');
      document.getElementById('overview-verify-label').textContent = t('overviewVerify');
      document.getElementById('app-status-title').textContent = t('appStatusTitle');
      document.getElementById('platform-status-title').textContent = t('platformStatusTitle');
      document.getElementById('site-status-title').textContent = t('siteStatusTitle');
      document.getElementById('pricing-status-title').textContent = t('pricingStatusTitle');
      document.getElementById('quality-status-title').textContent = t('qualityStatusTitle');
      document.getElementById('filter-panel-title').textContent = t('filterPanelTitle');
      tokenInput.placeholder = t('tokenPlaceholder');
      document.getElementById('save-token').textContent = t('connectSync');
      document.getElementById('refresh-state').textContent = t('refresh');
      document.getElementById('token-note').textContent = t('tokenNeededNote');
      document.getElementById('credentials-title').textContent = t('credentialsTitle');
      document.getElementById('credential-panel-title').textContent = t('credentialPanelTitle');
      document.getElementById('credentials-copy').textContent = t('credentialsCopy');
      document.getElementById('bluesky-handle-label').textContent = t('blueskyHandle');
      document.getElementById('bluesky-password-label').textContent = t('blueskyAppPassword');
      document.getElementById('devto-key-label').textContent = t('devtoApiKey');
      document.getElementById('save-credentials').textContent = t('saveCredentials');
      document.getElementById('copy-env-block').textContent = t('copyEnvBlock');
      document.getElementById('copy-secret-sync-command').textContent = t('copySecretSyncCommand');
      document.getElementById('copy-post-command').textContent = t('copyPostCommand');
      document.getElementById('run-posting-now').textContent = t('runPostingNow');
      document.getElementById('clear-credentials').textContent = t('clearCredentials');
      document.getElementById('posting-run-note').textContent = t('postingRunHelp');
      document.getElementById('credential-note').textContent = t('credentialNote');
      badgeButton.textContent = t('enableBadge');
      updateVariantToggle();
      filters.search.placeholder = t('searchPlaceholder');
      filters.platform.options[0].textContent = t('allPlatforms');
      filters.language.options[0].textContent = t('allLanguages');
      filters.status.options[0].textContent = t('allStatuses');
      filters.mode.options[0].textContent = t('manualOnly');
      filters.mode.options[1].textContent = t('automaticOnly');
      filters.mode.options[2].textContent = t('allModes');
      filters.visibility.options[0].textContent = t('dueOnly');
      filters.visibility.options[1].textContent = t('activeOnly');
      filters.visibility.options[2].textContent = t('showDone');
      empty.textContent = t('empty');
      langToggle.textContent = currentLang === 'ko' ? 'English' : '한국어';
      setSync(syncStateLarge.dataset.state || (githubToken() ? 'synced' : 'viewOnly'));
      setVerifyState(verifyStateLarge.dataset.state || (githubToken() ? 'verificationReady' : 'verificationTokenRequired'), verifyCountdownRemaining);
      renderVerificationRunLink();
      syncViewButtons();
      renderAppStatusSummary();
      renderSiteStatusSummary();
      renderPricingStatusSummary();
      renderQualityStatusSummary();
    }}

    function syncViewButtons() {{
      viewButtons.forEach((button) => {{
        button.classList.toggle('is-active', button.dataset.view === currentView);
      }});
    }}

    function applyView(view) {{
      currentView = view;
      if (view === 'due') {{
        filters.mode.value = 'manual';
        filters.visibility.value = 'due';
        filters.status.value = '';
      }} else if (view === 'manual') {{
        filters.mode.value = 'manual';
        filters.visibility.value = 'active';
        filters.status.value = '';
      }} else if (view === 'done') {{
        filters.mode.value = '';
        filters.visibility.value = 'all';
        filters.status.value = '';
      }} else {{
        filters.mode.value = '';
        filters.visibility.value = 'all';
        filters.status.value = '';
      }}
      render();
    }}

    function optionize(select, values) {{
      values.forEach((value) => {{
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
    }}
    function syncFilterOptions() {{
      const current = {{
        platform: filters.platform.value,
        language: filters.language.value,
        status: filters.status.value,
      }};
      [filters.platform, filters.language, filters.status].forEach((select) => {{
        while (select.options.length > 1) select.remove(1);
      }});
      optionize(filters.platform, [...new Set(items.map((item) => item.platform_label))].sort());
      optionize(filters.language, [...new Set(items.map((item) => item.language))].sort());
      optionize(filters.status, [...new Set(items.map((item) => item.status))].sort());
      Object.entries(current).forEach(([key, value]) => {{
        if ([...filters[key].options].some((option) => option.value === value)) filters[key].value = value;
      }});
      applyTranslations();
    }}
    syncFilterOptions();

    function githubToken() {{
      return localStorage.getItem(tokenKey) || tokenInput.value.trim();
    }}

    function shellQuote(value) {{
      return "'" + String(value || '').replace(/'/g, "'\\\\''") + "'";
    }}

    function credentialValues() {{
      return {{
        blueskyHandle: credentialInputs.blueskyHandle.value.trim(),
        blueskyAppPassword: credentialInputs.blueskyAppPassword.value.trim(),
        devtoApiKey: credentialInputs.devtoApiKey.value.trim(),
      }};
    }}

    function loadCredentials() {{
      try {{
        const saved = JSON.parse(localStorage.getItem(credentialStorageKey) || '{{}}');
        credentialInputs.blueskyHandle.value = saved.blueskyHandle || credentialInputs.blueskyHandle.value || 'onnellab.bsky.social';
        credentialInputs.blueskyAppPassword.value = saved.blueskyAppPassword || '';
        credentialInputs.devtoApiKey.value = saved.devtoApiKey || '';
      }} catch (error) {{
        console.warn(error);
      }}
      updateCredentialOutput();
    }}

    function saveCredentials(button) {{
      localStorage.setItem(credentialStorageKey, JSON.stringify(credentialValues()));
      updateCredentialOutput();
      flash(button, t('credentialsSaved'));
    }}

    function clearCredentials(button) {{
      localStorage.removeItem(credentialStorageKey);
      credentialInputs.blueskyHandle.value = 'onnellab.bsky.social';
      credentialInputs.blueskyAppPassword.value = '';
      credentialInputs.devtoApiKey.value = '';
      updateCredentialOutput();
      flash(button, t('credentialsCleared'));
    }}

    function missingCredentialNames(values) {{
      return [
        values.blueskyHandle ? '' : 'BLUESKY_HANDLE',
        values.blueskyAppPassword ? '' : 'BLUESKY_APP_PASSWORD',
        values.devtoApiKey ? '' : 'DEVTO_API_KEY',
      ].filter(Boolean);
    }}

    function credentialEnvBlock() {{
      const values = credentialValues();
      return [
        '# ONNELLAB automated posting credentials',
        `export BLUESKY_HANDLE=${{shellQuote(values.blueskyHandle)}}`,
        `export BLUESKY_APP_PASSWORD=${{shellQuote(values.blueskyAppPassword)}}`,
        `export DEVTO_API_KEY=${{shellQuote(values.devtoApiKey)}}`,
      ].join('\\n') + '\\n';
    }}

    function postingCommand() {{
      return 'python3 scripts/run_with_local_env.py -- python3 scripts/post_core_distribution.py';
    }}

    function secretSyncCommand() {{
      return 'python3 scripts/run_with_local_env.py -- python3 scripts/sync_publishing_secrets.py';
    }}

    function updateCredentialOutput() {{
      const missing = missingCredentialNames(credentialValues());
      credentialOutput.value = missing.length
        ? `${{t('missingCredentials')}}: ${{missing.join(', ')}}\\n\\n${{credentialEnvBlock()}}`
        : credentialEnvBlock() + '\\n' + secretSyncCommand() + '\\n' + postingCommand();
    }}

    async function copyCredentialEnv(button) {{
      updateCredentialOutput();
      await copyText(credentialEnvBlock(), button);
    }}

    async function copyPostingCommand(button) {{
      updateCredentialOutput();
      await copyText(postingCommand(), button);
    }}

    async function copySecretSyncCommand(button) {{
      updateCredentialOutput();
      await copyText(secretSyncCommand(), button);
    }}

    async function runPostingNow(button) {{
      if (!githubToken()) {{
        setSync('viewOnly');
        revealTokenInput();
        return;
      }}
      button.disabled = true;
      try {{
        await githubRequest(`/repos/${{stateRepo}}/actions/workflows/publishing.yml/dispatches`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ ref: stateBranch, inputs: {{ dry_run: 'false' }} }}),
        }});
        flash(button, t('postingRunStarted'));
        await refreshVerificationRunLink();
      }} catch (error) {{
        flash(button, t('verificationFailed'));
        setSync('syncError');
        console.error(error);
      }} finally {{
        button.disabled = false;
      }}
    }}

    function setSync(label) {{
      syncStateLarge.dataset.state = label;
      const value = messages[currentLang][label] || label;
      setStateContent(syncStateLarge, value, label === 'syncing');
      syncButtonLarge.classList.toggle('is-working', label === 'syncing');
      syncButtonLarge.disabled = false;
      syncButtonLarge.setAttribute('aria-disabled', 'false');
      verifyButtonLarge.disabled = false;
      verifyButtonLarge.setAttribute('aria-disabled', 'false');
      verifyButtonPrimary.disabled = false;
      verifyButtonPrimary.setAttribute('aria-disabled', 'false');
      document.getElementById('token-note').hidden = Boolean(githubToken());
      if (githubToken()) syncAuthPanel.hidden = true;
      if (!githubToken()) setVerifyState('verificationTokenRequired');
    }}

    function setVerifyState(label, countdown = 0) {{
      verifyStateLarge.dataset.state = label;
      const isWorking = ['verifyingPublications', 'verificationStarted', 'verificationQueued', 'verificationRunning'].includes(label);
      const subtext = label === 'verificationStarted' && countdown > 0
        ? `${{t('verificationRefreshIn')}} ${{countdown}}${{t('secondsShort')}}`
        : '';
      setStateContent(verifyStateLarge, messages[currentLang][label] || label, isWorking, subtext);
      verifyButtonLarge.classList.toggle('is-working', isWorking);
      verifyButtonLarge.disabled = false;
      verifyButtonLarge.setAttribute('aria-disabled', 'false');
      verifyButtonPrimary.disabled = false;
      verifyButtonPrimary.setAttribute('aria-disabled', 'false');
    }}

    function setVerificationRunLink(run) {{
      latestVerificationRunUrl = run?.html_url || latestVerificationRunUrl;
      renderVerificationRunLink();
    }}

    function clearVerificationRunLink() {{
      latestVerificationRunUrl = '';
      renderVerificationRunLink();
    }}

    function renderVerificationRunLink() {{
      verificationRunLink.hidden = !latestVerificationRunUrl;
      verificationRunLink.href = latestVerificationRunUrl || '#';
      verificationRunLink.textContent = t('verificationRunLink');
    }}

    function setStateContent(element, label, isWorking = false, subtext = '') {{
      element.textContent = '';
      element.classList.toggle('state-line', isWorking || Boolean(subtext));
      if (isWorking) {{
        const spinner = document.createElement('span');
        spinner.className = 'spinner';
        spinner.setAttribute('aria-hidden', 'true');
        element.appendChild(spinner);
      }}
      const labelText = document.createElement('span');
      labelText.textContent = label;
      element.appendChild(labelText);
      if (subtext) {{
        const small = document.createElement('span');
        small.className = 'state-subtext';
        small.textContent = subtext;
        element.appendChild(small);
      }}
    }}

    function clearVerifyCountdown() {{
      if (verifyCountdownTimer) clearInterval(verifyCountdownTimer);
      verifyCountdownTimer = null;
      verifyCountdownRemaining = 0;
    }}

    function startVerifyCountdown(seconds) {{
      clearVerifyCountdown();
      verifyCountdownRemaining = seconds;
      setVerifyState('verificationStarted', verifyCountdownRemaining);
      verifyCountdownTimer = setInterval(() => {{
        verifyCountdownRemaining -= 1;
        if (verifyCountdownRemaining <= 0) {{
          clearVerifyCountdown();
          loadRemoteState({{ refreshDashboardData: true }});
          return;
        }}
        setVerifyState('verificationStarted', verifyCountdownRemaining);
      }}, 1000);
    }}

    function workflowRunLabel(run) {{
      if (!run) return 'verificationStarted';
      if (run.status === 'queued' || run.status === 'requested' || run.status === 'waiting' || run.status === 'pending') return 'verificationQueued';
      if (run.status === 'in_progress') return 'verificationRunning';
      if (run.status === 'completed' && run.conclusion === 'success') return 'verificationCompleted';
      if (run.status === 'completed') return 'verificationFailed';
      return 'verificationStarted';
    }}

    function verificationReportCoversRun(run) {{
      const reportDate = parseDate(verificationReport?.checked_at);
      const runDate = parseDate(run?.created_at);
      return Boolean(reportDate && runDate && reportDate.getTime() >= runDate.getTime());
    }}

    function completedVerificationLabel(run) {{
      if (run?.conclusion === 'success' || verificationReportCoversRun(run)) return 'verificationCompleted';
      return 'verificationFailed';
    }}

    async function reconcileCompletedVerification(run, maxAttempts = 10) {{
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {{
        await loadRemoteState({{
          refreshDashboardData: attempt === 0,
          preserveVerifyState: true,
          skipRunLinkRefresh: true,
        }});
        if (verificationReportCoversRun(run)) return true;
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }}
      return false;
    }}

    async function latestVerificationRun() {{
      const query = new URLSearchParams({{
        branch: stateBranch,
        event: 'workflow_dispatch',
        per_page: '1',
        _: String(Date.now()),
      }});
      const data = await githubRequest(`/repos/${{stateRepo}}/actions/workflows/verify-manual-publications.yml/runs?${{query.toString()}}`);
      return data.workflow_runs?.[0] || null;
    }}

    async function refreshVerificationRunLink() {{
      if (!githubToken()) {{
        clearVerificationRunLink();
        return;
      }}
      try {{
        setVerificationRunLink(await latestVerificationRun());
      }} catch (error) {{
        console.warn(error);
      }}
    }}

    function isDispatchedVerificationRun(run, previousRunId, dispatchedAt) {{
      if (!run) return false;
      if (previousRunId && String(run.id) === String(previousRunId)) return false;
      const createdAt = parseDate(run.created_at);
      if (!createdAt || !dispatchedAt) return !previousRunId;
      return createdAt.getTime() >= dispatchedAt - 15000;
    }}

    async function pollVerificationRun({{ previousRunId = null, dispatchedAt = 0, maxAttempts = 24 }} = {{}}) {{
      clearVerifyCountdown();
      let run = null;
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {{
        try {{
          const candidate = await latestVerificationRun();
          if (!isDispatchedVerificationRun(candidate, previousRunId, dispatchedAt)) {{
            setVerifyState('verificationQueued');
            await new Promise((resolve) => setTimeout(resolve, attempt < 4 ? 5000 : 10000));
            continue;
          }}
          run = candidate;
          setVerificationRunLink(run);
          setVerifyState(workflowRunLabel(run));
          if (run?.status === 'completed') {{
            const reportReady = await reconcileCompletedVerification(run);
            setVerifyState(reportReady ? completedVerificationLabel(run) : 'verificationTimedOut');
            return;
          }}
        }} catch (error) {{
          console.warn(error);
        }}
        await new Promise((resolve) => setTimeout(resolve, attempt < 4 ? 5000 : 10000));
      }}
      try {{
        const finalRun = await latestVerificationRun();
        if (isDispatchedVerificationRun(finalRun, previousRunId, dispatchedAt) && finalRun?.status === 'completed') {{
          setVerificationRunLink(finalRun);
          const reportReady = await reconcileCompletedVerification(finalRun);
          setVerifyState(reportReady ? completedVerificationLabel(finalRun) : 'verificationTimedOut');
          return;
        }}
      }} catch (error) {{
        console.warn(error);
      }}
      setVerifyState('verificationTimedOut');
    }}

    function revealTokenInput() {{
      syncAuthPanel.hidden = false;
      tokenInput.classList.add('needs-token');
      tokenInput.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
      tokenInput.focus({{ preventScroll: true }});
      setTimeout(() => tokenInput.classList.remove('needs-token'), 1600);
    }}

    function decodeBase64Unicode(value) {{
      const binary = atob(value.replace(/\\n/g, ''));
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    }}

    function encodeBase64Unicode(value) {{
      const bytes = new TextEncoder().encode(value);
      let binary = '';
      bytes.forEach((byte) => binary += String.fromCharCode(byte));
      return btoa(binary);
    }}

    async function githubRequest(path, options = {{}}) {{
      const token = githubToken();
      const authHeaders = token ? {{ 'Authorization': 'Bearer ' + token }} : {{}};
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), githubRequestTimeoutMs);
      try {{
        const response = await fetch('https://api.github.com' + path, {{
          cache: 'no-store',
          ...options,
          signal: options.signal || controller.signal,
          headers: {{
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            ...authHeaders,
            ...(options.headers || {{}}),
          }},
        }});
        const text = await response.text();
        const data = text ? JSON.parse(text) : {{}};
        if (!response.ok) throw new Error(data.message || 'GitHub request failed');
        return data;
      }} finally {{
        clearTimeout(timeoutId);
      }}
    }}

    async function triggerPublicationVerification() {{
      if (!githubToken()) {{
        setVerifyState('verificationTokenRequired');
        revealTokenInput();
        return;
      }}
      setVerifyState('verifyingPublications');
      clearVerificationRunLink();
      verifyButtonLarge.disabled = true;
      verifyButtonPrimary.disabled = true;
      try {{
        let previousRun = null;
        try {{
          previousRun = await latestVerificationRun();
        }} catch (lookupError) {{
          console.warn(lookupError);
        }}
        const dispatchedAt = Date.now();
        await githubRequest(`/repos/${{stateRepo}}/actions/workflows/verify-manual-publications.yml/dispatches`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ ref: stateBranch, inputs: {{ visual_public_pages: 'true' }} }}),
        }});
        setVerifyState('verificationQueued');
        await pollVerificationRun({{ previousRunId: previousRun?.id || null, dispatchedAt }});
      }} catch (error) {{
        clearVerifyCountdown();
        setVerifyState('verificationFailed');
        setSync('syncError');
        console.error(error);
      }} finally {{
        verifyButtonLarge.disabled = false;
        verifyButtonPrimary.disabled = false;
      }}
    }}

    function readEmbeddedJson(doc, id) {{
      const element = doc.getElementById(id);
      return element ? JSON.parse(element.textContent || '[]') : [];
    }}

    async function refreshDashboardDataFromPublishedPage() {{
      const url = new URL(window.location.href);
      url.searchParams.set('refresh', String(Date.now()));
      const response = await fetch(url.toString(), {{ cache: 'no-store' }});
      if (!response.ok) throw new Error('Failed to refresh dashboard data');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      items = readEmbeddedJson(doc, 'manual-data');
      releases = readEmbeddedJson(doc, 'release-data');
      blogItems = readEmbeddedJson(doc, 'blog-data');
      storeItems = readEmbeddedJson(doc, 'store-data');
      flutterDependencyItems = readEmbeddedJson(doc, 'flutter-dependency-data');
      siteItems = readEmbeddedJson(doc, 'site-data');
      pricingItems = readEmbeddedJson(doc, 'pricing-data');
      aiProviderPricingStatus = readEmbeddedJson(doc, 'ai-provider-pricing-status-data');
      releaseSyncStatus = readEmbeddedJson(doc, 'release-sync-data');
      verificationReport = readEmbeddedJson(doc, 'verification-report-data');
      syncFilterOptions();
    }}

    async function loadRemoteState(options = {{}}) {{
      clearVerifyCountdown();
      setSync('syncing');
      try {{
        const cacheKey = Date.now();
        const data = await githubRequest(`/repos/${{stateRepo}}/contents/${{statePath}}?ref=${{stateBranch}}&_=${{cacheKey}}`);
        remoteSha = data.sha;
        remoteState = JSON.parse(decodeBase64Unicode(data.content));
        remoteState.done ||= {{}};
        if (options.refreshDashboardData) {{
          try {{
            await refreshDashboardDataFromPublishedPage();
          }} catch (refreshError) {{
            console.warn(refreshError);
          }}
        }}
        try {{
          const reportData = await githubRequest(`/repos/${{stateRepo}}/contents/${{reportPath}}?ref=${{stateBranch}}&_=${{cacheKey}}`);
          verificationReport = JSON.parse(decodeBase64Unicode(reportData.content));
        }} catch (reportError) {{
          console.warn(reportError);
        }}
        setSync(githubToken() ? 'synced' : 'viewOnly');
        if (!options.preserveVerifyState) setVerifyState(githubToken() ? 'verificationReady' : 'verificationTokenRequired');
        render();
        if (!options.skipRunLinkRefresh) await refreshVerificationRunLink();
      }} catch (error) {{
        setSync('syncError');
        console.error(error);
      }}
      render();
    }}

    async function updateAppBadge() {{
      const count = items.filter(isDue).length;
      if (!('setAppBadge' in navigator) || !('clearAppBadge' in navigator)) return;
      try {{
        if (count > 0) await navigator.setAppBadge(count);
        else await navigator.clearAppBadge();
      }} catch (error) {{
        console.warn(error);
      }}
    }}

    async function saveRemoteState(message) {{
      if (!githubToken()) throw new Error('GitHub token is required to save synced state');
      remoteState.updated_at = new Date().toISOString();
      const content = encodeBase64Unicode(JSON.stringify(remoteState, null, 2) + '\\n');
      const payload = {{ message, content, branch: stateBranch }};
      if (remoteSha) payload.sha = remoteSha;
      const data = await githubRequest(`/repos/${{stateRepo}}/contents/${{statePath}}`, {{
        method: 'PUT',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload),
      }});
      remoteSha = data.content.sha;
      setSync('synced');
    }}

    async function saveWithMerge(message, localDone) {{
      try {{
        await saveRemoteState(message);
      }} catch (error) {{
        if (!String(error.message || '').includes('sha')) throw error;
        await loadRemoteState();
        remoteState.done ||= {{}};
        Object.assign(remoteState.done, localDone);
        await saveRemoteState(message + ' after sync refresh');
      }}
    }}

    function parseCsv(text) {{
      const rows = [];
      let row = [];
      let value = '';
      let quoted = false;
      for (let index = 0; index < text.length; index += 1) {{
        const char = text[index];
        if (quoted) {{
          if (char === '"' && text[index + 1] === '"') {{
            value += '"';
            index += 1;
          }} else if (char === '"') {{
            quoted = false;
          }} else {{
            value += char;
          }}
        }} else if (char === '"') {{
          quoted = true;
        }} else if (char === ',') {{
          row.push(value);
          value = '';
        }} else if (char === '\\n') {{
          row.push(value);
          rows.push(row);
          row = [];
          value = '';
        }} else if (char !== '\\r') {{
          value += char;
        }}
      }}
      if (value || row.length) {{
        row.push(value);
        rows.push(row);
      }}
      return rows;
    }}

    function csvValue(value) {{
      const text = String(value || '');
      return /[",\\n\\r]/.test(text) ? `"${{text.replace(/"/g, '""')}}"` : text;
    }}

    function csvText(rows) {{
      return rows.map((row) => row.map(csvValue).join(',')).join('\\n') + '\\n';
    }}

    async function savePublicReleaseApproval(item, approvedAt) {{
      const data = await githubRequest(`/repos/${{stateRepo}}/contents/${{releasePublicationsPath}}?ref=${{stateBranch}}`);
      const rows = parseCsv(decodeBase64Unicode(data.content));
      const header = rows[0] && rows[0].length ? rows[0] : ['release_id', 'public_release', 'approved_at', 'notes'];
      const releaseIdIndex = header.indexOf('release_id');
      const publicIndex = header.indexOf('public_release');
      const approvedIndex = header.indexOf('approved_at');
      const notesIndex = header.indexOf('notes');
      let found = false;
      const nextRows = [header, ...rows.slice(1).filter((row) => row.some(Boolean)).map((row) => {{
        const next = [...row];
        while (next.length < header.length) next.push('');
        if (next[releaseIdIndex] === item.release_id) {{
          next[publicIndex] = 'true';
          next[approvedIndex] = next[approvedIndex] || approvedAt;
          next[notesIndex] = next[notesIndex] || t('publicApprovalNote');
          found = true;
        }}
        return next;
      }})];
      if (!found) {{
        const row = Array(header.length).fill('');
        row[releaseIdIndex] = item.release_id;
        row[publicIndex] = 'true';
        row[approvedIndex] = approvedAt;
        row[notesIndex] = t('publicApprovalNote');
        nextRows.push(row);
      }}
      const payload = {{
        message: `Approve public release ${{item.release_id}}`,
        content: encodeBase64Unicode(csvText(nextRows)),
        branch: stateBranch,
        sha: data.sha,
      }};
      await githubRequest(`/repos/${{stateRepo}}/contents/${{releasePublicationsPath}}`, {{
        method: 'PUT',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload),
      }});
    }}

    async function approvePublicRelease(item, button) {{
      if (!githubToken()) {{
        setSync('viewOnly');
        revealTokenInput();
        return;
      }}
      const approvedAt = new Date().toISOString();
      const previous = {{ public_release: item.public_release, approved_at: item.approved_at }};
      item.public_release = 'true';
      item.approved_at = approvedAt;
      render();
      try {{
        flash(button, t('saving'));
        await savePublicReleaseApproval(item, approvedAt);
        setSync('synced');
      }} catch (error) {{
        item.public_release = previous.public_release;
        item.approved_at = previous.approved_at;
        flash(button, t('saveFailed'));
        setSync('saveError');
        console.error(error);
        render();
      }}
    }}

    async function copyText(text, button) {{
      await navigator.clipboard.writeText(text);
      flash(button, t('copied'));
    }}

    async function copyHtml(htmlText, plainText, button) {{
      if (window.ClipboardItem && navigator.clipboard.write) {{
        await navigator.clipboard.write([
          new ClipboardItem({{
            'text/html': new Blob([htmlText], {{ type: 'text/html' }}),
            'text/plain': new Blob([plainText], {{ type: 'text/plain' }}),
          }})
        ]);
      }} else {{
        await navigator.clipboard.writeText(plainText);
      }}
      flash(button, t('copied'));
    }}

    async function copyImage(src, button) {{
      if (!src || !window.ClipboardItem) {{
        flash(button, t('openImageFallback'));
        return;
      }}
      const response = await fetch(src);
      const blob = await response.blob();
      await navigator.clipboard.write([new ClipboardItem({{ [blob.type]: blob }})]);
      flash(button, t('imageCopied'));
    }}

    async function copyThenOpen(item, button) {{
      await navigator.clipboard.writeText(item.text);
      window.open(item.open_url, '_blank', 'noopener,noreferrer');
      flash(button, t('opened'));
    }}

    async function copyMediumThenOpen(item, textarea, button) {{
      const plainText = mediumBodyText(item, textarea.value);
      await copyHtml(mediumHtmlText(item, plainText), plainText, button);
      window.open(item.open_url, '_blank', 'noopener,noreferrer');
      flash(button, t('opened'));
    }}

    function flash(button, label) {{
      const original = button.textContent;
      button.textContent = label;
      setTimeout(() => {{ button.textContent = original; }}, 1200);
    }}

    function keepButtonLabel(button, label) {{
      button.textContent = label;
      button.dataset.stateLabel = label;
    }}

    function isDone(item) {{
      return item.status === 'posted' || Boolean(remoteState.done?.[item.manual_key]) || Boolean(doneReportRecord(item));
    }}

    function doneRecord(item) {{
      return remoteState.done?.[item.manual_key] || doneReportRecord(item) || null;
    }}

    function verificationReportRecord(item) {{
      const rows = Array.isArray(verificationReport?.items) ? verificationReport.items : [];
      return rows.find((row) => row.manual_key === item.manual_key) || null;
    }}

    function doneReportRecord(item) {{
      const row = verificationReportRecord(item);
      if (!row || !['verified', 'already_done'].includes(row.status)) return null;
      return {{
        verified_at: verificationReport?.checked_at || '',
        marked_at: verificationReport?.checked_at || '',
        posted_url: row.posted_url || '',
        verification_method: row.verification_method || 'publication_report',
        verification_confidence: row.verification_confidence || '',
      }};
    }}

    function pendingReportReason(item) {{
      if (isDone(item)) return '';
      const row = verificationReportRecord(item);
      return row?.status === 'pending' ? row.reason || '' : '';
    }}

    function postedOrVerifiedAt(item) {{
      const record = doneRecord(item);
      return item.posted_at || record?.verified_at || record?.marked_at || '';
    }}

    function verificationLabel(item) {{
      if (item.status === 'posted') return [t('automaticVerified'), 'verification-automatic'];
      const record = doneRecord(item);
      const method = String(record?.verification_method || '');
      if (method.includes('public_page_visual')) return [t('publicVerified'), 'verification-public'];
      if (method) return [t('automaticVerified'), 'verification-automatic'];
      if (record) return [t('manualVerified'), 'verification-manual'];
      return ['', ''];
    }}

    async function markDone(item, button) {{
      remoteState.done ||= {{}};
      const previousDone = remoteState.done[item.manual_key];
      const markedAt = new Date().toISOString();
      const localDone = {{
        [item.manual_key]: {{
        topic_id: item.topic_id,
        platform: item.platform,
        language: item.language,
        template_id: item.template_id,
        marked_at: markedAt,
        marked_by: 'manual_user_confirmation',
        posted_url: item.posted_url || platformProfileUrl(item.platform),
        verified_at: markedAt,
        verification_method: 'user_confirmed_manual_publish',
        verification_confidence: 'manual',
        }}
      }};
      Object.assign(remoteState.done, localDone);
      render();
      try {{
        flash(button, t('saving'));
        await saveWithMerge('Mark manual publish item done', localDone);
      }} catch (error) {{
        if (previousDone) remoteState.done[item.manual_key] = previousDone;
        else delete remoteState.done[item.manual_key];
        flash(button, t('saveFailed'));
        setSync('saveError');
        console.error(error);
      }}
      render();
    }}

    async function undoDone(item, button) {{
      if (remoteState.done) delete remoteState.done[item.manual_key];
      try {{
        flash(button, t('saving'));
        await saveRemoteState('Undo manual publish item done');
      }} catch (error) {{
        flash(button, t('saveFailed'));
        setSync('saveError');
        console.error(error);
      }}
      render();
    }}

    function dueDate(item) {{
      if (!item.due_at) return null;
      const date = new Date(item.due_at);
      return Number.isNaN(date.getTime()) ? null : date;
    }}

    function isDue(item) {{
      if (isDone(item) || item.is_variant) return false;
      if (item.publishing_mode !== 'manual') return false;
      if (!['draft', 'failed', 'approved'].includes(item.status)) return false;
      const date = dueDate(item);
      return date ? kstDayNumber(date) <= kstDayNumber(new Date()) : false;
    }}

    function formatDue(item) {{
      const date = dueDate(item);
      if (!date) return '';
      return new Intl.DateTimeFormat(t('dateLocale'), {{ dateStyle: 'medium', timeStyle: 'short' }}).format(date);
    }}

    function parseDate(value) {{
      if (!value) return null;
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? null : date;
    }}

    function kstDateParts(date) {{
      const parts = new Intl.DateTimeFormat('en-CA', {{
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }}).formatToParts(date);
      return Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, Number(part.value)]));
    }}

    function kstDayNumber(date) {{
      const parts = kstDateParts(date);
      return Math.floor(Date.UTC(parts.year, parts.month - 1, parts.day) / 86400000);
    }}

    function atKstTime(date, hour, minute) {{
      const parts = kstDateParts(date);
      return new Date(Date.UTC(parts.year, parts.month - 1, parts.day, hour - 9, minute, 0, 0));
    }}

    function formatDate(value) {{
      const date = parseDate(value);
      if (!date) return t('none');
      return new Intl.DateTimeFormat(t('dateLocale'), {{ dateStyle: 'medium', timeStyle: 'short' }}).format(date);
    }}

    function formatPublishedDate(value) {{
      if (!value) return t('none');
      if (/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(value)) return value;
      const date = parseDate(value);
      if (!date) return String(value);
      return new Intl.DateTimeFormat(t('dateLocale'), {{ dateStyle: 'medium', timeStyle: 'short' }}).format(date);
    }}

    function daysAgo(value) {{
      const date = parseDate(value);
      if (!date) return t('noRecord');
      const days = Math.max(0, kstDayNumber(new Date()) - kstDayNumber(date));
      if (days === 0) return t('today');
      if (currentLang === 'ko') return `${{days}}${{t('dayAgo')}}`;
      return `${{days}} ${{days === 1 ? t('dayAgo') : t('daysAgo')}}`;
    }}

    function latestDate(values) {{
      return values.map(parseDate).filter(Boolean).sort((a, b) => b - a)[0] || null;
    }}

    function futureDates(values) {{
      const now = Date.now();
      return values.map(parseDate).filter((date) => date && date.getTime() > now);
    }}

    function verificationCheckedAtForPlatform(platform) {{
      const rows = Array.isArray(verificationReport?.items) ? verificationReport.items : [];
      return rows.some((row) => row.platform === platform) ? verificationReport?.checked_at || '' : '';
    }}

    function nextAutomatedBlogSlot() {{
      const anchor = latestDate(blogItems.map((item) => item.published_at || item.scheduled_at));
      if (!anchor) return null;
      let next = atKstTime(new Date(anchor.getTime() + (86400000 * 3)), 9, 0);
      while (next.getTime() <= Date.now()) next = new Date(next.getTime() + (86400000 * 3));
      return next;
    }}

    function hasBilingualBlogQueue() {{
      const groups = new Map();
      blogItems.forEach((item) => {{
        if (!['approved', 'research', 'outline', 'draft', 'image_planning', 'review'].includes(item.status)) return;
        const key = `${{item.category || ''}}::${{item.slug || ''}}`;
        if (!groups.has(key)) groups.set(key, new Set());
        groups.get(key).add(item.language);
      }});
      return [...groups.values()].some((languages) => languages.has('en') && languages.has('ko'));
    }}

    function nextBlogScheduledDate() {{
      return futureDates(blogItems
        .filter((item) => item.status === 'scheduled' && item.scheduled_at)
        .map((item) => item.scheduled_at))
        .sort((a, b) => a - b)[0] || (hasBilingualBlogQueue() ? nextAutomatedBlogSlot() : null);
    }}

    function nextManualDueDate() {{
      return futureDates(items
        .filter((item) => item.publishing_mode === 'manual' && !isDone(item) && !item.is_variant && item.due_at)
        .map((item) => item.due_at))
        .sort((a, b) => a - b)[0] || null;
    }}

    function latestPostedDate() {{
      return latestDate(items.filter((item) => isDone(item)).map(postedOrVerifiedAt));
    }}

    function usesLinkPreviewCard(item) {{
      return ['x', 'linkedin'].includes(item.platform);
    }}

    function previewImageSrc(item) {{
      return item.card_asset_href || (item.platform === 'medium' ? item.publish_cover_image || '' : '');
    }}

    function copyField(labelText, value) {{
      const row = document.createElement('div');
      row.className = 'copy-field';
      const label = document.createElement('label');
      label.textContent = labelText;
      const field = document.createElement('textarea');
      field.value = value || '';
      field.spellcheck = false;
      label.appendChild(field);
      const button = document.createElement('button');
      button.className = 'secondary';
      button.textContent = t('copy');
      button.onclick = () => copyText(field.value, button);
      row.append(label, button);
      return row;
    }}

    function appendSyndicationPublishFields(detail, item) {{
      if (item.kind !== 'syndication') return;
      syndicationCopyRows(item).forEach(([labelText, value]) => detail.appendChild(copyField(labelText, value)));
    }}

    function syndicationCopyRows(item) {{
      if (item.platform === 'medium') {{
        const topics = mediumTopicRows(item);
        return [
          [t('publishTitle'), item.publish_title || displayTitle(item)],
          [t('storyPreviewSubtitle'), item.seo_description || ''],
          ...topics,
          [t('canonicalUrl'), item.publish_canonical_url || item.canonical_url || ''],
        ].filter(([, value]) => value);
      }}
      const tagRows = item.platform === 'hashnode' ? hashnodeTagRows(item) : [];
      return [
        [t('publishTitle'), item.publish_title || displayTitle(item)],
        [t('seoTitle'), item.seo_title || item.publish_title || displayTitle(item)],
        [t('seoDescription'), item.seo_description || ''],
        [t('publishTags'), item.publish_tags || ''],
        ...tagRows,
        [t('canonicalUrl'), item.publish_canonical_url || item.canonical_url || ''],
        [t('coverImage'), item.publish_cover_image || ''],
      ].filter(([, value]) => value);
    }}

    function mediumTopicRows(item) {{
      return String(item.publish_tags || '')
        .split(',')
        .map((topic) => topic.trim())
        .filter(Boolean)
        .slice(0, 5)
        .map((topic, index) => [`${{t('topic')}} ${{index + 1}}`, topic]);
    }}

    function hashnodeTagRows(item) {{
      return String(item.publish_tags || '')
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
        .slice(0, 10)
        .map((tag, index) => [`${{t('tagItem')}} ${{index + 1}}`, tag]);
    }}

    function syndicationQuickCopyRows(item) {{
      if (item.platform === 'medium') {{
        return syndicationCopyRows(item);
      }}
      return syndicationCopyRows(item).filter(([labelText]) => labelText !== t('coverImage'));
    }}

    function copyValueButton(labelText, value) {{
      const button = document.createElement('button');
      button.className = 'secondary';
      button.textContent = `${{labelText}} ${{t('copy')}}`;
      button.onclick = () => copyText(value, button);
      return button;
    }}

    function publishBodyText(item) {{
      if (item.platform === 'hashnode' && item.publish_body) return item.publish_body;
      return titlePrefixedMarkdown(item, item.text);
    }}

    function removeLeadingMarkdownTitle(item, text) {{
      const title = displayTitle(item);
      if (!title) return text;
      const titleHeading = new RegExp('^\\\\s*#\\\\s+' + escapeRegExp(title) + '\\\\s*(?:\\\\n{{1,2}}|$)', 'i');
      return String(text || '').replace(titleHeading, '').replace(/^\\n+/, '');
    }}

    function mediumBodyText(item, text) {{
      return removeLeadingMarkdownTitle(item, text);
    }}

    function titlePrefixedMarkdown(item, text) {{
      if (item.kind !== 'syndication' || item.platform === 'hashnode') return text;
      const title = displayTitle(item);
      if (!title) return text;
      const trimmed = String(text || '').trimStart();
      const titleHeading = new RegExp('^#\\\\s+' + escapeRegExp(title) + '\\\\s*(?:\\\\n{{1,2}}|$)', 'im');
      const leadingTitleHeading = new RegExp('^#\\\\s+' + escapeRegExp(title) + '\\\\s*(?:\\\\n{{1,2}}|$)', 'i');
      if (trimmed.startsWith('---') || trimmed.match(leadingTitleHeading)) return text;
      const body = String(text || '').replace(titleHeading, '').replace(/^\\n+/, '');
      return `# ${{title}}\\n\\n${{body}}`;
    }}

    function copyAndOpenText(item, textarea) {{
      if (item.platform === 'hashnode') return publishBodyText({{ ...item, publish_body: textarea.value }});
      if (item.platform === 'medium') return mediumBodyText(item, textarea.value);
      return titlePrefixedMarkdown(item, textarea.value);
    }}

    function escapeHtml(value) {{
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }}

    function inlineMarkdownToHtml(value) {{
      return escapeHtml(value)
        .replace(/!\\[([^\\]]*)\\]\\((https?:\\/\\/[^\\s)]+)(?:\\s+&quot;[^&]*&quot;)?\\)/g, '<img src="$2" alt="$1">')
        .replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^\\s)]+)\\)/g, '<a href="$2">$1</a>')
        .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*([^*]+)\\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
    }}

    function markdownToMediumHtml(markdown) {{
      const lines = String(markdown || '').replace(/\\r\\n/g, '\\n').split('\\n');
      const blocks = [];
      let paragraph = [];
      let listItems = [];
      let listType = '';

      function flushParagraph() {{
        if (!paragraph.length) return;
        blocks.push(`<p>${{inlineMarkdownToHtml(paragraph.join(' '))}}</p>`);
        paragraph = [];
      }}

      function flushList() {{
        if (!listItems.length) return;
        const tag = listType === 'ol' ? 'ol' : 'ul';
        blocks.push(`<${{tag}}>${{listItems.map((item) => `<li>${{inlineMarkdownToHtml(item)}}</li>`).join('')}}</${{tag}}>`);
        listItems = [];
        listType = '';
      }}

      function flushOpenBlocks() {{
        flushParagraph();
        flushList();
      }}

      lines.forEach((line) => {{
        const trimmed = line.trim();
        if (!trimmed) {{
          flushOpenBlocks();
          return;
        }}
        const heading = trimmed.match(/^(#{{1,6}})\\s+(.+)$/);
        if (heading) {{
          flushOpenBlocks();
          const level = Math.min(heading[1].length, 3);
          blocks.push(`<h${{level}}>${{inlineMarkdownToHtml(heading[2])}}</h${{level}}>`);
          return;
        }}
        const quote = trimmed.match(/^>\\s*(.+)$/);
        if (quote) {{
          flushOpenBlocks();
          blocks.push(`<blockquote>${{inlineMarkdownToHtml(quote[1])}}</blockquote>`);
          return;
        }}
        const unordered = trimmed.match(/^[-*]\\s+(.+)$/);
        const ordered = trimmed.match(/^\\d+\\.\\s+(.+)$/);
        if (unordered || ordered) {{
          flushParagraph();
          const nextType = ordered ? 'ol' : 'ul';
          if (listType && listType !== nextType) flushList();
          listType = nextType;
          listItems.push((unordered || ordered)[1]);
          return;
        }}
        flushList();
        paragraph.push(trimmed);
      }});
      flushOpenBlocks();
      return blocks.join('\\n');
    }}

    function mediumHtmlText(item, markdown) {{
      const bodyHtml = markdownToMediumHtml(markdown);
      const imageUrl = String(item.publish_cover_image || '').trim();
      if (!imageUrl || bodyHtml.includes(imageUrl)) return bodyHtml;
      const imageHtml = `<figure><img src="${{escapeHtml(imageUrl)}}" alt="${{escapeHtml(displayTitle(item))}}"></figure>`;
      return `${{imageHtml}}\\n${{bodyHtml}}`;
    }}

    function renderEmptyState() {{
      empty.textContent = '';
      const title = document.createElement('strong');
      title.textContent = currentView === 'due' ? t('emptyTitle') : t('empty');
      const next = document.createElement('span');
      const nextDue = nextManualDueDate();
      next.textContent = t('emptyNext') + ': ' + (nextDue ? formatDate(nextDue.toISOString()) : t('none'));
      const latest = document.createElement('span');
      const latestPosted = latestPostedDate();
      latest.textContent = t('emptyLatest') + ': ' + (latestPosted ? `${{formatDate(latestPosted.toISOString())}} (${{daysAgo(latestPosted.toISOString())}})` : t('none'));
      empty.append(title, next, latest);
    }}

    function updateVariantToggle() {{
      const count = items.filter((item) => item.is_variant).length;
      if (currentLang === 'ko') {{
        variantToggle.textContent = showVariants ? `대안 숨김 ${{count}}` : `대안 ${{count}}`;
      }} else {{
        variantToggle.textContent = showVariants ? `Hide ${{count}}` : `Alt ${{count}}`;
      }}
    }}

    function platformProfileUrl(platformOrLabel) {{
      const key = String(platformOrLabel || '').toLowerCase();
      const urls = {{
        blog: '/blog/',
        x: 'https://x.com/onnellab',
        twitter: 'https://x.com/onnellab',
        linkedin: 'https://www.linkedin.com/in/onnel-lab-b5b9b0421/',
        bluesky: 'https://bsky.app/profile/onnellab.bsky.social',
        'dev.to': 'https://dev.to/onnellab',
        devto: 'https://dev.to/onnellab',
        hashnode: 'https://hashnode.com/@onnellab',
        medium: 'https://medium.com/@onnellab.app',
      }};
      return urls[key] || '';
    }}

    function profileLink(label, url, className = '') {{
      const link = document.createElement('a');
      link.href = url || '#';
      link.textContent = label;
      if (className) link.className = className;
      if (url && !url.startsWith('/')) {{
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      }}
      return link;
    }}

    function siteItemUrl(item) {{
      if (item.kind === 'home') return '/';
      return item.slug ? `/apps/${{item.slug}}/` : '/apps/';
    }}

    function renderPlatformSummary() {{
      platformSummary.textContent = '';
      const blogCounts = blogItems.reduce((acc, item) => {{
        acc[item.status] = (acc[item.status] || 0) + 1;
        return acc;
      }}, {{}});
      const platformSummaryBadges = [[t('blogPlatformName'), blogItems.length, platformProfileUrl('blog')]];
      const latestPublished = latestDate(blogItems.map((item) => item.published_at));
      const nextScheduled = nextBlogScheduledDate();
      const blogCard = document.createElement('div');
      blogCard.className = 'platform-card';
      const blogTitle = document.createElement('strong');
      const blogTitleText = profileLink(t('blogPlatformName'), platformProfileUrl('blog'));
      const blogTag = document.createElement('span');
      blogTag.className = 'tag mode-automatic';
      blogTag.textContent = t('blogMode');
      blogTitle.append(blogTitleText, blogTag);
      const blogStatus = document.createElement('span');
      blogStatus.textContent = Object.entries(blogCounts).map(([status, count]) => `${{status}} ${{count}}`).join(' / ') || t('none');
      const blogLatest = document.createElement('span');
      blogLatest.textContent = t('latestPublished') + ': ' + (latestPublished ? `${{formatDate(latestPublished.toISOString())}} (${{daysAgo(latestPublished.toISOString())}})` : t('none'));
      const blogNext = document.createElement('span');
      blogNext.textContent = t('nextScheduled') + ': ' + (nextScheduled ? formatDate(nextScheduled.toISOString()) : t('none'));
      blogCard.append(blogTitle, blogStatus, blogLatest, blogNext);
      platformSummary.appendChild(blogCard);

      const platforms = [...new Set(items.map((item) => item.platform_label))].sort();
      platforms.forEach((label) => {{
        const rows = items.filter((item) => item.platform_label === label && !item.is_variant);
        platformSummaryBadges.push([label, rows.length, platformProfileUrl(rows[0]?.platform || label)]);
        const posted = rows.filter((item) => isDone(item));
        const failed = rows.filter((item) => !isDone(item) && item.status === 'failed');
        const drafts = rows.filter((item) => !isDone(item) && ['draft', 'approved'].includes(item.status));
        const latestPosted = latestDate(posted.map(postedOrVerifiedAt));
        const latestAttempt = latestDate([
          verificationCheckedAtForPlatform(rows[0]?.platform || ''),
          ...rows.map((item) => item.last_attempt_at || item.approved_at),
        ]);
        const nextDue = futureDates(rows
          .filter((item) => !isDone(item) && !item.is_variant && item.due_at)
          .map((item) => item.due_at))
          .sort((a, b) => a - b)[0] || nextScheduled;
        const card = document.createElement('div');
        card.className = 'platform-card';
        const title = document.createElement('strong');
        const titleText = profileLink(label, platformProfileUrl(rows[0]?.platform || label));
        const modeTag = document.createElement('span');
        modeTag.className = 'tag ' + (rows[0]?.publishing_mode === 'automatic' ? 'mode-automatic' : 'mode-manual');
        modeTag.textContent = rows[0]?.publishing_mode === 'automatic' ? t('automaticMode') : t('manualMode');
        title.append(titleText, modeTag);
        const status = document.createElement('span');
        status.textContent = `${{posted.length}} ${{t('postedWord')}} / ${{drafts.length}} ${{t('waitingWord')}} / ${{failed.length}} ${{t('failedWord')}}`;
        const postedLine = document.createElement('span');
        postedLine.textContent = t('lastPosted') + ': ' + (latestPosted ? `${{formatDate(latestPosted.toISOString())}} (${{daysAgo(latestPosted.toISOString())}})` : t('none'));
        const nextLine = document.createElement('span');
        nextLine.textContent = t('nextScheduled') + ': ' + (nextDue ? formatDate(nextDue.toISOString()) : t('none'));
        const attemptLine = document.createElement('span');
        attemptLine.textContent = t('lastUpdate') + ': ' + (latestAttempt ? `${{formatDate(latestAttempt.toISOString())}} (${{daysAgo(latestAttempt.toISOString())}})` : t('none'));
        card.append(title, status, postedLine, nextLine, attemptLine);
        platformSummary.appendChild(card);
      }});
      platformStatusSummary.textContent = '';
      platformSummaryBadges.forEach(([label, count, url]) => {{
        const badge = document.createElement('span');
        badge.className = 'platform-count-badge';
        const name = document.createElement('span');
        name.textContent = label;
        const value = document.createElement('b');
        value.textContent = String(count);
        badge.append(name, value);
        platformStatusSummary.appendChild(badge);
      }});
    }}

    function renderSiteStatusSummary() {{
      siteStatusGrid.textContent = '';
      const appCount = siteItems.filter((item) => item.kind === 'app').length;
      siteStatusSummary.textContent = `${{siteItems.length}} ${{t('siteStatusSummary')}} / ${{appCount}} apps`;
      siteItems.forEach((item) => {{
        const card = document.createElement('div');
        card.className = 'app-status-card';
        const title = document.createElement('strong');
        title.appendChild(profileLink(item.kind === 'home' ? t('mainHome') : item.name, siteItemUrl(item)));
        const landing = document.createElement('div');
        landing.className = 'app-status-row is-store';
        landing.innerHTML = `<b>${{siteLandingLabel(item)}}</b><span>${{formatDate(item.landing_updated_at)}}</span>`;
        const assets = document.createElement('div');
        assets.className = 'app-status-row is-release';
        assets.innerHTML = `<b>${{t('assetsUpdated')}}</b><span>${{formatDate(item.assets_updated_at)}}</span>`;
        card.append(title, landing, assets);
        if (item.kind === 'app') {{
          const screenshots = document.createElement('div');
          screenshots.className = 'app-status-row is-store';
          screenshots.innerHTML = `<b>${{t('screenshotsUpdated')}}</b><span>${{formatDate(item.screenshots_updated_at)}} / ${{item.screenshot_count}} ${{t('screenshotCount')}}</span>`;
          card.appendChild(screenshots);
        }}
        siteStatusGrid.appendChild(card);
      }});
    }}

    function renderPricingStatusSummary() {{
      pricingStatusGrid.textContent = '';
      const appCount = new Set(pricingItems.map((item) => item.app_slug || item.app_name)).size;
      const explicitPrices = pricingItems.filter((item) => item.price).length;
      const needsStoreCheck = pricingItems.length - explicitPrices;
      const aiPricingNote = aiProviderPricingSummaryText();
      pricingStatusSummary.textContent = `${{pricingItems.length}} ${{t('paidProduct')}} / ${{appCount}} ${{t('appsWord')}} / ${{needsStoreCheck}} ${{t('priceCheckNeeded')}}${{aiPricingNote ? ' / ' + aiPricingNote : ''}}`;
      const groups = new Map();
      pricingItems.forEach((item) => {{
        const key = item.app_slug || item.app_name;
        if (!groups.has(key)) groups.set(key, {{ app_name: item.app_name, app_slug: item.app_slug, items: [] }});
        groups.get(key).items.push(item);
      }});
      [...groups.values()].sort((a, b) => a.app_name.localeCompare(b.app_name)).forEach((group) => {{
        const card = document.createElement('div');
        card.className = 'app-status-card';
        const title = document.createElement('strong');
        title.appendChild(profileLink(group.app_name || t('none'), group.app_slug ? `/apps/${{group.app_slug}}/` : '/apps/'));
        card.appendChild(title);
        group.items.forEach((item) => {{
          const row = document.createElement('div');
          row.className = pricingRowClass(item);
          const label = document.createElement('b');
          label.textContent = pricingProductLabel(item);
          if (item.ai_margin_status) {{
            const margin = document.createElement('span');
            margin.className = 'ai-margin-badge';
            margin.textContent = aiCreditMarginText(item);
            row.appendChild(margin);
          }}
          const price = document.createElement('span');
          price.textContent = `${{t('priceLabel')}}: ${{item.price || t('priceCheckNeeded')}}`;
          const model = document.createElement('span');
          model.textContent = `${{t('pricingModel')}}: ${{pricingModelLabel(item.pricing || item.pricing_model)}}`;
          const checked = document.createElement('span');
          checked.textContent = `${{t('checkedAt')}}: ${{formatDate(item.checked_at)}}`;
          row.append(label, price, model, checked);
          if (item.price_note) {{
            const note = document.createElement('span');
            note.textContent = pricingNoteLabel(item.price_note);
            row.appendChild(note);
          }}
          if (item.ai_provider_cost_usd) {{
            const economics = document.createElement('span');
            economics.textContent = `${{t('aiCreditEconomics')}}: ${{t('aiNetRevenue')}} $${{item.ai_net_revenue_usd}} / ${{t('aiProviderCost')}} $${{item.ai_provider_cost_usd}}`;
            row.appendChild(economics);
          }}
          if (item.ai_cost_basis) {{
            const basis = document.createElement('span');
            basis.textContent = item.ai_cost_basis;
            row.appendChild(basis);
          }}
          const links = document.createElement('span');
          const linkParts = [];
          if (item.app_store_url) linkParts.push([t('appStore'), item.app_store_url]);
          if (item.play_store_url) linkParts.push([t('playStore'), item.play_store_url]);
          linkParts.forEach(([labelText, href], index) => {{
            if (index > 0) links.append(' / ');
            const link = document.createElement('a');
            link.href = href;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = labelText;
            links.appendChild(link);
          }});
          if (linkParts.length) row.appendChild(links);
          card.appendChild(row);
        }});
        pricingStatusGrid.appendChild(card);
      }});
    }}

    function pricingRowClass(item) {{
      if (item.ai_margin_status === 'loss') return 'app-status-row is-ai-loss';
      if (item.ai_margin_status === 'profit') return 'app-status-row is-ai-profit';
      return item.product_type === 'paid_download' ? 'app-status-row is-store' : 'app-status-row is-release';
    }}

    function aiCreditMarginText(item) {{
      const label = item.ai_margin_status === 'loss' ? t('aiCreditMarginLoss') : t('aiCreditMarginProfit');
      return `${{label}}: $${{item.ai_profit_usd}} (${{item.ai_margin_percent}}%)`;
    }}

    function aiProviderPricingSummaryText() {{
      const outcome = aiProviderPricingStatus && aiProviderPricingStatus.outcome;
      const providers = Array.isArray(aiProviderPricingStatus && aiProviderPricingStatus.providers) ? aiProviderPricingStatus.providers : [];
      if (providers.some((provider) => provider.status === 'manual_ok')) return t('aiPricingManualOk');
      if (outcome === 'changed') return t('aiPricingCheckChanged');
      if (outcome === 'warning') return t('aiPricingCheckWarning');
      if (aiProviderPricingStatus && aiProviderPricingStatus.checked_at) {{
        return `${{t('aiPricingCheckedAt')}}: ${{formatDate(aiProviderPricingStatus.checked_at)}}`;
      }}
      return '';
    }}

    function pricingProductLabel(item) {{
      if (item.product_type === 'paid_download') return t('paidDownload');
      if (item.product_type === 'ai_credit') return item.product_name || t('aiCredit');
      return item.product_name || t('paidProduct');
    }}

    function pricingNoteLabel(note) {{
      if (note === 'Public landing page metadata') return t('localPriceMetadata');
      if (note === 'Store in-app purchase price not recorded locally') return t('iapPriceNotRecorded');
      if (note === 'AI credit price not recorded locally') return t('aiCreditPriceNotRecorded');
      return note;
    }}

    function pricingModelLabel(model) {{
      if (!model) return t('none');
      const normalized = String(model).toLowerCase();
      if (currentLang === 'ko') {{
        if (normalized === 'free download with optional pro purchase') return '무료 다운로드 + 선택 Pro 구매';
        if (normalized === 'paid download') return '유료 다운로드';
        if (normalized === 'freemium') return '프리미엄';
        if (normalized === 'one_time_purchase') return '일회성 구매';
      }}
      if (normalized === 'one_time_purchase') return 'one-time purchase';
      return model;
    }}

    function renderQualityStatusSummary() {{
      qualityStatusGrid.textContent = '';
      const social = qualityReport?.social || {{}};
      const syndication = qualityReport?.syndication || {{}};
      const warnings = Array.isArray(social.repetition_warnings) ? social.repetition_warnings : [];
      qualityStatusSummary.textContent = `${{t('qualityStatusSummary')}} / ${{warnings.length}} ${{t('repetitionWarnings')}}`;
      const rows = [
        [t('socialQuality'), social.average_score, `${{(social.posts || []).length}} items`],
        [t('syndicationQuality'), syndication.average_score, `${{(syndication.drafts || []).length}} items`],
        [t('repetitionWarnings'), warnings.length, warnings.length ? warnings.map((warning) => `${{warning.phrase}} (${{warning.count}})`).join(' / ') : t('noWarnings')],
      ];
      if (qualityReport?.error) rows.push([t('qualityError'), '!', qualityReport.error]);
      rows.forEach(([labelText, score, detail]) => {{
        const card = document.createElement('div');
        card.className = 'app-status-card';
        const title = document.createElement('strong');
        title.textContent = labelText;
        const row = document.createElement('div');
        row.className = 'app-status-row is-release';
        const scoreLine = document.createElement('b');
        scoreLine.textContent = score === undefined || score === null ? t('none') : String(score);
        const detailLine = document.createElement('span');
        detailLine.textContent = detail || '';
        row.append(scoreLine, detailLine);
        card.append(title, row);
        if (labelText === t('repetitionWarnings') && warnings.length) {{
          const actions = document.createElement('div');
          actions.className = 'credential-actions';
          const commandButton = document.createElement('button');
          commandButton.type = 'button';
          commandButton.textContent = t('copyRepetitionFixCommand');
          commandButton.onclick = () => copyText(t('repetitionFixCommand'), commandButton);
          const warningsButton = document.createElement('button');
          warningsButton.type = 'button';
          warningsButton.className = 'secondary';
          warningsButton.textContent = t('copyRepetitionWarnings');
          warningsButton.onclick = () => copyText(warnings.map((warning) => `${{warning.phrase}} (${{warning.count}})`).join('\\n'), warningsButton);
          actions.append(commandButton, warningsButton);
          card.appendChild(actions);
        }}
        qualityStatusGrid.appendChild(card);
      }});
    }}

    function appStatusGroups() {{
      const groups = new Map();
      function ensure(item) {{
        const key = item.app_id || item.app_slug || item.app_name;
        if (!groups.has(key)) groups.set(key, {{ app_name: item.app_name, app_slug: item.app_slug || item.app_id || '', stores: [], releases: [], flutterDependencies: [] }});
        return groups.get(key);
      }}
      storeItems.forEach((item) => ensure(item).stores.push(item));
      releases.forEach((item) => ensure(item).releases.push(item));
      flutterDependencyItems.forEach((item) => {{
        ensure(item).flutterDependencies.push(item);
      }});
      return [...groups.values()].sort((a, b) => a.app_name.localeCompare(b.app_name));
    }}

    function storeLabel(platform) {{
      if (platform === 'ios') return 'App Store';
      if (platform === 'android') return 'Play Store';
      return platform || t('noStore');
    }}

    function siteLandingLabel(item) {{
      return item.kind === 'home' ? t('homePageUpdated') : t('appPageUpdated');
    }}

    function displayFlutterDependency(item) {{
      return !(item.package_type === 'dependency' && item.declared_version === 'sdk:flutter');
    }}

    function renderAppStatusSummary() {{
      appStatusGrid.textContent = '';
      const groups = appStatusGroups();
      const storeCount = storeItems.length;
      const releaseCount = releases.length;
      const dependencyCount = flutterDependencyItems.filter(displayFlutterDependency).length;
      const checkedDates = storeItems
        .map((item) => parseDate(item.checked_at))
        .filter((date) => date instanceof Date && !Number.isNaN(date.getTime()));
      const latestCheckedAt = checkedDates.length
        ? new Date(Math.max(...checkedDates.map((value) => value.getTime())))
        : null;
      const latestCheckedAtText = checkedDates.length
        ? `${{t('checkedAt')}}: ${{formatDate(latestCheckedAt)}}`
        : `${{t('checkedAt')}}: ${{t('none')}}`;
      appStatusSummary.textContent = `${{groups.length}} apps / ${{storeCount}} stores / ${{releaseCount}} releases / ${{dependencyCount}} plugin rows / ${{latestCheckedAtText}} / ${{releaseSyncSummaryText()}}`;
      groups.forEach((group) => {{
        const card = document.createElement('div');
        card.className = 'app-status-card';
        const title = document.createElement('strong');
        title.appendChild(profileLink(group.app_name || t('none'), group.app_slug ? `/apps/${{group.app_slug}}/` : '/apps/'));
        card.appendChild(title);
        group.stores
          .sort((a, b) => a.platform.localeCompare(b.platform))
          .forEach((item) => {{
            const row = document.createElement('div');
            row.className = 'app-status-row is-store';
            const label = document.createElement('b');
            label.textContent = storeLabel(item.platform);
            const version = document.createElement('span');
            version.textContent = `${{t('currentVersion')}}: ${{item.version || t('none')}} / ${{item.status || t('none')}}`;
            const published = document.createElement('span');
            published.textContent = `${{t('releasedDate')}}: ${{formatPublishedDate(item.published_at)}}`;
            row.append(label, version, published);
            if (item.release_notes) {{
              const notes = document.createElement('span');
              notes.textContent = `${{t('releaseNotes')}}: ${{item.release_notes}}`;
              row.appendChild(notes);
            }}
            card.appendChild(row);
          }});
        if (!group.stores.length) {{
          const row = document.createElement('div');
          row.className = 'app-status-row is-store';
          row.textContent = t('noStore');
          card.appendChild(row);
        }}
        if (group.releases.length) {{
          group.releases
            .sort((a, b) => a.platform.localeCompare(b.platform))
            .forEach((item) => {{
              const row = document.createElement('div');
              row.className = 'app-status-row is-release';
              const label = document.createElement('b');
              label.textContent = `${{t('githubRelease')}} / ${{item.platform}}`;
              const status = document.createElement('span');
              status.textContent = `${{item.tag}} / ${{item.status}} / ${{item.release_channel || 'public'}} / ${{item.public_release === 'true' ? t('publicApproved') : t('publicPending')}}`;
              const planned = document.createElement('span');
              const releaseDateLabel = item.released_at ? t('githubReleasedAt') : t('plannedDate');
              planned.textContent = `${{releaseDateLabel}}: ${{item.released_at ? formatDate(item.released_at) : item.release_date || t('none')}}`;
              const repo = document.createElement('span');
              repo.textContent = item.repository;
              row.append(label, status, planned, repo);
              if (item.release_channel === 'public' && item.public_release !== 'true') {{
                const approve = document.createElement('button');
                approve.className = 'secondary';
                approve.textContent = t('approvePublicRelease');
                approve.onclick = () => approvePublicRelease(item, approve);
                row.appendChild(approve);
              }}
              if (item.release_url) {{
                const link = document.createElement('a');
                link.href = item.release_url;
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = 'Release Notes';
                row.appendChild(link);
              }}
              card.appendChild(row);
            }});
        }} else {{
          const row = document.createElement('div');
          row.className = 'app-status-row is-release';
          row.textContent = t('noRelease');
          card.appendChild(row);
        }}
        const visibleFlutterDependencies = group.flutterDependencies.filter(displayFlutterDependency);
        if (visibleFlutterDependencies.length) {{
          const dependencyHeader = document.createElement('div');
          dependencyHeader.className = 'app-status-row is-store';
          const dependencyTitle = document.createElement('b');
          dependencyTitle.textContent = t('flutterDependencyVersions');
          const dependencySummary = document.createElement('span');
          dependencySummary.textContent = `${{visibleFlutterDependencies.length}} / ${{t('dependencyStatusLabel')}}`;
          dependencyHeader.appendChild(dependencyTitle);
          dependencyHeader.appendChild(dependencySummary);
          card.appendChild(dependencyHeader);
          visibleFlutterDependencies
            .sort((a, b) => `${{a.package_type}}:${{a.package_name}}`.localeCompare(`${{b.package_type}}:${{b.package_name}}`))
            .forEach((item) => {{
              const row = document.createElement('div');
              row.className = 'app-status-row is-store';
              const packageName = document.createElement('b');
              const packageTitle = item.package_name || t('none');
              const packageKind = item.package_type === 'flutter_sdk' ? t('flutterSdk') : t('flutterPlugin');
              packageName.textContent = `${{packageKind}}: ${{packageTitle}}`;
              const status = document.createElement('span');
              status.textContent = `${{t('dependencyStatusLabel')}}: ${{item.status || t('none')}}`;
              const declared = document.createElement('span');
              declared.textContent = `${{t('dependencyDeclared')}}: ${{item.declared_version || item.flutter_constraint || t('none')}}`;
              const resolved = document.createElement('span');
              resolved.textContent = `${{t('dependencyResolved')}}: ${{item.resolved_version || t('none')}}`;
              const source = document.createElement('span');
              source.textContent = `${{t('dependencySource')}}: ${{item.source || t('none')}}`;
              row.append(packageName, status, declared, resolved, source);
              card.appendChild(row);
            }});
        }} else {{
          const row = document.createElement('div');
          row.className = 'app-status-row is-store';
          row.textContent = `${{t('flutterDependencyVersions')}}: ${{t('none')}}`;
          card.appendChild(row);
        }}
        appStatusGrid.appendChild(card);
      }});
    }}

    function releaseSyncSummaryText() {{
      if (!releaseSyncStatus || !releaseSyncStatus.outcome) return `${{t('releaseSyncStatus')}}: ${{t('releaseSyncUnknown')}}`;
      const label = releaseSyncStatus.outcome === 'skipped'
        ? t('releaseSyncSkipped')
        : releaseSyncStatus.outcome === 'not_found'
          ? t('releaseSyncNotFound')
          : t('releaseSyncSynced');
      return `${{t('releaseSyncStatus')}}: ${{label}} / ${{formatDate(releaseSyncStatus.checked_at)}}`;
    }}

    function statusClass(status) {{
      return 'status-' + String(status || 'draft').replace(/[^a-z0-9]+/g, '-');
    }}

    function platformClass(platform) {{
      return 'platform-' + String(platform || '').replace(/[^a-z0-9]+/g, '-');
    }}

    function displayTitle(item) {{
      if (item.title) return String(item.title).trim();
      const text = String(item.text || '');
      const frontmatterTitle = text.match(/^---[\\s\\S]*?^title:\\s*["']?(.+?)["']?\\s*$[\\s\\S]*?^---/m);
      if (frontmatterTitle) return frontmatterTitle[1].trim();
      const heading = text.match(/^#\\s+(.+)$/m);
      if (heading) return heading[1].trim();
      return text.split('\\n').find((line) => line.trim()) || item.slug;
    }}

    function escapeRegExp(value) {{
      return String(value).replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
    }}

    function publishedItemUrl(item) {{
      if (!isDone(item)) return '';
      const record = doneRecord(item);
      const url = String(item.posted_url || record?.posted_url || platformProfileUrl(item.platform || item.platform_label) || item.canonical_url || '').trim();
      return url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/') ? url : '';
    }}

    function render() {{
      const query = filters.search.value.trim().toLowerCase();
      const platform = filters.platform.value;
      const language = filters.language.value;
      const status = filters.status.value;
      const mode = filters.mode.value;
      const visibility = filters.visibility.value;
      const visible = items.filter((item) => {{
        const haystack = [item.topic_id, item.platform_label, item.language, item.status, item.template_id, item.text].join(' ').toLowerCase();
        const done = isDone(item);
        const due = isDue(item);
        if (item.is_variant && !showVariants) return false;
        if (currentView === 'due' && !due) return false;
        if (currentView === 'manual' && (item.publishing_mode !== 'manual' || done)) return false;
        if (currentView === 'done' && !done) return false;
        return (!query || haystack.includes(query))
          && (!platform || item.platform_label === platform)
          && (!language || item.language === language)
          && (!status || item.status === status)
          && (!mode || item.publishing_mode === mode)
          && (currentView !== 'custom' || visibility === 'all' || (visibility === 'due' ? due : !done));
      }});
      const dueTotal = String(items.filter(isDue).length);
      const manualTotal = String(items.filter((item) =>
        item.publishing_mode === 'manual'
        && !item.is_variant
        && !isDone(item)
        && ['draft', 'failed', 'approved'].includes(item.status)
      ).length);
      const postedTotal = String(items.filter((item) => !item.is_variant && isDone(item)).length);
      dueCountEls.forEach((element) => element.textContent = dueTotal);
      manualCountEl.textContent = manualTotal;
      postedCountEl.textContent = postedTotal;
      grid.textContent = '';
      empty.hidden = visible.length !== 0;
      if (!visible.length) renderEmptyState();
      visible.forEach((item) => grid.appendChild(card(item)));
      renderPlatformSummary();
      renderAppStatusSummary();
      renderSiteStatusSummary();
      renderPricingStatusSummary();
      updateVariantToggle();
      syncViewButtons();
      updateAppBadge();
    }}

    function card(item) {{
      const article = document.createElement('article');
      article.className = [isDue(item) ? 'is-due' : '', isDone(item) ? 'is-done' : ''].filter(Boolean).join(' ');
      const previewSrc = previewImageSrc(item);
      if (previewSrc) {{
        const img = document.createElement('img');
        img.className = 'thumb';
        img.src = previewSrc;
        img.alt = item.platform === 'medium' ? item.topic_id + ' featured image' : item.topic_id + ' social card';
        article.appendChild(img);
      }}
      const body = document.createElement('div');
      body.className = 'body';
      const cardHead = document.createElement('div');
      cardHead.className = 'card-head';
      const platformBadge = document.createElement('div');
      platformBadge.className = 'platform-badge ' + platformClass(item.platform);
      platformBadge.textContent = item.platform_label;
      cardHead.append(platformBadge);
      const meta = document.createElement('div');
      meta.className = 'meta';
      const statusParts = [
        item.publishing_mode === 'manual' ? t('manualMode') : t('automaticMode'),
        item.language,
        isDone(item) ? t('doneTag') : item.status,
      ];
      if (isDue(item)) {{
        statusParts.push(t('dueTag'));
      }}
      if (isDone(item)) {{
        const [label, className] = verificationLabel(item);
        if (label) {{
          statusParts.push(label);
        }}
      }}
      meta.textContent = statusParts.filter(Boolean).join(' / ');
      const title = document.createElement('h2');
      const titleText = displayTitle(item) + (item.is_variant ? ' / ' + t('variantTag') : '');
      const publishedUrl = publishedItemUrl(item);
      if (publishedUrl) {{
        const titleLink = document.createElement('a');
        titleLink.href = publishedUrl;
        titleLink.textContent = titleText;
        if (!publishedUrl.startsWith('/')) {{
          titleLink.target = '_blank';
          titleLink.rel = 'noopener noreferrer';
        }}
        title.appendChild(titleLink);
      }} else {{
        title.textContent = titleText;
      }}
      const summary = document.createElement('div');
      summary.className = 'card-summary';
      const summaryNote = document.createElement('div');
      summaryNote.className = 'note';
      summaryNote.textContent = isDone(item)
        ? t('completedAt') + ' ' + formatDate(postedOrVerifiedAt(item))
        : item.due_at ? t('dueAt') + ' ' + formatDue(item) : t('noRecord');
      const textarea = document.createElement('textarea');
      textarea.value = publishBodyText(item);
      textarea.spellcheck = false;
      const detail = document.createElement('div');
      detail.className = 'card-detail';
      const actions = document.createElement('div');
      actions.className = 'actions';
      const open = document.createElement('button');
      open.className = 'primary';
      open.textContent = item.platform === 'hashnode'
        ? t('copyBodyAndOpen')
        : item.platform === 'medium' ? t('copyFormattedAndOpen') : t('copyAndOpen');
      open.onclick = () => item.platform === 'medium'
        ? copyMediumThenOpen(item, textarea, open)
        : copyThenOpen({{ ...item, text: copyAndOpenText(item, textarea) }}, open);
      const detailToggle = document.createElement('button');
      detailToggle.className = 'secondary';
      detailToggle.textContent = t('showDetails');
      detailToggle.onclick = () => {{
        article.classList.toggle('is-expanded');
        detailToggle.textContent = article.classList.contains('is-expanded') ? t('hideDetails') : t('showDetails');
      }};
      const copy = document.createElement('button');
      copy.className = 'secondary';
      copy.textContent = item.platform === 'hashnode'
        ? t('publishBody') + ' ' + t('copy')
        : item.platform === 'medium' ? t('copyFormatted') : item.kind === 'syndication' ? t('copyMarkdown') : t('copyPost');
      copy.onclick = () => {{
        if (item.platform === 'medium') {{
          const plainText = copyAndOpenText(item, textarea);
          copyHtml(mediumHtmlText(item, plainText), plainText, copy);
          return;
        }}
        copyText(textarea.value, copy);
      }};
      const doneButton = document.createElement('button');
      doneButton.className = 'secondary';
      doneButton.textContent = isDone(item) ? t('undoDone') : t('markDone');
      doneButton.onclick = () => isDone(item) ? undoDone(item, doneButton) : markDone(item, doneButton);
      actions.append(open, doneButton, detailToggle);
      if (item.kind === 'syndication') {{
        syndicationQuickCopyRows(item).forEach(([labelText, value]) => actions.appendChild(copyValueButton(labelText, value)));
      }}
      const imageActionSrc = previewImageSrc(item);
      if (imageActionSrc && !usesLinkPreviewCard(item)) {{
        const copyImg = document.createElement('button');
        copyImg.className = 'secondary';
        copyImg.textContent = t('copyImage');
        copyImg.onclick = () => copyImage(imageActionSrc, copyImg);
        const openImg = document.createElement('a');
        openImg.className = 'button secondary';
        openImg.textContent = t('openImage');
        openImg.href = imageActionSrc;
        openImg.target = '_blank';
        openImg.rel = 'noopener noreferrer';
        detail.append(copyImg, openImg);
      }}
      appendSyndicationPublishFields(detail, item);
      const note = document.createElement('div');
      note.className = 'note';
      note.textContent = item.draft_path + ' / ' + t('length') + ' ' + item.length + (item.due_at ? ' / ' + t('dueAt') + ' ' + formatDue(item) : '') + (usesLinkPreviewCard(item) ? ' / ' + t('noImageAttach') : '');
      const pendingReason = pendingReportReason(item);
      if (pendingReason) {{
        const pending = document.createElement('div');
        pending.className = 'note';
        pending.textContent = `${{t('verificationPendingReason')}}: ${{pendingReason}}`;
        detail.appendChild(pending);
      }}
      detail.append(textarea, copy, note);
      summary.append(summaryNote);
      if (item.error) {{
        const error = document.createElement('div');
        error.className = 'error';
        error.textContent = item.error;
        detail.appendChild(error);
      }}
      body.append(cardHead, meta, title, summary, actions, detail);
      article.appendChild(body);
      return article;
    }}

    document.getElementById('save-token').onclick = async () => {{
      localStorage.setItem(tokenKey, tokenInput.value.trim());
      await loadRemoteState({{ refreshDashboardData: true }});
    }};
    document.getElementById('save-credentials').onclick = (event) => saveCredentials(event.currentTarget);
    document.getElementById('clear-credentials').onclick = (event) => clearCredentials(event.currentTarget);
    document.getElementById('copy-env-block').onclick = (event) => copyCredentialEnv(event.currentTarget);
    document.getElementById('copy-secret-sync-command').onclick = (event) => copySecretSyncCommand(event.currentTarget);
    document.getElementById('copy-post-command').onclick = (event) => copyPostingCommand(event.currentTarget);
    document.getElementById('run-posting-now').onclick = (event) => runPostingNow(event.currentTarget);
    Object.values(credentialInputs).forEach((input) => input.addEventListener('input', updateCredentialOutput));
    refreshButton.onclick = () => {{
      if (!githubToken()) {{
        setSync('viewOnly');
        revealTokenInput();
        return;
      }}
      loadRemoteState({{ refreshDashboardData: true }});
    }};
    verifyButtonLarge.onclick = triggerPublicationVerification;
    verifyButtonPrimary.onclick = triggerPublicationVerification;
    syncButtonLarge.onclick = () => {{
      if (!githubToken()) {{
        setSync('viewOnly');
        revealTokenInput();
        return;
      }}
      loadRemoteState({{ refreshDashboardData: true }});
    }};
    badgeButton.onclick = async () => {{
      if ('Notification' in window && Notification.permission === 'default') {{
        await Notification.requestPermission();
      }}
      await updateAppBadge();
      keepButtonLabel(badgeButton, t('badgeReady'));
    }};
    langToggle.onclick = () => {{
      currentLang = currentLang === 'ko' ? 'en' : 'ko';
      localStorage.setItem(langKey, currentLang);
      applyTranslations();
      render();
    }};
    variantToggle.onclick = () => {{
      showVariants = !showVariants;
      render();
    }};
    viewButtons.forEach((button) => button.onclick = () => applyView(button.dataset.view));
    Object.values(filters).forEach((input) => input.addEventListener('input', () => {{
      currentView = 'custom';
      render();
    }}));
    window.setInterval(render, 60000);
    window.setInterval(() => loadRemoteState({{ refreshDashboardData: true }}), 900000);
    document.addEventListener('visibilitychange', () => {{
      if (document.visibilityState === 'visible') {{
        render();
        loadRemoteState({{ refreshDashboardData: true }});
      }}
    }});
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(console.warn);
    loadCredentials();
    loadRemoteState({{ refreshDashboardData: true }});
  </script>
</body>
</html>
"""


def pwa_manifest_document() -> str:
    return json.dumps(
        {
            "name": "ONNELLAB Publish Status Dashboard",
            "short_name": "ONNEL Dashboard",
            "start_url": "/manual-publish/",
            "scope": "/manual-publish/",
            "display": "standalone",
            "background_color": "#fffaf5",
            "theme_color": "#fffaf5",
            "icons": [
                {
                    "src": "./icon-180.png?v=20260713-dashboard-bg",
                    "sizes": "180x180",
                    "type": "image/png",
                },
                {
                    "src": "./icon-192.png?v=20260713-dashboard-bg",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
                {
                    "src": "./icon-512.png?v=20260713-dashboard-bg",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def service_worker_document() -> str:
    return """const CACHE = 'onnellab-manual-publish-v11';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
"""


def quality_report_item(social_manifest: Path, syndication_manifest: Path) -> dict[str, object]:
    report: dict[str, object] = {}
    errors: list[str] = []
    try:
        report["social"] = evaluate_social_templates(social_manifest)
    except Exception as error:  # Keep dashboard generation available even if quality checks fail.
        errors.append(f"social: {error}")
    try:
        report["syndication"] = evaluate_syndication_drafts(syndication_manifest)
    except Exception as error:  # Keep dashboard generation available even if quality checks fail.
        errors.append(f"syndication: {error}")
    if errors:
        report["error"] = " / ".join(errors)
    return report


def build_manual_publish_site(
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    output: Path = DEFAULT_OUTPUT,
    topics_path: Path = DEFAULT_TOPICS,
    manual_state_path: Path = DEFAULT_MANUAL_STATE,
    app_releases_path: Path = DEFAULT_APP_RELEASES,
    app_release_publications_path: Path = DEFAULT_APP_RELEASE_PUBLICATIONS,
    app_release_sync_status_path: Path = DEFAULT_APP_RELEASE_SYNC_STATUS,
    verification_report_path: Path = DEFAULT_VERIFICATION_REPORT,
    store_versions_path: Path = DEFAULT_STORE_VERSIONS,
    flutter_dependency_versions_path: Path = DEFAULT_FLUTTER_DEPENDENCY_VERSIONS,
    homepage_repo: Path = DEFAULT_HOMEPAGE_REPO,
) -> Path:
    topics = read_topics(topics_path)
    items = social_items(social_manifest, topics) + syndication_items(syndication_manifest, topics)
    manual_state = manual_state_item(manual_state_path)
    releases = app_release_items(app_releases_path, app_release_publications_path)
    blog_items = blog_status_items(topics_path)
    store_items = store_status_items(store_versions_path)
    flutter_dependency_items = flutter_dependency_status_items(flutter_dependency_versions_path)
    site_items = homepage_status_items(homepage_repo)
    pricing_items = product_pricing_items(homepage_repo)
    ai_provider_pricing_status = ai_provider_pricing_status_item()
    release_sync_status = release_sync_status_item(app_release_sync_status_path)
    verification_report = verification_report_item(verification_report_path)
    quality_report = quality_report_item(social_manifest, syndication_manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        html_document(
            items,
            manual_state,
        releases,
        blog_items,
        store_items,
        flutter_dependency_items,
        site_items,
        pricing_items,
            ai_provider_pricing_status,
            release_sync_status,
            verification_report,
            quality_report,
        ),
        encoding="utf-8",
    )
    (output.parent / "manifest.webmanifest").write_text(pwa_manifest_document(), encoding="utf-8")
    (output.parent / "sw.js").write_text(service_worker_document(), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hosted manual publishing dashboard")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS)
    parser.add_argument("--manual-state", type=Path, default=DEFAULT_MANUAL_STATE)
    parser.add_argument("--app-releases", type=Path, default=DEFAULT_APP_RELEASES)
    parser.add_argument("--app-release-publications", type=Path, default=DEFAULT_APP_RELEASE_PUBLICATIONS)
    parser.add_argument("--app-release-sync-status", type=Path, default=DEFAULT_APP_RELEASE_SYNC_STATUS)
    parser.add_argument("--verification-report", type=Path, default=DEFAULT_VERIFICATION_REPORT)
    parser.add_argument("--store-versions", type=Path, default=DEFAULT_STORE_VERSIONS)
    parser.add_argument("--flutter-dependency-versions", type=Path, default=DEFAULT_FLUTTER_DEPENDENCY_VERSIONS)
    parser.add_argument("--homepage-repo", type=Path, default=DEFAULT_HOMEPAGE_REPO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_manual_publish_site(
        args.social_manifest,
        args.syndication_manifest,
        args.output,
        args.topics,
        args.manual_state,
        args.app_releases,
        args.app_release_publications,
        args.app_release_sync_status,
        args.verification_report,
        args.store_versions,
        args.flutter_dependency_versions,
        args.homepage_repo,
    )
    print(f"generated {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
