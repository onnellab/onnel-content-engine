#!/usr/bin/env python3
"""Evaluate generated long-form syndication drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "generated" / "syndication" / "manifest.json"


class SyndicationEvaluationError(ValueError):
    """Raised when syndication drafts cannot be evaluated."""


def frontmatter(content: str) -> dict[str, str]:
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}
    metadata: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def score_draft(draft: dict[str, object], project_root: Path = ROOT) -> dict[str, object]:
    platform = str(draft["platform"])
    path = project_root / str(draft["draft_path"])
    canonical_url = str(draft["canonical_url"])
    if not path.exists():
        raise SyndicationEvaluationError(f"syndication draft does not exist: {path}")
    content = path.read_text(encoding="utf-8")
    metadata = frontmatter(content)
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, points: float) -> None:
        checks.append({"name": name, "passed": passed, "points": points if passed else 0.0, "max_points": points})

    add("canonical_frontmatter", platform == "medium" or metadata.get("canonical_url") == canonical_url, 1.5)
    add("canonical_notice", f"Originally published at {canonical_url}" in content, 1.5)
    add("body_preserved", bool(re.search(r"^#\s+", content, re.MULTILINE)), 1.0)
    add("distribution_status", draft.get("status") in {"draft", "approved", "posted"}, 0.8)
    add("platform_supported", platform in {"devto", "hashnode", "medium"}, 0.7)
    if platform == "devto":
        tags = metadata.get("tags", "")
        add("devto_public", metadata.get("published") == "true", 1.0)
        add("devto_tags", bool(tags) and len(tags.split(",")) <= 4 and " " not in tags, 1.0)
    if platform == "hashnode":
        add("hashnode_tags", bool(metadata.get("tags")), 0.8)
        add("hashnode_cover_image", metadata.get("cover_image", "").endswith("/social-card.png"), 1.2)
        add("hashnode_publication_placeholder", "publication_id" in metadata, 0.8)
    if platform == "medium":
        add("medium_export_only", draft.get("status") in {"draft", "approved", "posted"}, 1.0)
        add("medium_no_api_claim", "published:" not in content, 0.8)
    total = round(sum(float(check["points"]) for check in checks), 2)
    maximum = round(sum(float(check["max_points"]) for check in checks), 2)
    return {
        "topic_id": draft["topic_id"],
        "platform": platform,
        "language": draft["language"],
        "score": round(total / maximum * 10, 2) if maximum else 0.0,
        "checks": checks,
    }


def evaluate_syndication_drafts(manifest_path: Path = DEFAULT_MANIFEST_PATH, project_root: Path = ROOT) -> dict[str, object]:
    if not manifest_path.exists():
        raise SyndicationEvaluationError(f"syndication manifest does not exist: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drafts = manifest.get("drafts")
    if not isinstance(drafts, list) or not drafts:
        raise SyndicationEvaluationError("syndication manifest has no drafts")
    evaluations = [score_draft(draft, project_root) for draft in drafts if isinstance(draft, dict)]
    average = round(sum(float(item["score"]) for item in evaluations) / len(evaluations), 2)
    return {"type": "syndication_evaluation", "average_score": average, "drafts": evaluations}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate generated syndication drafts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_syndication_drafts(args.manifest)
    except (SyndicationEvaluationError, OSError, json.JSONDecodeError) as error:
        print(f"syndication evaluation failed: {error}", file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(f"syndication average score: {result['average_score']}/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
