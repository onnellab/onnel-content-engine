#!/usr/bin/env python3
"""Score generated social drafts and template readiness."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from publishing import x_weighted_length
from validate_social_posts import DEFAULT_MANIFEST_PATH, ROOT, SocialValidationError, validate_social_posts


PLACEHOLDER_RE = re.compile(r"\{\{[a-zA-Z0-9_]+\}\}")
REPETITION_PATTERNS = (
    "workflow problem",
    "plain-text file",
    "large txt file",
    "slow text file",
    "tool choice",
    "opens, renders, and searches",
)


def score_post(post: dict[str, object], project_root: Path = ROOT) -> dict[str, object]:
    draft_path = project_root / str(post["draft_path"])
    text = draft_path.read_text(encoding="utf-8").strip()
    platform = str(post["platform"])
    language = str(post["language"])
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, points: float) -> None:
        checks.append({"name": name, "passed": passed, "points": points if passed else 0.0, "max_points": points})

    add("canonical_url", str(post["canonical_url"]) in text, 1.5)
    add("no_placeholders", not PLACEHOLDER_RE.search(text), 1.0)
    add("png_card", str(post["card_asset_path"]).endswith(".png"), 1.0)
    add("template_tracked", bool(post.get("template_id")) and bool(post.get("template_path")), 1.0)
    add("approval_fields", all(field in post for field in ["approved_by", "approved_at", "post_id", "posted_url", "retry_count"]), 1.0)
    add("metrics_fields", all(field in post for field in ["impressions", "clicks", "engagements", "last_metrics_at"]), 0.7)
    if platform == "x":
        add("x_weighted_length", x_weighted_length(text) <= 280, 1.8)
        add("x_compact", x_weighted_length(text) <= 240, 1.0)
    if platform == "bluesky":
        add("bluesky_length", len(text) <= 300, 1.8)
        add("bluesky_compact", len(text) <= 260, 1.0)
    if platform == "linkedin":
        cta = "전체 글 읽기:" if language == "ko" else "Read the full article:"
        bullet_count = sum(1 for line in text.splitlines() if line.startswith("- "))
        add("linkedin_cta", cta in text, 1.2)
        add("linkedin_bullets", 0 < bullet_count <= 3, 1.0)
        add("linkedin_readable_length", len(text) <= 900, 1.0)
    total = round(sum(float(check["points"]) for check in checks), 2)
    maximum = round(sum(float(check["max_points"]) for check in checks), 2)
    score = round(total / maximum * 10, 2) if maximum else 0.0
    return {
        "topic_id": post["topic_id"],
        "platform": platform,
        "language": language,
        "template_id": post["template_id"],
        "status": post["status"],
        "score": score,
        "checks": checks,
    }


def repetition_warnings(posts: list[dict[str, object]], project_root: Path = ROOT) -> list[dict[str, object]]:
    """Find repeated phrases among actionable primary drafts.

    Posted history and mutually exclusive variants remain scoreable, but they do
    not represent copy that will be published together and must not inflate the
    repetition gate.
    """
    texts: list[str] = []
    for post in posts:
        if post.get("is_variant") or post.get("status") == "posted":
            continue
        draft_path = project_root / str(post["draft_path"])
        if draft_path.exists():
            texts.append(draft_path.read_text(encoding="utf-8").lower())
    repeated: list[dict[str, object]] = []
    for pattern in REPETITION_PATTERNS:
        count = sum(text.count(pattern) for text in texts)
        if count > 2:
            repeated.append({"phrase": pattern, "count": count, "severity": "warning"})
    return repeated


def evaluate_social_templates(manifest_path: Path = DEFAULT_MANIFEST_PATH, project_root: Path = ROOT) -> dict[str, object]:
    validate_social_posts(manifest_path, project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    posts = [post for post in manifest["posts"] if isinstance(post, dict)]
    evaluations = [score_post(post, project_root) for post in posts]
    average = round(sum(float(item["score"]) for item in evaluations) / len(evaluations), 2) if evaluations else 0.0
    return {
        "type": "social_template_evaluation",
        "average_score": average,
        "repetition_warnings": repetition_warnings(posts, project_root),
        "posts": evaluations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate generated social templates")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_social_templates(args.manifest)
    except (SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social template evaluation failed: {error}", file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(f"social template average score: {result['average_score']}/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
