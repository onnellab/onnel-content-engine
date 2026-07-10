#!/usr/bin/env python3
"""Evaluate article readiness before scheduling or publishing."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, read_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA_ROOT = ROOT / "generated" / "metadata"
DEFAULT_ASSETS_ROOT = ROOT / "generated" / "assets" / "blog"
DEFAULT_REVIEW_ROOT = ROOT / "generated" / "reviews"
DEFAULT_THRESHOLD = 9.0


class ArticleEvaluationError(ValueError):
    """Raised when article evaluation cannot proceed."""


def parse_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith("---\n"):
        return {}, markdown
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return {}, markdown
    metadata: dict[str, str] = {}
    for line in markdown[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, markdown[end + 5 :]


def sections(body: str) -> set[str]:
    return {match.group(1).strip().lower() for match in re.finditer(r"^##\s+(.+)$", body, flags=re.MULTILINE)}


def split_pipe(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def markdown_path_for(topic: dict[str, str], topics_path: Path) -> Path:
    if not topic["canonical_path"]:
        raise ArticleEvaluationError(f"{topic['id']} has no canonical_path")
    path = topics_path.parent.parent / topic["canonical_path"]
    if not path.exists():
        raise ArticleEvaluationError(f"{topic['id']} Markdown file does not exist: {topic['canonical_path']}")
    return path


def find_topic(topic_id: str, topics_path: Path) -> dict[str, str]:
    for row in read_csv(topics_path, TOPIC_HEADER):
        if row["id"] == topic_id:
            return row
    raise ArticleEvaluationError(f"topic not found: {topic_id}")


def metadata_path(topic: dict[str, str], metadata_root: Path) -> Path:
    return metadata_root / topic["primary_language"] / topic["category"] / topic["slug"] / "internal_links.json"


def review_path(topic: dict[str, str], review_root: Path) -> Path:
    return review_root / topic["primary_language"] / topic["category"] / topic["slug"] / "review.json"


def blog_asset_paths(body: str) -> list[str]:
    return re.findall(r"\]\((/blog-assets/[^)\s\"]+)", body)


def related_article_count(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data.get("recommendations", {}).get("related_articles", []))


SECTION_ALIASES = {
    "question": {"question", "질문"},
    "short_answer": {"short answer", "짧은 답변", "요약 답변", "핵심 답변", "요약"},
    "recommended_workflow": {"recommended workflow", "권장 워크플로"},
    "onnellab_application": {"onnellab application", "온넬랩 앱"},
    "references": {"references", "참고 자료"},
    "conclusion": {"conclusion", "결론"},
    "faq": {"faq", "자주 묻는 질문"},
}


def has_required_sections(found_sections: set[str]) -> bool:
    return all(aliases & found_sections for aliases in SECTION_ALIASES.values())


def has_clear_definitions(body: str) -> bool:
    lowered = body.lower()
    return any(
        phrase in lowered
        for phrase in [
            "virtual rendering is",
            "encoding is",
            "가상 렌더링은",
            "인코딩은",
        ]
    )


def find_product_section(body: str) -> int:
    lowered = body.lower()
    positions = [
        lowered.find("## onnellab application"),
        lowered.find("## 온넬랩 앱"),
    ]
    valid = [position for position in positions if position >= 0]
    return min(valid, default=-1)


def has_reference_section(found_sections: set[str]) -> bool:
    return bool(SECTION_ALIASES["references"] & found_sections)


def section_keys(found_sections: set[str]) -> set[str]:
    return {key for key, aliases in SECTION_ALIASES.items() if aliases & found_sections}


def find_counterpart(topic: dict[str, str], topics_path: Path) -> dict[str, str] | None:
    counterpart_language = "en" if topic["primary_language"] == "ko" else "ko"
    for row in read_csv(topics_path, TOPIC_HEADER):
        if (
            row["primary_language"] == counterpart_language
            and row["category"] == topic["category"]
            and row["slug"] == topic["slug"]
            and row["canonical_path"]
        ):
            return row
    return None


def translation_quality_passes(
    topic: dict[str, str],
    metadata: dict[str, str],
    body: str,
    found_sections: set[str],
    topics_path: Path,
) -> tuple[bool, str]:
    counterpart = find_counterpart(topic, topics_path)
    if not counterpart:
        return False, "English and Korean counterparts must exist before publication."
    counterpart_path = markdown_path_for(counterpart, topics_path)
    counterpart_metadata, counterpart_body = parse_front_matter(counterpart_path.read_text(encoding="utf-8"))
    counterpart_sections = sections(counterpart_body)
    if metadata.get("slug") != counterpart_metadata.get("slug"):
        return False, "Translated counterparts must share the same slug."
    missing_sections = section_keys(counterpart_sections) - section_keys(found_sections)
    if missing_sections:
        return False, f"Translated article is missing counterpart section(s): {', '.join(sorted(missing_sections))}."
    if topic["primary_language"] == "ko":
        forbidden_terms = ["plain-text", "rich text"]
        lowered_body = body.lower()
        found_forbidden = [term for term in forbidden_terms if term in lowered_body]
        if found_forbidden:
            return False, f"Korean translation contains avoidable English mixed terms: {', '.join(found_forbidden)}."
        required_korean_terms = ["일반 텍스트", "인코딩", "가상 렌더링"]
        missing_terms = [term for term in required_korean_terms if term not in body]
        if missing_terms:
            return False, f"Korean translation is missing required localized term(s): {', '.join(missing_terms)}."
    return True, "Translation counterpart, section alignment, slug alignment, and localized terminology are valid."


def svg_arrows_avoid_cards(svg: str) -> bool:
    card_matches = [
        (int(match.group(1)), int(match.group(2)))
        for match in re.finditer(r'<g transform="translate\((\d+) \d+\)"><rect width="(\d+)"', svg)
    ]
    arrow_matches = [
        (int(match.group(1)), int(match.group(2)))
        for match in re.finditer(r'<path d="M(\d+) 295H(\d+)', svg)
    ]
    if len(card_matches) < 2 or len(arrow_matches) != len(card_matches) - 1:
        return False
    for index, (start, end) in enumerate(arrow_matches):
        previous_x, previous_width = card_matches[index]
        next_x, _ = card_matches[index + 1]
        if start <= previous_x + previous_width or end >= next_x:
            return False
    return True


def image_quality_passes(topic: dict[str, str], assets: list[str], assets_root: Path) -> tuple[bool, str]:
    if not assets:
        return False, "Article has no referenced blog image asset."
    for asset in assets:
        expected_prefix = f"/blog-assets/{topic['primary_language']}/{topic['slug']}/"
        if not asset.startswith(expected_prefix):
            return False, f"Image asset path must be language-specific: {expected_prefix}"
        asset_path = assets_root / asset.removeprefix("/blog-assets/")
        if not asset_path.exists():
            return False, f"Referenced image asset does not exist: {asset}"
        if asset_path.suffix != ".svg":
            continue
        svg = asset_path.read_text(encoding="utf-8")
        required_fragments = ['viewBox="0 0 1200 675"', "<title", "<desc", "<tspan"]
        missing = [fragment for fragment in required_fragments if fragment not in svg]
        if missing:
            return False, f"SVG is missing quality structure fragment(s): {', '.join(missing)}."
        if "…" in svg:
            return False, "SVG text must wrap on spaces instead of truncating with an ellipsis."
        if not svg_arrows_avoid_cards(svg):
            return False, "SVG arrows must remain in the gaps between workflow cards."
        if topic["primary_language"] == "ko":
            forbidden_svg_terms = ["Problem", "Workflow", "Result", "Generated workflow asset"]
            found = [term for term in forbidden_svg_terms if term in svg]
            if found:
                return False, f"Korean SVG contains untranslated text: {', '.join(found)}."
    return True, "Referenced image assets use language-specific paths, accessible SVG structure, word wrapping, and non-overlapping arrows."


def score_article(topic: dict[str, str], markdown: str, topics_path: Path, metadata_root: Path, assets_root: Path) -> dict[str, object]:
    metadata, body = parse_front_matter(markdown)
    found_sections = sections(body)
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, points: float, note: str) -> None:
        checks.append({"name": name, "passed": passed, "points": points if passed else 0.0, "max_points": points, "note": note})

    required_metadata = ["title", "slug", "description", "status", "topic_id", "search_intent", "primary_keyword", "tags"]
    add("metadata_complete", all(metadata.get(key) for key in required_metadata), 1.2, "Pre-publication frontmatter contains the fields needed for review and scheduling.")

    add("required_sections", has_required_sections(found_sections), 1.4, "Article includes the required problem-first and publication sections.")

    add("structured_answer", bool(re.search(r"^\d+\.\s+", body, flags=re.MULTILINE)) and "|" in body, 1.0, "Article includes steps and a comparison table.")
    add("clear_definitions", has_clear_definitions(body), 0.8, "Article defines important technical terms.")
    add("primary_keyword", topic["primary_keyword"].lower() in (metadata.get("title", "") + " " + body).lower(), 0.8, "Primary keyword appears naturally.")
    add("external_reference", "https://" in body and has_reference_section(found_sections), 0.8, "Article cites an official or recognized external reference.")

    app_section = find_product_section(body)
    related_apps = split_pipe(topic["related_apps"])
    first_app = min((body.lower().find(app.lower()) for app in related_apps if app.lower() in body.lower()), default=-1)
    add(
        "product_after_education",
        app_section >= 0 and (not related_apps or first_app >= app_section),
        1.0,
        "Product appears after the educational explanation, or the article explicitly has no related application.",
    )

    assets = blog_asset_paths(body)
    asset_ok = bool(assets)
    for asset in assets:
        asset_path = assets_root / asset.removeprefix("/blog-assets/")
        asset_ok = asset_ok and asset_path.exists()
    add("publish_ready_image", asset_ok, 1.0, "At least one referenced blog image asset exists.")
    image_ok, image_note = image_quality_passes(topic, assets, assets_root)
    add("image_quality", image_ok, 1.0, image_note)

    links_path = metadata_path(topic, metadata_root)
    related_count = related_article_count(links_path)
    link_points = 1.0 if related_count > 0 else 0.6 if links_path.exists() else 0.0
    checks.append(
        {
            "name": "internal_links",
            "passed": links_path.exists(),
            "points": link_points,
            "max_points": 1.0,
            "note": "Internal link metadata exists; full credit requires at least one related article.",
        }
    )

    word_count = len(re.findall(r"\b[\w'-]+\b", body))
    add("readability_depth", 200 <= word_count <= 1800, 1.0, "Article length supports a complete but focused answer.")

    translation_ok, translation_note = translation_quality_passes(topic, metadata, body, found_sections, topics_path)
    add("translation_quality", translation_ok, 1.0, translation_note)

    points = sum(float(check["points"]) for check in checks)
    max_points = sum(float(check["max_points"]) for check in checks)
    score = round(points / max_points * 10, 2) if max_points else 0.0
    return {
        "version": 1,
        "type": "article_review",
        "topic_id": topic["id"],
        "title": topic["working_title"],
        "score": score,
        "threshold": DEFAULT_THRESHOLD,
        "passed": score > DEFAULT_THRESHOLD,
        "checks": checks,
    }


def evaluate_article(
    topic_id: str,
    topics_path: Path = DEFAULT_TOPICS_PATH,
    metadata_root: Path = DEFAULT_METADATA_ROOT,
    assets_root: Path = DEFAULT_ASSETS_ROOT,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> Path:
    topic = find_topic(topic_id, topics_path)
    markdown_path = markdown_path_for(topic, topics_path)
    review = score_article(topic, markdown_path.read_text(encoding="utf-8"), topics_path, metadata_root, assets_root)
    path = review_path(topic, review_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate article readiness before scheduling or publishing")
    parser.add_argument("topic_id")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--metadata-root", type=Path, default=DEFAULT_METADATA_ROOT)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    args = parser.parse_args()
    try:
        path = evaluate_article(args.topic_id, args.topics, args.metadata_root, args.assets_root, args.review_root)
    except (ArticleEvaluationError, OSError, json.JSONDecodeError) as error:
        print(f"article evaluation failed: {error}", file=sys.stderr)
        return 1
    print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
