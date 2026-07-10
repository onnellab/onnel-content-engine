#!/usr/bin/env python3
"""Generate simple publish-ready SVG assets from image specifications."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from topic_management import DEFAULT_TOPICS_PATH, LEGACY_TOPICS_PATH, TOPIC_HEADER, TopicError, TopicStore, read_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGES_ROOT = ROOT / "generated" / "images"
DEFAULT_ASSETS_ROOT = ROOT / "generated" / "assets" / "blog"
SVG_FONT_STACK = "Pretendard, SUIT, Noto Sans KR, Apple SD Gothic Neo, Inter, system-ui, sans-serif"


class ImageAssetError(ValueError):
    """Raised when image asset generation cannot proceed."""


def find_topic_by_slug(rows: list[dict[str, str]], language: str, category: str, slug: str) -> dict[str, str]:
    for row in rows:
        if row["primary_language"] == language and row["category"] == category and row["slug"] == slug:
            return row
    raise ImageAssetError(f"topic not found for {language}/{category}/{slug}")


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_text(value: str, max_chars: int = 34) -> str:
    value = " ".join(value.split())
    return html_escape(value[: max_chars - 1] + "…") if len(value) > max_chars else html_escape(value)


def wrap_words(value: str, max_chars: int, max_lines: int = 2) -> list[str]:
    words = " ".join(value.split()).split(" ")
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    remaining_index = sum(len(line.split(" ")) for line in lines) + len(current.split(" "))
    if remaining_index < len(words):
        current = f"{current} ..."
    lines.append(current)
    return lines[:max_lines]


def svg_tspans(lines: list[str], x: int, y: int, line_height: int) -> str:
    return "".join(
        f'<tspan x="{x}" y="{y + index * line_height}">{html_escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )


def localized_steps(language: str) -> tuple[str, str, list[tuple[str, str]], str, str]:
    if language == "ko":
        return (
            "실용 워크플로",
            "도구를 추천하기 전에 과정을 먼저 설명합니다.",
            [
                ("1. 문제", "읽기 작업 확인"),
                ("2. 점검", "파일과 맥락 확인"),
                ("3. 흐름", "가벼운 경로 선택"),
                ("4. 결과", "마찰을 줄여 읽기"),
            ],
            "온넬랩 블로그 · 생성된 워크플로 자산",
            "워크플로 다이어그램",
        )
    return (
        "A practical workflow",
        "Explain the process before recommending a tool.",
        [
            ("1. Problem", "Identify the reader task"),
            ("2. Check", "Confirm file and context"),
            ("3. Workflow", "Choose the lightest path"),
            ("4. Result", "Read with less friction"),
        ],
        "ONNELLAB Blog · Generated workflow asset",
        "workflow diagram",
    )


def workflow_svg(title: str, keyword: str, language: str) -> str:
    title_lines = wrap_words(title, 34, max_lines=2)
    keyword = svg_text(keyword, 36)
    subtitle, bottom_message, steps, footer, description_label = localized_steps(language)
    cards = []
    card_width = 190
    card_gap = 84
    x = 72
    for heading, detail in steps:
        detail_lines = wrap_words(detail, 16, max_lines=2)
        cards.append(
            f'<g transform="translate({x} 220)">'
            f'<rect width="{card_width}" height="150" rx="18" fill="#fffdf8" stroke="#d8d0c3" stroke-width="1.6"/>'
            f'<text x="24" y="48" fill="#30302c" font-family="{SVG_FONT_STACK}" font-size="20" font-weight="650">{html_escape(heading)}</text>'
            f'<text fill="#5f5b54" font-family="{SVG_FONT_STACK}" font-size="16">{svg_tspans(detail_lines, 24, 88, 23)}</text>'
            "</g>"
        )
        x += card_width + card_gap
    arrows = "".join(
        f'<path d="M{72 + card_width + i * (card_width + card_gap) + 18} 295H{72 + (i + 1) * (card_width + card_gap) - 18}m-10-11 12 11-12 11" fill="none" stroke="#8c867b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        for i in range(3)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-labelledby="title desc">
  <title id="title">{html_escape(" ".join(title_lines))}</title>
  <desc id="desc">ONNELLAB {description_label} for {keyword}.</desc>
  <rect width="1200" height="675" fill="#fbf7ef"/>
  <rect x="54" y="48" width="1092" height="579" rx="28" fill="#f7f2e9" stroke="#ded7ca" stroke-width="1.8"/>
  <text fill="#30302c" font-family="{SVG_FONT_STACK}" font-size="38" font-weight="680">{svg_tspans(title_lines, 92, 112, 44)}</text>
  <text x="92" y="184" fill="#69645c" font-family="{SVG_FONT_STACK}" font-size="19">{html_escape(subtitle)} · {keyword}</text>
  {''.join(cards)}
  {arrows}
  <rect x="92" y="456" width="1016" height="82" rx="18" fill="#e7f2fb" stroke="#b9d7ea" stroke-width="1.6"/>
  <text x="124" y="506" fill="#30302c" font-family="{SVG_FONT_STACK}" font-size="20" font-weight="650">{html_escape(bottom_message)}</text>
  <text x="92" y="588" fill="#817c73" font-family="{SVG_FONT_STACK}" font-size="14">{html_escape(footer)}</text>
</svg>
'''


def spec_parts(spec_path: Path, images_root: Path) -> tuple[str, str, str]:
    relative = spec_path.relative_to(images_root)
    if len(relative.parts) != 4 or relative.name != "image_spec.json":
        raise ImageAssetError(f"unsupported image spec path: {spec_path}")
    return relative.parts[0], relative.parts[1], relative.parts[2]


def markdown_image_line(language: str, slug: str, title: str) -> str:
    alt = "워크플로 다이어그램" if language == "ko" else "Workflow diagram"
    return f'![{alt}](/blog-assets/{language}/{slug}/workflow-diagram.svg "{title}")'


def ensure_markdown_references_asset(markdown_path: Path, language: str, slug: str, title: str) -> None:
    content = markdown_path.read_text(encoding="utf-8")
    legacy_asset = f"/blog-assets/{slug}/workflow-diagram.svg"
    localized_asset = f"/blog-assets/{language}/{slug}/workflow-diagram.svg"
    if legacy_asset in content:
        content = content.replace(legacy_asset, localized_asset)
        markdown_path.write_text(content, encoding="utf-8")
        return
    if localized_asset in content:
        return
    marker = "## 권장 워크플로" if language == "ko" else "## Recommended Workflow"
    marker_index = content.find(marker)
    if marker_index == -1:
        raise ImageAssetError(f"cannot place workflow image in {markdown_path}")
    next_section = content.find("\n## ", marker_index + len(marker))
    if next_section == -1:
        updated = content.rstrip() + "\n\n" + markdown_image_line(language, slug, title) + "\n"
    else:
        updated = content[:next_section].rstrip() + "\n\n" + markdown_image_line(language, slug, title) + "\n" + content[next_section:]
    markdown_path.write_text(updated, encoding="utf-8")


def generate_image_asset(
    spec_path: Path,
    topics_path: Path = DEFAULT_TOPICS_PATH,
    images_root: Path = DEFAULT_IMAGES_ROOT,
    assets_root: Path = DEFAULT_ASSETS_ROOT,
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
    advance_to_review: bool = True,
) -> Path:
    rows = read_csv(topics_path, TOPIC_HEADER)
    language, category, slug = spec_parts(spec_path, images_root)
    topic = find_topic_by_slug(rows, language, category, slug)
    if topic["status"] not in {"image_planning", "review", "scheduled", "published", "update_required"}:
        raise ImageAssetError(f"{topic['id']} must be in image_planning or later before image asset generation")
    if not topic["canonical_path"]:
        raise ImageAssetError(f"{topic['id']} has no canonical_path")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    title = str(spec.get("workflow_diagrams", [{}])[0].get("title") or topic["working_title"])
    keyword = topic["primary_keyword"]
    output_path = assets_root / language / slug / "workflow-diagram.svg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(workflow_svg(title, keyword, language), encoding="utf-8")
    markdown_path = topics_path.parent.parent / topic["canonical_path"]
    ensure_markdown_references_asset(markdown_path, language, slug, title)
    if advance_to_review and topic["status"] == "image_planning":
        TopicStore(topics_path, mirror_path=legacy_topics_path).edit(topic["id"], {"status": "review"})
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a publish-ready SVG asset from image_spec.json")
    parser.add_argument("spec_path", type=Path)
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--legacy-topics", type=Path, default=LEGACY_TOPICS_PATH)
    parser.add_argument("--no-advance", action="store_true", help="Do not advance image_planning topics to review")
    args = parser.parse_args()
    try:
        path = generate_image_asset(
            args.spec_path,
            topics_path=args.topics,
            images_root=args.images_root,
            assets_root=args.assets_root,
            legacy_topics_path=args.legacy_topics,
            advance_to_review=not args.no_advance,
        )
    except (ImageAssetError, TopicError, OSError, json.JSONDecodeError) as error:
        print(f"image asset generation failed: {error}", file=sys.stderr)
        return 1
    print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
