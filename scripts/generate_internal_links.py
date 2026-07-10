#!/usr/bin/env python3
"""Generate internal recommendation metadata.

This script analyzes topic records, the knowledge graph principles, related
applications, and topic clusters. It writes metadata only and never modifies
article Markdown text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from topic_management import (
    APP_HEADER,
    DEFAULT_APPS_PATH,
    DEFAULT_TOPICS_PATH,
    TOPIC_HEADER,
    read_csv,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "generated" / "metadata"


class InternalLinkError(ValueError):
    """Raised when recommendation metadata cannot be generated."""


def split_pipe(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def normalize_words(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "can",
        "for",
        "how",
        "i",
        "is",
        "of",
        "or",
        "the",
        "to",
        "what",
        "when",
        "with",
        "without",
    }
    return {word for word in words if word not in stop_words and len(word) > 1}


def topic_cluster(topic: dict[str, str]) -> list[str]:
    terms: list[str] = []
    terms.extend(split_pipe(topic["secondary_keywords"]))
    terms.append(topic["primary_keyword"])
    terms.append(topic["category"])
    seen: set[str] = set()
    clusters: list[str] = []
    for term in terms:
        cleaned = term.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            clusters.append(cleaned)
            seen.add(key)
    return clusters


def load_apps(apps_path: Path) -> dict[str, dict[str, str]]:
    return {row["app_name"]: row for row in read_csv(apps_path, APP_HEADER)}


def find_topic(rows: list[dict[str, str]], topic_id: str) -> dict[str, str]:
    for row in rows:
        if row["id"] == topic_id:
            return row
    raise InternalLinkError(f"topic not found: {topic_id}")


def article_url(topic: dict[str, str]) -> str:
    if topic["published_url"]:
        return topic["published_url"]
    if topic["canonical_path"]:
        return topic["canonical_path"]
    return f"generated/markdown/{topic['primary_language']}/{topic['category']}/{topic['slug']}.md"


def relationship(target: dict[str, str], candidate: dict[str, str], shared_clusters: set[str]) -> str:
    if candidate["search_intent"] == "learn" and target["search_intent"] in {"solve", "workflow", "troubleshoot"}:
        return "prerequisite"
    if candidate["search_intent"] == "compare":
        return "comparison"
    if candidate["search_intent"] == "troubleshoot":
        return "troubleshooting"
    if candidate["search_intent"] in {"workflow", "solve"} and shared_clusters:
        return "deeper"
    if candidate["category"] != target["category"]:
        return "cross_domain"
    return "related"


def score_article(target: dict[str, str], candidate: dict[str, str]) -> tuple[int, set[str]]:
    target_clusters = {item.lower() for item in topic_cluster(target)}
    candidate_clusters = {item.lower() for item in topic_cluster(candidate)}
    shared_clusters = target_clusters & candidate_clusters
    target_apps = set(split_pipe(target["related_apps"]))
    candidate_apps = set(split_pipe(candidate["related_apps"]))
    shared_apps = target_apps & candidate_apps
    target_words = normalize_words(" ".join([target["primary_question"], target["working_title"], target["primary_keyword"]]))
    candidate_words = normalize_words(" ".join([candidate["primary_question"], candidate["working_title"], candidate["primary_keyword"]]))
    shared_words = target_words & candidate_words

    score = 0
    if candidate["category"] == target["category"]:
        score += 4
    score += len(shared_clusters) * 3
    score += len(shared_apps) * 3
    score += min(len(shared_words), 4)
    if candidate["status"] == "published":
        score += 2
    elif candidate["status"] in {"draft", "image_planning", "review", "scheduled"}:
        score += 1
    if candidate["primary_language"] == target["primary_language"]:
        score += 1
    return score, shared_clusters


def related_articles(target: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, object]]:
    recommendations: list[dict[str, object]] = []
    for candidate in rows:
        if candidate["id"] == target["id"]:
            continue
        if candidate["status"] in {"idea", "approved", "research", "outline", "archived", "failed"}:
            continue
        score, shared_clusters = score_article(target, candidate)
        if score <= 0:
            continue
        recommendations.append(
            {
                "topic_id": candidate["id"],
                "title": candidate["working_title"],
                "slug": candidate["slug"],
                "category": candidate["category"],
                "language": candidate["primary_language"],
                "status": candidate["status"],
                "url": article_url(candidate),
                "relationship": relationship(target, candidate, shared_clusters),
                "shared_clusters": sorted(shared_clusters),
                "score": score,
            }
        )
    return sorted(recommendations, key=lambda item: (-int(item["score"]), str(item["topic_id"])))[:6]


def related_apps(target: dict[str, str], apps: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    recommendations: list[dict[str, object]] = []
    for index, app_name in enumerate(split_pipe(target["related_apps"])):
        if app_name not in apps:
            raise InternalLinkError(f"{target['id']} references unknown app: {app_name}")
        app = apps[app_name]
        if app["status"] not in {"released", "beta"} or app["content_eligible"] != "true" or not app["official_site_path"]:
            continue
        recommendations.append(
            {
                "app_id": app["app_id"],
                "app_name": app["app_name"],
                "slug": app["slug"],
                "category": app["primary_category"],
                "url": app["official_site_path"],
                "description": app["one_line_description"],
                "relationship": "solution",
                "priority": index + 1,
            }
        )
    return recommendations


def related_guides(target: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, object]]:
    clusters = topic_cluster(target)
    guides: list[dict[str, object]] = [
        {
            "type": "broader_topic",
            "title": f"{target['category'].title()} guide",
            "category": target["category"],
            "cluster": target["category"],
            "reason": "Provides the broader domain context required by the knowledge graph.",
        }
    ]

    if clusters:
        guides.append(
            {
                "type": "topic_cluster",
                "title": f"{clusters[0]} cluster",
                "category": target["category"],
                "cluster": clusters[0],
                "reason": "Connects the article to its nearest conceptual cluster.",
            }
        )

    cross_domain = next(
        (
            row
            for row in rows
            if row["id"] != target["id"]
            and row["category"] != target["category"]
            and set(normalize_words(row["primary_keyword"])) & set(normalize_words(target["primary_keyword"]))
        ),
        None,
    )
    if cross_domain:
        guides.append(
            {
                "type": "cross_domain",
                "title": cross_domain["working_title"],
                "category": cross_domain["category"],
                "cluster": cross_domain["primary_keyword"],
                "topic_id": cross_domain["id"],
                "reason": "Supports cross-domain navigation when the concepts overlap.",
            }
        )
    return guides


def output_path_for(target: dict[str, str], output_root: Path) -> Path:
    return output_root / target["primary_language"] / target["category"] / target["slug"] / "internal_links.json"


def build_metadata(target: dict[str, str], rows: list[dict[str, str]], apps: dict[str, dict[str, str]]) -> dict[str, object]:
    return {
        "version": 1,
        "type": "internal_link_recommendations",
        "generation_scope": "metadata_only",
        "article_text_modified": False,
        "source": {
            "topics": "data/topics.csv",
            "apps_registry": "data/apps_registry.csv",
            "knowledge_graph": "docs/Knowledge_Graph.md",
        },
        "topic": {
            "id": target["id"],
            "title": target["working_title"],
            "slug": target["slug"],
            "category": target["category"],
            "language": target["primary_language"],
            "status": target["status"],
            "topic_clusters": topic_cluster(target),
            "related_app_names": split_pipe(target["related_apps"]),
        },
        "recommendations": {
            "related_articles": related_articles(target, rows),
            "related_apps": related_apps(target, apps),
            "related_guides": related_guides(target, rows),
        },
        "rules": [
            "Recommendations represent conceptual relationships, not SEO-only links.",
            "Applications appear as solutions, not categories.",
            "Every recommendation should help the reader continue learning.",
            "No article Markdown is modified by this generator.",
        ],
    }


def generate_internal_links(
    topic_id: str,
    topics_path: Path = DEFAULT_TOPICS_PATH,
    apps_path: Path = DEFAULT_APPS_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> Path:
    rows = read_csv(topics_path, TOPIC_HEADER)
    target = find_topic(rows, topic_id)
    apps = load_apps(apps_path)
    metadata = build_metadata(target, rows, apps)
    output_path = output_path_for(target, output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate internal link recommendation metadata")
    parser.add_argument("topic_id")
    args = parser.parse_args()
    try:
        path = generate_internal_links(args.topic_id)
    except (InternalLinkError, OSError) as error:
        print(f"internal link generation failed: {error}", file=sys.stderr)
        return 1
    print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
