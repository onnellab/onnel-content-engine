#!/usr/bin/env python3
"""Evaluate article readiness before scheduling or publishing."""

from __future__ import annotations

import argparse
import hashlib
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
REVIEW_VERSION = 2
FORBIDDEN_LOCAL_BRAND = "\uc628\ub128\ub7a9"
FINGERPRINT_TOPIC_FIELDS = (
    "id",
    "category",
    "primary_question",
    "working_title",
    "slug",
    "primary_language",
    "search_intent",
    "related_apps",
    "primary_keyword",
    "secondary_keywords",
    "source_type",
    "canonical_path",
)


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


def has_workflow_social_source(assets: list[str]) -> bool:
    return any(asset.endswith("/workflow-diagram.svg") for asset in assets)


def card_title_matches_title(metadata: dict[str, str]) -> bool:
    title = metadata.get("title", "").strip()
    card_title = metadata.get("card_title", metadata.get("cardTitle", "")).strip()
    return bool(title and card_title and title == card_title)


def brand_spelling_passes(metadata: dict[str, str], body: str) -> tuple[bool, str]:
    combined = "\n".join([*(str(value) for value in metadata.values()), body])
    if FORBIDDEN_LOCAL_BRAND in combined:
        return False, "Article text must keep the brand spelling as ONNELLAB."
    return True, "Article text keeps the ONNELLAB brand spelling consistent."


def related_article_count(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data.get("recommendations", {}).get("related_articles", []))


