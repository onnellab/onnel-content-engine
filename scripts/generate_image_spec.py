#!/usr/bin/env python3
"""Generate image_spec.json from a Markdown draft.

This script creates planning specifications only. It does not generate images,
screenshots, diagrams, or publishing assets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from topic_management import (
    DEFAULT_APPS_PATH,
    DEFAULT_TOPICS_PATH,
    LEGACY_TOPICS_PATH,
    TopicError,
    TopicStore,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "generated" / "images"

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class ImageSpecError(ValueError):
    """Raised when image specification generation cannot proceed safely."""


def read_markdown(path: Path) -> str:
    if not path.exists():
        raise ImageSpecError(f"Markdown file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def parse_front_matter(markdown: str) -> dict[str, str]:
    match = FRONT_MATTER_RE.match(markdown)
    if not match:
        raise ImageSpecError("Markdown draft must contain YAML-style front matter")

    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def extract_headings(markdown: str) -> list[str]:
    return [match.group(2).strip() for match in HEADING_RE.finditer(markdown)]


def find_topic(rows: list[dict[str, str]], topic_id: str) -> dict[str, str]:
    for row in rows:
        if row["id"] == topic_id:
            return row
    raise ImageSpecError(f"topic not found: {topic_id}")


def split_pipe(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def spec_path_for(topic: dict[str, str], output_root: Path) -> Path:
    return output_root / topic["primary_language"] / topic["category"] / topic["slug"] / "image_spec.json"


def canonical_output_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def build_spec(markdown_path: Path, markdown: str, topic: dict[str, str]) -> dict[str, object]:
    headings = extract_headings(markdown)
    related_apps = split_pipe(topic["related_apps"])
    secondary_keywords = split_pipe(topic["secondary_keywords"])

    required_infographics: list[dict[str, object]] = [
        {
            "id": "workflow-primary",
            "type": "workflow",
            "required": True,
            "question_answered": f"What is the recommended workflow for {topic['primary_keyword']}?",
            "source_sections": ["Short Answer", "Recommended Workflow"],
            "structure": ["Problem", "Process", "Result"],
            "notes": "Use a calm, minimal workflow diagram. The visual should explain the process, not decorate the article.",
        }
    ]

    if secondary_keywords:
        required_infographics.append(
            {
                "id": "comparison-options",
                "type": "comparison",
                "required": True,
                "question_answered": f"Which concepts or approaches matter when evaluating {topic['primary_keyword']}?",
                "source_sections": ["Why This Problem Happens", "What To Check First"],
                "compare": secondary_keywords[:3],
                "notes": "Keep the comparison balanced and avoid presenting any ONNELLAB product as universally superior.",
            }
        )

    screenshot_required = bool(related_apps)
    screenshot_requirements = {
        "required": screenshot_required,
        "reason": (
            "Related ONNELLAB applications are referenced, so screenshots may be useful only if they demonstrate a real feature."
            if screenshot_required
            else "No related application is referenced; decorative screenshots are not required."
        ),
        "applications": related_apps,
        "rules": [
            "Use screenshots only to demonstrate a real feature.",
            "Crop unnecessary UI.",
            "Highlight only the relevant control or workflow area.",
            "Maintain high resolution.",
            "Do not use screenshots as decoration.",
        ],
    }

    workflow_diagrams = [
        {
            "id": "workflow-primary",
            "title": f"{topic['working_title']} Workflow",
            "steps": ["Problem", "Explanation", "Options", "Recommended workflow", "Optional application"],
            "layout": "vertical or left-to-right sequence",
        }
    ]

    comparison_diagrams = [
        {
            "id": "comparison-options",
            "title": f"{topic['primary_keyword']} Comparison",
            "items": secondary_keywords[:3] or [topic["primary_keyword"]],
            "layout": "side-by-side comparison table",
        }
    ]

    return {
        "version": 1,
        "type": "image_spec",
        "generation_scope": "specification_only",
        "image_generation_allowed": False,
        "source_markdown": canonical_output_path(markdown_path, ROOT),
        "topic": {
            "id": topic["id"],
            "title": topic["working_title"],
            "slug": topic["slug"],
            "category": topic["category"],
            "language": topic["primary_language"],
            "primary_keyword": topic["primary_keyword"],
            "related_apps": related_apps,
        },
        "article_sections_detected": headings,
        "visual_style": {
            "tone": ["calm", "clean", "minimal", "structured", "approachable", "timeless"],
            "colors": {
                "background": "Ivory Soft",
                "primary": "Baby Blue Calm",
                "secondary": "Dusty Lilac",
                "accent": "Soft Peach",
                "text": "Charcoal Soft",
            },
            "typography": ["ONNEL Sans", "System UI", "Pretendard", "Inter"],
            "accessibility": [
                "Readable on mobile",
                "Understandable in grayscale",
                "Color must not be the only information channel",
            ],
        },
        "required_infographic_types": required_infographics,
        "screenshot_requirements": screenshot_requirements,
        "workflow_diagrams": workflow_diagrams,
        "comparison_diagrams": comparison_diagrams,
        "prohibited": [
            "Do not generate image files in this step.",
            "Do not create screenshots in this step.",
            "Do not publish assets in this step.",
            "Do not use decorative visuals without explanatory purpose.",
        ],
    }


def generate_image_spec(
    markdown_path: Path,
    topics_path: Path = DEFAULT_TOPICS_PATH,
    apps_path: Path = DEFAULT_APPS_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
) -> Path:
    markdown = read_markdown(markdown_path)
    metadata = parse_front_matter(markdown)
    topic_id = metadata.get("topic_id")
    if not topic_id:
        raise ImageSpecError("Markdown front matter must include topic_id")

    store = TopicStore(topics_path, apps_path=apps_path, mirror_path=legacy_topics_path)
    rows = store.read()
    topic = find_topic(rows, topic_id)
    if topic["status"] != "draft":
        raise ImageSpecError(f"{topic_id} must be in draft status before image specification generation")
    if topic["canonical_path"] and Path(topic["canonical_path"]).name != markdown_path.name:
        raise ImageSpecError(f"{topic_id} canonical_path does not match the Markdown input")

    output_path = spec_path_for(topic, output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    spec = build_spec(markdown_path, markdown, topic)
    output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    store.edit(topic_id, {"status": "image_planning"})
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate image_spec.json from a Markdown draft")
    parser.add_argument("markdown_path", type=Path)
    args = parser.parse_args()
    try:
        path = generate_image_spec(args.markdown_path)
    except (ImageSpecError, TopicError, OSError) as error:
        print(f"image specification generation failed: {error}", file=sys.stderr)
        return 1
    print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
