#!/usr/bin/env python3
"""Print a dry-run report for generated syndication drafts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from evaluate_syndication_drafts import DEFAULT_MANIFEST_PATH
from validate_syndication_drafts import SyndicationValidationError, project_root_for_manifest, validate_syndication_drafts


def syndication_report(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> str:
    validate_syndication_drafts(manifest_path, project_root_for_manifest(manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drafts = [draft for draft in manifest["drafts"] if isinstance(draft, dict)]
    counts = Counter(str(draft["status"]) for draft in drafts)
    lines = [
        "Syndication dry-run report",
        "",
        f"total: {len(drafts)}",
        f"approved: {counts.get('approved', 0)}",
        f"draft: {counts.get('draft', 0)}",
        f"posted: {counts.get('posted', 0)}",
        f"failed: {counts.get('failed', 0)}",
        "",
        "Posting readiness:",
    ]
    for draft in drafts:
        reasons: list[str] = []
        if draft.get("platform") == "medium":
            reasons.append("Medium export-only")
        if draft.get("status") != "approved":
            reasons.append(f"status={draft.get('status')}")
        if draft.get("status") == "posted":
            reasons.append("already posted")
        if draft.get("platform") in {"devto", "hashnode"}:
            reasons.append("real API token required for non-mock adapter")
        ready = draft.get("status") == "approved" and draft.get("platform") != "medium"
        lines.append(
            f"- {'ready for mock posting' if ready else 'not ready'}: "
            f"{draft['topic_id']} {draft['platform']} {draft['language']} "
            f"({'; '.join(reasons) if reasons else 'approved'})"
        )
    lines.extend(["", "Approved drafts:"])
    approved = [draft for draft in drafts if draft.get("status") == "approved"]
    if not approved:
        lines.append("- none")
    for draft in approved:
        lines.append(f"- {draft['topic_id']} {draft['platform']} {draft['language']} {draft['draft_path']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a dry-run syndication report")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()
    try:
        print(syndication_report(args.manifest))
    except (SyndicationValidationError, OSError, json.JSONDecodeError) as error:
        print(f"syndication report failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
