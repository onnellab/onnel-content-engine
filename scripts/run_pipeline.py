#!/usr/bin/env python3
"""Run the validated publishing pipeline with an optional dry-run mode."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from generate_all_image_specs import generate_all_image_specs
from generate_all_image_assets import generate_all_image_assets
from generate_all_internal_links import generate_all_internal_links
from generate_all_markdown import generate_all_markdown
from generate_syndication_drafts import generate_syndication_drafts
from evaluate_all_articles import evaluate_all_articles
from publishing import DEFAULT_HOMEPAGE_REPOSITORY_PATH, DEFAULT_SITE_URL, build_site, deploy_github_pages, generate_social_posts
from publish_due_articles import publish_due_articles
from schedule_ready_articles import schedule_ready_articles


ROOT = Path(__file__).resolve().parents[1]


class PipelineError(RuntimeError):
    """Raised when a pipeline stage fails."""


def run_command(command: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def validate() -> None:
    run_command(["scripts/validate_topics.py"])
    run_command(["scripts/validate_apps_registry.py"])
    run_command(["scripts/validate_foundation.py"])


def copy_for_dry_run(destination: Path) -> None:
    for name in ["data", "topics", "templates", "generated"]:
        source = ROOT / name
        target = destination / name
        if source.exists():
            shutil.copytree(source, target)


def run_pipeline(
    dry_run: bool = False,
    deploy: bool = False,
    site_url: str = DEFAULT_SITE_URL,
    homepage_repo: Path = DEFAULT_HOMEPAGE_REPOSITORY_PATH,
) -> None:
    validate()
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="onnel-content-engine-dry-run-") as temp_dir:
            temp_root = Path(temp_dir)
            copy_for_dry_run(temp_root)
            topics_path = temp_root / "data" / "topics.csv"
            apps_path = temp_root / "data" / "apps_registry.csv"
            legacy_topics_path = temp_root / "topics" / "topics.csv"
            markdown_root = temp_root / "generated" / "markdown"
            images_root = temp_root / "generated" / "images"
            assets_root = temp_root / "generated" / "assets" / "blog"
            metadata_root = temp_root / "generated" / "metadata"
            review_root = temp_root / "generated" / "reviews"
            html_root = temp_root / "generated" / "html"
            social_root = temp_root / "generated" / "social"
            syndication_root = temp_root / "generated" / "syndication"
            generate_all_markdown(topics_path, apps_path, markdown_root, legacy_topics_path)
            generate_all_image_specs(topics_path, apps_path, images_root, legacy_topics_path)
            generate_all_image_assets(topics_path, images_root, assets_root, legacy_topics_path)
            generate_all_internal_links(topics_path, apps_path, metadata_root)
            evaluate_all_articles(topics_path, metadata_root, assets_root, review_root)
            schedule_ready_articles(topics_path, review_root, legacy_topics_path)
            publish_due_articles(topics_path, review_root, legacy_topics_path, site_url=site_url)
            build_site(topics_path, html_root, site_url)
            generate_social_posts(topics_path, social_root, site_url)
            generate_syndication_drafts(topics_path, syndication_root, site_url)
            deploy_github_pages(topics_path=topics_path, homepage_repo=homepage_repo, dry_run=True)
        return

    generate_all_markdown()
    generate_all_image_specs()
    generate_all_image_assets()
    generate_all_internal_links()
    evaluate_all_articles()
    schedule_ready_articles()
    publish_due_articles(site_url=site_url)
    build_site(site_url=site_url)
    generate_social_posts(site_url=site_url)
    generate_syndication_drafts(site_url=site_url)
    if deploy:
        deploy_github_pages(homepage_repo=homepage_repo)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ONNELLAB publishing pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run in a temporary copy without changing repository outputs")
    parser.add_argument("--deploy", action="store_true", help="Deploy after build. Ignored during dry-run.")
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument("--homepage-repo", type=Path, default=DEFAULT_HOMEPAGE_REPOSITORY_PATH)
    args = parser.parse_args()
    try:
        run_pipeline(
            dry_run=args.dry_run,
            deploy=args.deploy and not args.dry_run,
            site_url=args.site_url,
            homepage_repo=args.homepage_repo,
        )
    except (OSError, PipelineError, subprocess.CalledProcessError, ValueError) as error:
        print(f"pipeline failed: {error}", file=sys.stderr)
        return 1
    print("pipeline completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
