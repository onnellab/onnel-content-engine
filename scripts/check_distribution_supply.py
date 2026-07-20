#!/usr/bin/env python3
"""Fail closed when a published article lacks channel-ready distribution copy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluate_social_templates import evaluate_social_templates
from evaluate_syndication_drafts import evaluate_syndication_drafts
from publishing import EXTERNAL_DISTRIBUTION_LANGUAGES
from topic_management import DEFAULT_TOPICS_PATH, TOPIC_HEADER, read_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOCIAL_MANIFEST = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION_MANIFEST = ROOT / "generated" / "syndication" / "manifest.json"
REQUIRED_SOCIAL_PLATFORMS = {"x", "linkedin", "bluesky"}
REQUIRED_SYNDICATION_PLATFORMS = {"devto", "hashnode", "medium"}


class DistributionSupplyError(ValueError):
    """Raised when downstream channel copy is missing or below the quality bar."""


def load_manifest(path: Path, collection: str) -> list[dict[str, object]]:
    if not path.exists():
        raise DistributionSupplyError(f"distribution manifest does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get(collection)
    if not isinstance(items, list):
        raise DistributionSupplyError(f"distribution manifest has no {collection}: {path}")
    return [item for item in items if isinstance(item, dict)]


def distribution_supply_report(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    project_root: Path | None = None,
    minimum_score: float = 9.5,
) -> dict[str, object]:
    project_root = project_root or topics_path.resolve().parent.parent
    topics = [
        row
        for row in read_csv(topics_path, TOPIC_HEADER)
        if row["status"] == "published" and row["primary_language"] in EXTERNAL_DISTRIBUTION_LANGUAGES
    ]
    social = load_manifest(social_manifest, "posts")
    syndication = load_manifest(syndication_manifest, "drafts")
    primary_social = [item for item in social if not item.get("is_variant")]

    missing: list[dict[str, str]] = []
    for topic in topics:
        identity = (topic["id"], topic["primary_language"])
        social_platforms = {
            str(item.get("platform", ""))
            for item in primary_social
            if (str(item.get("topic_id", "")), str(item.get("language", ""))) == identity
        }
        syndication_platforms = {
            str(item.get("platform", ""))
            for item in syndication
            if (str(item.get("topic_id", "")), str(item.get("language", ""))) == identity
        }
        for platform in sorted(REQUIRED_SOCIAL_PLATFORMS - social_platforms):
            missing.append({"topic_id": topic["id"], "channel": "social", "platform": platform})
        for platform in sorted(REQUIRED_SYNDICATION_PLATFORMS - syndication_platforms):
            missing.append({"topic_id": topic["id"], "channel": "syndication", "platform": platform})

    social_quality = evaluate_social_templates(social_manifest, project_root)
    syndication_quality = evaluate_syndication_drafts(syndication_manifest, project_root)
    social_score = float(social_quality["average_score"])
    syndication_score = float(syndication_quality["average_score"])
    repetition = social_quality.get("repetition_warnings") or []
    low_quality = [
        {
            "topic_id": str(item.get("topic_id", "")),
            "channel": "social",
            "platform": str(item.get("platform", "")),
            "score": float(item.get("score", 0.0)),
        }
        for item in social_quality.get("posts", [])
        if isinstance(item, dict)
        and not next(
            (
                post.get("is_variant")
                for post in social
                if post.get("topic_id") == item.get("topic_id")
                and post.get("platform") == item.get("platform")
                and post.get("language") == item.get("language")
                and post.get("template_id") == item.get("template_id")
            ),
            False,
        )
        and float(item.get("score", 0.0)) < minimum_score
    ]
    low_quality.extend(
        {
            "topic_id": str(item.get("topic_id", "")),
            "channel": "syndication",
            "platform": str(item.get("platform", "")),
            "score": float(item.get("score", 0.0)),
        }
        for item in syndication_quality.get("drafts", [])
        if isinstance(item, dict) and float(item.get("score", 0.0)) < minimum_score
    )
    failures: list[str] = []
    if missing:
        failures.append(f"{len(missing)} required channel draft(s) missing")
    if social_score < minimum_score:
        failures.append(f"social score {social_score}/10 is below {minimum_score}/10")
    if syndication_score < minimum_score:
        failures.append(f"syndication score {syndication_score}/10 is below {minimum_score}/10")
    if repetition:
        failures.append(f"{len(repetition)} social repetition warning(s)")
    if low_quality:
        failures.append(f"{len(low_quality)} individual channel draft(s) below {minimum_score}/10")
    return {
        "published_source_count": len(topics),
        "required_social_platforms": sorted(REQUIRED_SOCIAL_PLATFORMS),
        "required_syndication_platforms": sorted(REQUIRED_SYNDICATION_PLATFORMS),
        "missing": missing,
        "social_average_score": social_score,
        "syndication_average_score": syndication_score,
        "repetition_warnings": repetition,
        "low_quality_drafts": low_quality,
        "minimum_score": minimum_score,
        "ready": not failures,
        "failures": failures,
    }


def require_distribution_supply(**kwargs: object) -> dict[str, object]:
    report = distribution_supply_report(**kwargs)
    if not report["ready"]:
        raise DistributionSupplyError("; ".join(str(item) for item in report["failures"]))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check downstream distribution supply and quality")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--minimum-score", type=float, default=9.5)
    args = parser.parse_args()
    try:
        report = require_distribution_supply(
            topics_path=args.topics,
            social_manifest=args.social_manifest,
            syndication_manifest=args.syndication_manifest,
            project_root=args.project_root,
            minimum_score=args.minimum_score,
        )
    except (DistributionSupplyError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"distribution supply check failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
