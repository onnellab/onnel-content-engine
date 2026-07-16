#!/usr/bin/env python3
"""Reduce repeated phrases in generated social drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from evaluate_social_templates import REPETITION_PATTERNS
from publishing import x_weighted_length
from validate_social_posts import DEFAULT_MANIFEST_PATH, ROOT, SocialValidationError, validate_social_posts


REPLACEMENTS = {
    "workflow problem": ["planning issue", "handling issue", "process issue"],
    "plain-text file": ["text document", "TXT document", "text export"],
    "large txt file": ["large text export", "big TXT document", "long text file"],
    "slow text file": ["laggy text document", "slow TXT document", "heavy text export"],
    "tool choice": ["setup decision", "processing choice", "app decision"],
    "opens, renders, and searches": ["loads, displays, and searches", "reads, lays out, and searches"],
}


class RepetitionReductionError(ValueError):
    """Raised when social repetition cannot be reduced."""


def replace_case_insensitive(text: str, phrase: str, replacement: str) -> tuple[str, int]:
    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
    return pattern.subn(replacement, text)


def reduce_social_repetition(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    project_root: Path = ROOT,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    validate_social_posts(manifest_path, project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    posts = manifest.get("posts")
    if not isinstance(posts, list):
        raise RepetitionReductionError("social manifest has no posts list")

    changes: list[dict[str, object]] = []
    replacement_index = {phrase: 0 for phrase in REPETITION_PATTERNS}
    for post in posts:
        if not isinstance(post, dict) or post.get("status") == "posted":
            continue
        draft_path = project_root / str(post.get("draft_path", ""))
        if not draft_path.exists():
            continue
        original = draft_path.read_text(encoding="utf-8")
        updated = original
        applied: list[str] = []
        for phrase in REPETITION_PATTERNS:
            if phrase.lower() not in updated.lower():
                continue
            options = REPLACEMENTS.get(phrase, [])
            if not options:
                continue
            replacement = options[replacement_index[phrase] % len(options)]
            replacement_index[phrase] += 1
            updated, count = replace_case_insensitive(updated, phrase, replacement)
            if count:
                applied.append(f"{phrase} -> {replacement}")
        if updated == original:
            continue
        changes.append(
            {
                "topic_id": post.get("topic_id", ""),
                "platform": post.get("platform", ""),
                "language": post.get("language", ""),
                "template_id": post.get("template_id", ""),
                "draft_path": str(post.get("draft_path", "")),
                "replacements": applied,
            }
        )
        if dry_run:
            continue
        draft_path.write_text(updated, encoding="utf-8")
        post["weighted_length"] = x_weighted_length(updated) if post.get("platform") == "x" else len(updated)

    if changes and not dry_run:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Reduce repeated phrases in generated social drafts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        changes = reduce_social_repetition(args.manifest, args.project_root, args.dry_run)
    except (RepetitionReductionError, SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social repetition reduction failed: {error}", file=sys.stderr)
        return 1
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {len(changes)} social draft(s)")
    for change in changes:
        print(
            f"- {change['topic_id']} {change['platform']} {change['language']} "
            f"{change['template_id']}: {change['draft_path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