def _article_input_fingerprint(
    topic: dict[str, str],
    markdown: str,
    metadata_root: Path,
    assets_root: Path,
) -> str:
    links_path = metadata_path(topic, metadata_root)
    if links_path.exists():
        links_input = {"state": "present", "sha256": hashlib.sha256(links_path.read_bytes()).hexdigest()}
    else:
        links_input = {"state": "absent"}

    asset_inputs: list[dict[str, str]] = []
    for asset in sorted(set(blog_asset_paths(markdown))):
        asset_path = assets_root / asset.removeprefix("/blog-assets/")
        if asset_path.exists():
            asset_inputs.append(
                {"path": asset, "state": "present", "sha256": hashlib.sha256(asset_path.read_bytes()).hexdigest()}
            )
        else:
            asset_inputs.append({"path": asset, "state": "absent"})

    fingerprint_input = {
        "assets": asset_inputs,
        "evaluator_version": REVIEW_VERSION,
        "internal_links": links_input,
        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "topic": {field: topic.get(field, "") for field in FINGERPRINT_TOPIC_FIELDS},
    }
    canonical = json.dumps(
        fingerprint_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


SECTION_ALIASES = {
    "question": {"question", "질문"},
    "short_answer": {"short answer", "짧은 답변", "요약 답변", "핵심 답변", "요약"},
    "recommended_workflow": {"recommended workflow", "권장 워크플로"},
    "onnellab_application": {"onnellab application", "where onnellab fits", "onnellab 앱"},
    "references": {"references", "참고 자료"},
    "conclusion": {"conclusion", "결론"},
    "faq": {"faq", "자주 묻는 질문"},
}


def has_required_sections(found_sections: set[str]) -> bool:
    required = (aliases for key, aliases in SECTION_ALIASES.items() if key != "onnellab_application")
    return all(aliases & found_sections for aliases in required)


def has_clear_definitions(body: str) -> bool:
    prose = human_readable_prose(body)
    return bool(
        re.search(
            r"(?:^|[.!?]\s+|\n)(?!No\b)(?!(?:This|It)\s+(?:is|are|means|refers to)\b)"
            r"[A-Z][A-Za-z0-9 /-]{1,60}\s+"
            r"(?:is|are|means|refers to)\s+\S",
            prose,
            flags=re.MULTILINE,
        )
        or re.search(
            r"(?:^|\n|[.!?]\s*)(?!(?:이것|그것)(?:은|는|이|가)\b)"
            r"[가-힣A-Za-z0-9 /-]{1,40}(?:은|는|이|가)\s+[^.\n]{2,240}"
            r"(?:뜻합니다|의미합니다|말합니다|개념입니다|방법입니다|과정입니다|기술입니다|규칙입니다)",
            prose,
            flags=re.MULTILINE,
        )
    )


def has_short_answer(metadata: dict[str, str], found_sections: set[str], body: str) -> bool:
    if metadata.get("short_answer") or metadata.get("shortAnswer"):
        return True
    if not (SECTION_ALIASES["short_answer"] & found_sections):
        return False
    return bool(
        re.search(
            r"^##\s+(?:Short Answer|짧은 답변|요약 답변|핵심 답변|요약)\s*\n\n\S",
            body,
            flags=re.MULTILINE,
        )
    )


def find_product_section(body: str) -> int:
    return _find_section_position(body, "onnellab_application")


def has_reference_section(found_sections: set[str]) -> bool:
    return bool(SECTION_ALIASES["references"] & found_sections)


def section_keys(found_sections: set[str]) -> set[str]:
    return {key for key, aliases in SECTION_ALIASES.items() if aliases & found_sections}


def human_readable_prose(body: str) -> str:
    output: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        fence = body[index : index + 3]
        if fence in {"```", "~~~"}:
            closing = body.find(fence, index + 3)
            if closing < 0:
                output.append(fence)
                index += 3
                continue
            output.append(" ")
            index = closing + 3
            continue
        if body[index] == "`":
            closing = body.find("`", index + 1)
            if closing < 0:
                output.append("`")
                index += 1
                continue
            output.append(" ")
            index = closing + 1
            continue
        if body.startswith("](", index) and (index == 0 or body[index - 1] != "\\"):
            destination_start = index
            output.append("]")
            index += 2
            depth = 1
            while index < length and depth:
                if body[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                if body[index] == "(":
                    depth += 1
                elif body[index] == ")":
                    depth -= 1
                index += 1
            if depth:
                output[-1] = body[destination_start:]
                index = length
            continue
        lowered = body[index : index + 9].lower()
        if lowered.startswith("<http://") or lowered.startswith("<https://"):
            closing = body.find(">", index + 1)
            index = length if closing < 0 else closing + 1
            output.append(" ")
            continue
        if body[index : index + 7].lower() == "http://" or body[index : index + 8].lower() == "https://":
            while index < length and not body[index].isspace():
                index += 1
            output.append(" ")
            continue
        if body[index] == "*":
            index += 1
            continue
        output.append(body[index])
        index += 1
    return "".join(output)


def _h2_heading_positions(body: str) -> list[tuple[str, int]]:
    prose = human_readable_prose(body)
    return [
        (match.group(1).strip().lower(), match.start())
        for match in re.finditer(r"^##[ \t]+(.+?)\s*$", prose, flags=re.MULTILINE)
    ]


def _find_section_position(body: str, section_key: str) -> int:
    aliases = SECTION_ALIASES[section_key]
    return next((position for heading, position in _h2_heading_positions(body) if heading in aliases), -1)


def _contains_term(prose: str, term: str) -> bool:
    trailing_boundary = r"(?:(?!\w)|(?=[은는이가을를의과와도에에서로으]))"
    return bool(re.search(rf"(?<!\w){re.escape(term)}{trailing_boundary}", prose, flags=re.IGNORECASE))


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
        if FORBIDDEN_LOCAL_BRAND in body:
            return False, "Korean articles must keep the brand spelling as ONNELLAB."
        source_text = human_readable_prose(
            "\n".join(
                [
                    *(str(value) for value in counterpart_metadata.values()),
                    counterpart_body,
                    counterpart.get("primary_question", ""),
                    counterpart.get("working_title", ""),
                    counterpart.get("primary_keyword", ""),
                    counterpart.get("secondary_keywords", ""),
                ]
            )
        )
        terminology = [
            (("plain text", "plain-text"), "일반 텍스트"),
            (("rich text",), None),
            (("encoding",), "인코딩"),
            (("virtual rendering",), "가상 렌더링"),
        ]
        relevant_terms = [entry for entry in terminology if any(_contains_term(source_text, term) for term in entry[0])]
        forbidden_terms = sorted({term for source_terms, _ in relevant_terms for term in source_terms})
        visible_body = human_readable_prose(body)
        found_forbidden = [term for term in forbidden_terms if _contains_term(visible_body, term)]
        if found_forbidden:
            return False, f"Korean translation contains avoidable English mixed terms: {', '.join(found_forbidden)}."
        required_korean_terms = [localized_term for _, localized_term in relevant_terms if localized_term]
        missing_terms = [term for term in required_korean_terms if not _contains_term(visible_body, term)]
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
        if "…" in svg or "..." in svg:
            return False, "SVG text must wrap on spaces instead of truncating with an ellipsis."
        if not svg_arrows_avoid_cards(svg):
            return False, "SVG arrows must remain in the gaps between workflow cards."
        if topic["primary_language"] == "ko":
            forbidden_svg_terms = ["Problem", "Workflow", "Result", "Generated workflow asset"]
            found = [term for term in forbidden_svg_terms if term in svg]
            if found:
                return False, f"Korean SVG contains untranslated text: {', '.join(found)}."
            if FORBIDDEN_LOCAL_BRAND in svg or "ONNELLAB Blog" not in svg:
                return False, "Korean SVG must keep the brand label as ONNELLAB Blog."
    return True, "Referenced image assets use language-specific paths, accessible SVG structure, word wrapping, and non-overlapping arrows."


def score_article(topic: dict[str, str], markdown: str, topics_path: Path, metadata_root: Path, assets_root: Path) -> dict[str, object]:
    metadata, body = parse_front_matter(markdown)
    found_sections = sections(body)
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, points: float, note: str) -> None:
        checks.append({"name": name, "passed": passed, "points": points if passed else 0.0, "max_points": points, "note": note})

    required_metadata = ["title", "slug", "description", "status", "topic_id", "search_intent", "primary_keyword", "tags"]
    add("metadata_complete", all(metadata.get(key) for key in required_metadata), 1.2, "Pre-publication frontmatter contains the fields needed for review and scheduling.")
    add(
        "card_title_consistent",
        card_title_matches_title(metadata),
        0.4,
        "Blog list card title matches the article title so index and article pages stay consistent.",
    )
    brand_ok, brand_note = brand_spelling_passes(metadata, body)
    add("brand_spelling", brand_ok, 0.4, brand_note)

    related_apps = split_pipe(topic["related_apps"])
    add(
        "required_sections",
        has_required_sections(found_sections)
        and (not related_apps or bool(SECTION_ALIASES["onnellab_application"] & found_sections)),
        1.4,
        "Article includes the required problem-first and publication sections.",
    )
    add("short_answer_ready", has_short_answer(metadata, found_sections, body), 0.6, "Article exposes a direct short answer for readers, answer engines, and llms.txt summaries.")

    add("structured_answer", bool(re.search(r"^\d+\.\s+", body, flags=re.MULTILINE)) and "|" in body, 1.0, "Article includes steps and a comparison table.")
    add("clear_definitions", has_clear_definitions(body), 0.8, "Article defines important technical terms.")
    add("primary_keyword", topic["primary_keyword"].lower() in (metadata.get("title", "") + " " + body).lower(), 0.8, "Primary keyword appears naturally.")
    add("external_reference", "https://" in body and has_reference_section(found_sections), 0.8, "Article cites an official or recognized external reference.")

    app_section = find_product_section(body)
    workflow_section = _find_section_position(body, "recommended_workflow")
    visible_body = human_readable_prose(body).lower()
    first_app = min(
        (visible_body.find(app.lower()) for app in related_apps if app.lower() in visible_body),
        default=-1,
    )
    add(
        "product_after_education",
        not related_apps or (workflow_section >= 0 and app_section > workflow_section and first_app >= app_section),
        1.0,
        "Product appears after the educational explanation, or the article explicitly has no related application.",
    )

    assets = blog_asset_paths(body)
    asset_ok = bool(assets)
    for asset in assets:
        asset_path = assets_root / asset.removeprefix("/blog-assets/")
        asset_ok = asset_ok and asset_path.exists()
    add("publish_ready_image", asset_ok, 1.0, "At least one referenced blog image asset exists.")
    add(
        "social_card_source",
        has_workflow_social_source(assets),
        0.4,
        "A language-specific workflow diagram is available for social card generation.",
    )
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
        "version": REVIEW_VERSION,
        "type": "article_review",
        "topic_id": topic["id"],
        "title": topic["working_title"],
        "input_fingerprint": _article_input_fingerprint(topic, markdown, metadata_root, assets_root),
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
