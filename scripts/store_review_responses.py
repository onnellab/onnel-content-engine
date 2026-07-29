#!/usr/bin/env python3
"""Classify store reviews and create human-reviewed reply drafts."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = ROOT / "templates" / "store_reviews" / "reply_templates.json"

KEYWORDS = {
    "billing": (
        "결제",
        "구매",
        "복원",
        "환불",
        "구독",
        "payment",
        "purchase",
        "restore",
        "refund",
        "subscription",
        "charged",
    ),
    "privacy": (
        "개인정보",
        "프라이버시",
        "데이터 수집",
        "추적",
        "privacy",
        "personal data",
        "tracking",
        "collect data",
    ),
    "bug": (
        "오류",
        "버그",
        "충돌",
        "크래시",
        "멈춤",
        "안 돼",
        "안됨",
        "실패",
        "error",
        "bug",
        "crash",
        "freeze",
        "stuck",
        "doesn't work",
        "does not work",
        "failed",
    ),
    "feature": (
        "기능 추가",
        "지원해",
        "있으면 좋",
        "요청",
        "제안",
        "feature",
        "please add",
        "would like",
        "request",
        "suggestion",
        "support for",
    ),
}
PRICING_CONFUSION_KEYWORDS = ("not free", "actually a paid", "paid app", "free as stated", "무료가 아니", "유료")


def load_templates(path: Path = DEFAULT_TEMPLATES) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_language(value: str) -> str:
    language = value.strip().lower().replace("_", "-")
    return "ko" if language == "ko" or language.startswith("ko-") else "en"


def review_text(review: dict[str, str]) -> str:
    return " ".join(
        part.strip()
        for part in (review.get("title", ""), review.get("body", ""))
        if part and part.strip()
    )


def requires_korean_approval_translation(review: dict[str, str]) -> bool:
    language = review.get("reviewer_language", "").strip().lower().replace("_", "-")
    if language == "ko" or language.startswith("ko-"):
        return False
    text = review_text(review)
    if not language and re.search(r"[가-힣]", text):
        return False
    return bool(language or text)


def classify_review(review: dict[str, str]) -> str:
    text = review_text(review).lower()
    if not text:
        return "no_text"
    if any(keyword in text for keyword in PRICING_CONFUSION_KEYWORDS):
        return "pricing_confusion"
    for category in ("billing", "privacy", "bug", "feature"):
        if any(keyword in text for keyword in KEYWORDS[category]):
            return category
    try:
        rating = int(review.get("rating", "0"))
    except ValueError:
        rating = 0
    return "positive" if rating >= 4 else "negative"


def clean_app_name(value: str) -> str:
    cleaned = re.sub(r"[\r\n\t{}]+", " ", value).strip()
    return cleaned or "the app"


def generate_reply(
    review: dict[str, str],
    templates: dict[str, object] | None = None,
) -> dict[str, str]:
    template_data = templates or load_templates()
    language = normalized_language(review.get("reviewer_language", ""))
    category = classify_review(review)
    language_templates = template_data.get(language)
    if not isinstance(language_templates, dict):
        raise ValueError(f"missing store review templates for {language}")
    app_overrides = template_data.get("app_overrides", {})
    app_templates = app_overrides.get(review.get("app_slug", "").strip().lower(), {}) if isinstance(app_overrides, dict) else {}
    localized_override = app_templates.get(language, {}) if isinstance(app_templates, dict) else {}
    template = localized_override.get(category) if isinstance(localized_override, dict) else None
    template = template or language_templates.get(category)
    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"missing store review template for {language}/{category}")
    reply = template.format(app_name=clean_app_name(review.get("app_name", "")))
    return {
        "reply_language": language,
        "reply_category": category,
        "suggested_reply": reply,
        "human_review_required": "true",
    }
