#!/usr/bin/env python3
"""Build and assess Hashnode-native syndication content."""

from __future__ import annotations

import re


HASHNODE_CONTENT_PROFILE = "hashnode-native-v2"
HASHNODE_CATEGORY_TAGS = {
    "reading": ("programming", "performance", "text-processing"),
    "music": ("programming", "audio", "metadata"),
    "productivity": ("productivity", "software-engineering", "developer-tools"),
    "media": ("programming", "media-processing", "privacy"),
    "craft": ("programming", "developer-tools", "software-engineering"),
    "games": ("game-development", "programming", "performance"),
    "research": ("software-engineering", "research", "data"),
}
HASHNODE_DROPPED_SECTIONS = {"question", "related topics", "faq"}
HASHNODE_HEADING_RENAMES = {
    "short answer": "The constraint to solve",
    "what to check first": "Preflight checks",
    "recommended workflow": "Implementation path",
    "onnellab application": "When a focused tool helps",
    "conclusion": "Takeaway",
}
PRODUCT_URL_RE = re.compile(
    r"https?://(?:onnellab\.github\.io/apps/|apps\.apple\.com/|play\.google\.com/)[^)\s]+",
    re.IGNORECASE,
)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
EXTERNAL_URL_RE = re.compile(r"https?://[^)\s>\"]+")


def hashnode_tag_list(category: str) -> str:
    """Return a small, stable set of developer-community tags."""
    tags = HASHNODE_CATEGORY_TAGS.get(category.lower(), ("software-engineering", "programming"))
    return ",".join(tags)


def _limit_product_links(markdown: str, limit: int = 1) -> str:
    retained = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal retained
        label, url = match.groups()
        if not PRODUCT_URL_RE.fullmatch(url):
            return match.group(0)
        retained += 1
        return match.group(0) if retained <= limit else label

    return MARKDOWN_LINK_RE.sub(replace, markdown)


def hashnode_native_body(body: str) -> str:
    """Adapt canonical Markdown to a less repetitive Hashnode-native article body."""
    output: list[str] = []
    dropping_section = False
    for line in body.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level, title = heading.groups()
            normalized = title.strip().lower()
            if level == "#":
                continue
            if level == "##":
                dropping_section = normalized in HASHNODE_DROPPED_SECTIONS
                if dropping_section:
                    continue
                if re.fullmatch(r"where .+ fits", normalized):
                    title = "When a focused tool helps"
                else:
                    title = HASHNODE_HEADING_RENAMES.get(normalized, title)
                output.append(f"## {title}")
                continue
        if dropping_section:
            continue
        output.append(line)

    adapted = "\n".join(output).strip()
    adapted = re.sub(r"(?m)^>\s*ONNELLAB note:.*(?:\n|$)", "", adapted)
    adapted = _limit_product_links(adapted)
    return re.sub(r"\n{3,}", "\n\n", adapted).strip()


def _frontmatter_and_body(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    metadata: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, content[end + 5 :]


def hashnode_automod_risks(content: str, canonical_url: str) -> list[str]:
    """Return deterministic risk signals that must be resolved before publication."""
    metadata, body = _frontmatter_and_body(content)
    risks: list[str] = []
    if metadata.get("content_profile") != HASHNODE_CONTENT_PROFILE:
        risks.append(f"content_profile must be {HASHNODE_CONTENT_PROFILE}")
    if re.search(r"(?im)^>\s*ONNELLAB note:", body):
        risks.append("repeated ONNELLAB note is not allowed")
    if canonical_url and canonical_url in body:
        risks.append("canonical URL must be set as metadata, not repeated in the body")
    if re.search(r"(?im)^#\s+", body):
        risks.append("body must not repeat the article title as an H1")
    if re.search(r"(?im)^##\s+(Question|Short Answer|Related Topics|FAQ)\s*$", body):
        risks.append("generic canonical section headings must be adapted for Hashnode")

    product_links = PRODUCT_URL_RE.findall(body)
    if len(product_links) > 1:
        risks.append("body may contain at most one product link")
    external_links = EXTERNAL_URL_RE.findall(body)
    if len(external_links) > 8:
        risks.append("body contains more than eight external links")

    technical_signals = sum(
        (
            bool(re.search(r"(?m)^```", body) or re.search(r"`[^`\n]+`", body)),
            bool(re.search(r"(?m)^\|.+\|\s*$", body)),
            bool(re.search(r"(?m)^\d+\.\s+", body)),
            bool(re.search(r"(?im)^##\s+(References|Implementation|Preflight|Definitions|Technical)", body)),
        )
    )
    if technical_signals < 2:
        risks.append("body needs at least two technical evidence signals")
    return risks
