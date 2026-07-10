#!/usr/bin/env python3
"""Generate a Markdown draft from an approved topic.

The generator creates Markdown only. It does not generate images, publish
content, or run external research.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from topic_management import (
    APP_HEADER,
    DEFAULT_APPS_PATH,
    DEFAULT_TOPICS_PATH,
    LEGACY_TOPICS_PATH,
    TOPIC_HEADER,
    TopicError,
    TopicStore,
    read_csv,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = ROOT / "templates" / "blog" / "markdown_draft.md"
DEFAULT_OUTPUT_ROOT = ROOT / "generated" / "markdown"


class MarkdownGenerationError(ValueError):
    """Raised when a Markdown draft cannot be generated safely."""


def load_apps(apps_path: Path = DEFAULT_APPS_PATH) -> dict[str, dict[str, str]]:
    return {row["app_name"]: row for row in read_csv(apps_path, APP_HEADER)}


def find_topic(rows: list[dict[str, str]], topic_id: str) -> dict[str, str]:
    for row in rows:
        if row["id"] == topic_id:
            return row
    raise MarkdownGenerationError(f"topic not found: {topic_id}")


def markdown_escape(value: str) -> str:
    return value.strip()


def yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def sentence_from_question(question: str) -> str:
    cleaned = question.strip().rstrip("?")
    if not cleaned:
        return "the topic"
    return cleaned[0].lower() + cleaned[1:]


def card_title(title: str) -> str:
    cleaned = title.strip()
    if cleaned.lower().startswith("how to "):
        cleaned = cleaned[7:].strip()
    return cleaned or title.strip()


def split_pipe(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def render_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_steps(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def product_section(topic: dict[str, str], apps: dict[str, dict[str, str]]) -> str:
    app_names = split_pipe(topic["related_apps"])
    if not app_names:
        return (
            "No ONNELLAB application is recommended in this draft yet. "
            "The article should remain useful without a product recommendation."
        )

    lines = [
        "After the problem and workflow are understood, the following ONNELLAB application may be relevant:"
    ]
    for app_name in app_names:
        app = apps[app_name]
        if app["status"] not in {"released", "beta"} or app["content_eligible"] != "true" or not app["official_site_path"]:
            raise MarkdownGenerationError(f"{app_name} is not eligible for public recommendation")
        lines.append(f"- [{app_name}]({app['official_site_path']}): {app['one_line_description']}")
    lines.append("Mention the application only where it directly supports the reader's workflow.")
    return "\n".join(lines)


def related_topics(topic: dict[str, str]) -> str:
    keywords = split_pipe(topic["secondary_keywords"])
    related = keywords[:3]
    if topic["primary_keyword"] and topic["primary_keyword"] not in related:
        related.insert(0, topic["primary_keyword"])
    if not related:
        related = [topic["category"]]
    return render_list([f"Further reading placeholder: {item}" for item in related[:4]])


def localized_labels(language: str) -> dict[str, str]:
    if language == "ko":
        return {
            "question_heading": "질문",
            "short_answer_heading": "요약 답변",
            "problem_heading": "이 문제가 생기는 이유",
            "diagnostic_heading": "문제가 더 심하게 느껴지는 경우",
            "checklist_heading": "먼저 확인할 항목",
            "workflow_heading": "권장 워크플로",
            "app_heading": "ONNELLAB 앱",
            "related_heading": "관련 주제",
            "references_heading": "참고 자료",
            "conclusion_heading": "결론",
            "faq_heading": "자주 묻는 질문",
            "workflow_image_alt": "워크플로 다이어그램",
            "workflow_image_title": "권장 과정을 설명하는 워크플로 다이어그램",
        }
    return {
        "question_heading": "Question",
        "short_answer_heading": "Short Answer",
        "problem_heading": "Why This Problem Happens",
        "diagnostic_heading": "What Makes This Problem Feel Worse",
        "checklist_heading": "What To Check First",
        "workflow_heading": "Recommended Workflow",
        "app_heading": "ONNELLAB Application",
        "related_heading": "Related Topics",
        "references_heading": "References",
        "conclusion_heading": "Conclusion",
        "faq_heading": "FAQ",
        "workflow_image_alt": "Workflow diagram placeholder",
        "workflow_image_title": "Planned workflow diagram for the recommended process",
    }


def draft_context(topic: dict[str, str], apps: dict[str, dict[str, str]]) -> dict[str, str]:
    subject = sentence_from_question(topic["primary_question"])
    keyword = topic["primary_keyword"]
    secondary = split_pipe(topic["secondary_keywords"])
    concepts = secondary[:4] or [keyword]

    checklist_items = [
        f"Confirm the exact user problem: {topic['primary_question']}",
        f"Identify whether the issue is about {keyword} or a related workflow detail.",
        "Separate general explanation from any product recommendation.",
        "Keep claims objective and avoid unsupported performance or platform statements.",
    ]
    workflow_items = [
        "Define the problem in plain language.",
        "Explain why the problem occurs and which trade-offs matter.",
        "Compare practical solution paths without forcing a product choice.",
        "Recommend the most appropriate workflow for the reader's situation.",
        "Introduce an ONNELLAB application only if it directly solves the problem.",
    ]
    diagnostic_items = [
        "The size of the input can matter, but size alone rarely explains every slowdown.",
        "Long continuous sections may be harder to process than shorter structured sections.",
        "Encoding, file format, device memory, and search behavior can all affect the experience.",
        "The reader should identify whether the task is reading, searching, converting, or editing before choosing a tool.",
    ]
    faq = [
        f"**Is this article mainly about {keyword}?**\n\nYes. The draft should stay focused on one primary question and avoid unrelated keywords.",
        "**Should the article start with an ONNELLAB product?**\n\nNo. The article should explain the reader's problem before mentioning any application.",
        "**Can this draft include images?**\n\nNo. Image planning and image production are separate workflow stages.",
    ]

    context = {
        "title": topic["working_title"],
        "card_title": card_title(topic["working_title"]),
        "slug": topic["slug"],
        "category": topic["category"],
        "primary_language": topic["primary_language"],
        "meta_description": (
            f"Learn how to evaluate {keyword}, understand the practical trade-offs, and choose a workflow that solves "
            "the problem without unnecessary complexity."
        ),
        "topic_id": topic["id"],
        "search_intent": topic["search_intent"],
        "primary_keyword": keyword,
        "secondary_keywords": topic["secondary_keywords"],
        "related_apps": topic["related_apps"],
        "image_specs": (
            f"Workflow diagram for {keyword}|Comparison diagram for practical options|Screenshot requirements for related applications"
        ),
        "primary_question": topic["primary_question"],
        "short_answer": (
            f"The practical answer is to understand {subject}, then choose a workflow that solves the problem "
            f"without adding unnecessary complexity. This draft should explain {keyword} clearly before it mentions any product."
        ),
        "problem_explanation": (
            f"This problem usually appears when the reader does not yet know which part of the workflow matters most. "
            f"The article should define {keyword}, explain related concepts such as {', '.join(concepts)}, and describe "
            "the trade-offs in calm, objective language."
        ),
        "diagnostic_factors": "\n\n".join(diagnostic_items),
        "checklist": render_list(checklist_items),
        "workflow_steps": render_steps(workflow_items),
        "product_section": product_section(topic, apps),
        "related_topics": related_topics(topic),
        "references_section": (
            "Add official specifications, platform documentation, or recognized standards during review when they improve trust. "
            "Do not add low-quality external links."
        ),
        "conclusion": (
            f"Start with the reader's real task, explain {keyword} clearly, and recommend the simplest workflow that solves the problem. "
            "Mention an ONNELLAB application only after the educational answer is complete."
        ),
        "faq_section": "\n\n".join(faq),
    }
    context.update(localized_labels(topic["primary_language"]))
    return context


PLACEHOLDER_RE = re.compile(r"{{([a-zA-Z0-9_]+)}}")


def render_template(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise MarkdownGenerationError(f"unknown template placeholder: {key}")
        if key in {
            "title",
            "card_title",
            "slug",
            "category",
            "primary_language",
            "meta_description",
            "topic_id",
            "search_intent",
            "primary_keyword",
            "secondary_keywords",
            "related_apps",
            "image_specs",
        }:
            return yaml_escape(context[key])
        return markdown_escape(context[key])

    return PLACEHOLDER_RE.sub(replace, template)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def canonical_output_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def sync_legacy_topics(rows: list[dict[str, str]], legacy_path: Path | None = LEGACY_TOPICS_PATH) -> None:
    if legacy_path is None:
        return
    with legacy_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TOPIC_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_markdown(
    topic_id: str,
    topics_path: Path = DEFAULT_TOPICS_PATH,
    apps_path: Path = DEFAULT_APPS_PATH,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
) -> Path:
    store = TopicStore(topics_path, apps_path, mirror_path=legacy_topics_path)
    rows = store.read()
    topic = find_topic(rows, topic_id)
    if topic["status"] != "approved":
        raise MarkdownGenerationError(f"{topic_id} must be approved before Markdown generation")

    apps = load_apps(apps_path)
    for app_name in split_pipe(topic["related_apps"]):
        if app_name not in apps:
            raise MarkdownGenerationError(f"{topic_id} references unknown app: {app_name}")

    template = template_path.read_text(encoding="utf-8")
    content = render_template(template, draft_context(topic, apps))
    output_path = output_root / topic["primary_language"] / topic["category"] / f"{topic['slug']}.md"
    project_root = topics_path.parent.parent

    store.edit(topic_id, {"status": "research"})
    store.edit(topic_id, {"status": "outline"})
    write_markdown(output_path, content)
    store.edit(topic_id, {"status": "draft", "canonical_path": canonical_output_path(output_path, project_root)})
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Markdown draft from an approved topic")
    parser.add_argument("topic_id")
    args = parser.parse_args()
    try:
        path = generate_markdown(args.topic_id)
    except (MarkdownGenerationError, TopicError, OSError) as error:
        print(f"markdown generation failed: {error}", file=sys.stderr)
        return 1
    print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
