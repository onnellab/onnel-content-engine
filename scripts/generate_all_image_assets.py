#!/usr/bin/env python3
"""Generate publish-ready SVG assets for every image-planned article."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generate_image_assets import DEFAULT_ASSETS_ROOT, DEFAULT_IMAGES_ROOT, ImageAssetError, generate_image_asset
from topic_management import DEFAULT_TOPICS_PATH, LEGACY_TOPICS_PATH, TOPIC_HEADER, TopicError, read_csv


ASSET_GENERATION_STATUSES = {"image_planning", "review", "scheduled", "published", "update_required"}


def image_planning_spec_paths(topics_path: Path, images_root: Path) -> list[Path]:
    paths: list[Path] = []
    for row in read_csv(topics_path, TOPIC_HEADER):
        if row["status"] in ASSET_GENERATION_STATUSES:
            path = images_root / row["primary_language"] / row["category"] / row["slug"] / "image_spec.json"
            if path.exists():
                paths.append(path)
    return paths


def generate_all_image_assets(
    topics_path: Path = DEFAULT_TOPICS_PATH,
    images_root: Path = DEFAULT_IMAGES_ROOT,
    assets_root: Path = DEFAULT_ASSETS_ROOT,
    legacy_topics_path: Path | None = LEGACY_TOPICS_PATH,
    advance_to_review: bool = True,
) -> list[Path]:
    paths: list[Path] = []
    for spec_path in image_planning_spec_paths(topics_path, images_root):
        paths.append(
            generate_image_asset(
                spec_path,
                topics_path=topics_path,
                images_root=images_root,
                assets_root=assets_root,
                legacy_topics_path=legacy_topics_path,
                advance_to_review=advance_to_review,
            )
        )
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate publish-ready SVG assets for image-planned topics")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--legacy-topics", type=Path, default=LEGACY_TOPICS_PATH)
    parser.add_argument("--no-advance", action="store_true", help="Do not advance image_planning topics to review")
    args = parser.parse_args()
    try:
        paths = generate_all_image_assets(
            args.topics,
            args.images_root,
            args.assets_root,
            args.legacy_topics,
            advance_to_review=not args.no_advance,
        )
    except (ImageAssetError, TopicError, OSError) as error:
        print(f"generate all image assets failed: {error}", file=sys.stderr)
        return 1
    print(f"generated {len(paths)} image asset file(s)")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
