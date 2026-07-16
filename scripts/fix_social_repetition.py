#!/usr/bin/env python3
"""Fix social repeated phrase warnings and rebuild the manual publish site."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_manual_publish_site import (
    DEFAULT_OUTPUT,
    DEFAULT_SYNDICATION_MANIFEST,
    build_manual_publish_site,
)
from evaluate_social_templates import evaluate_social_templates
from reduce_social_repetition import RepetitionReductionError, reduce_social_repetition
from validate_social_posts import DEFAULT_MANIFEST_PATH, ROOT, SocialValidationError


def fix_social_repetition(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    syndication_manifest_path: Path = DEFAULT_SYNDICATION_MANIFEST,
    project_root: Path = ROOT,
    output: Path = DEFAULT_OUTPUT,
    dry_run: bool = False,
    rebuild_dashboard: bool = True,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    changes = reduce_social_repetition(manifest_path, project_root, dry_run=dry_run)
    evaluation = evaluate_social_templates(manifest_path, project_root)
    warnings = [item for item in evaluation.get("repetition_warnings", []) if isinstance(item, dict)]
    if rebuild_dashboard and not dry_run:
        build_manual_publish_site(
            social_manifest=manifest_path,
            syndication_manifest=syndication_manifest_path,
            output=output,
        )
    return changes, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix social repetition warnings and recheck them")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-dashboard", action="store_true")
    args = parser.parse_args()
    try:
        changes, warnings = fix_social_repetition(
            args.manifest,
            args.syndication_manifest,
            args.project_root,
            args.output,
            dry_run=args.dry_run,
            rebuild_dashboard=not args.skip_dashboard,
        )
    except (RepetitionReductionError, SocialValidationError, OSError, json.JSONDecodeError) as error:
        print(f"social repetition fix failed: {error}", file=sys.stderr)
        return 1

    action = "would update" if args.dry_run else "updated"
    print(f"{action} {len(changes)} social draft(s)")
    if not args.dry_run and not args.skip_dashboard:
        print(f"rebuilt {args.output}")
    if warnings:
        phrases = ", ".join(f"{item.get('phrase')} ({item.get('count')})" for item in warnings)
        print(f"remaining social repetition warnings: {phrases}", file=sys.stderr)
        return 1
    print("social repetition warnings: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
