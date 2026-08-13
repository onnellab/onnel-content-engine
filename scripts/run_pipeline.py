#!/usr/bin/env python3
"""Run the validated publishing pipeline with an optional dry-run mode."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

from approve_due_distribution import approve_due_distribution
from check_distribution_supply import require_distribution_supply
from create_github_releases import create_github_releases
from generate_all_image_specs import generate_all_image_specs
from generate_all_image_assets import generate_all_image_assets
from generate_all_internal_links import generate_all_internal_links
from generate_all_markdown import generate_all_markdown
from generate_syndication_drafts import generate_syndication_drafts
from evaluate_social_templates import evaluate_social_templates
from evaluate_syndication_drafts import evaluate_syndication_drafts
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
    run_command([sys.executable, "scripts/validate_topics.py"])
    run_command([sys.executable, "scripts/validate_apps_registry.py"])
    run_command([sys.executable, "scripts/validate_app_releases.py"])
    run_command([sys.executable, "scripts/validate_foundation.py"])


def published_social_gate_manifest(manifest_path: Path) -> Path:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    posts = payload.get("posts")
    if not isinstance(posts, list):
        raise PipelineError(f"social manifest has no posts: {manifest_path}")
    published_posts = [
        post
        for post in posts
        if isinstance(post, dict)
        and post.get("source_status", "published") == "published"
        and not post.get("is_variant")
        and post.get("status") != "posted"
    ]
    return write_social_gate_manifest(manifest_path, published_posts, "actionable")


def published_social_coverage_manifest(manifest_path: Path) -> Path:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    posts = payload.get("posts")
    if not isinstance(posts, list):
        raise PipelineError(f"social manifest has no posts: {manifest_path}")
    published_posts = [
        post
        for post in posts
        if isinstance(post, dict)
        and post.get("source_status", "published") == "published"
        and not post.get("is_variant")
    ]
    return write_social_gate_manifest(manifest_path, published_posts, "coverage")


def write_social_gate_manifest(manifest_path: Path, posts: list[dict[str, object]], purpose: str) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".published-social-{purpose}-",
        suffix=".json",
        dir=manifest_path.parent,
        delete=False,
    ) as handle:
        json.dump({"posts": posts}, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        return Path(handle.name)


def evaluate_actionable_social(manifest_path: Path, project_root: Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not payload.get("posts"):
        return {"average_score": 10.0, "repetition_warnings": [], "posts": []}
    return evaluate_social_templates(manifest_path, project_root)


def syndication_gate_manifest(manifest_path: Path, actionable_only: bool) -> Path:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    drafts = payload.get("drafts")
    if not isinstance(drafts, list):
        raise PipelineError(f"syndication manifest has no drafts: {manifest_path}")
    selected = [
        draft
        for draft in drafts
        if isinstance(draft, dict)
        and draft.get("source_status", "published") == "published"
        and (not actionable_only or draft.get("status") != "posted")
    ]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".published-syndication-{'actionable' if actionable_only else 'coverage'}-",
        suffix=".json",
        dir=manifest_path.parent,
        delete=False,
    ) as handle:
        json.dump({"drafts": selected}, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        return Path(handle.name)


def evaluate_actionable_syndication(manifest_path: Path, project_root: Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not payload.get("drafts"):
        return {"average_score": 10.0, "drafts": []}
    return evaluate_syndication_drafts(manifest_path, project_root)


def quality_gate(social_manifest: Path, syndication_manifest: Path, minimum_score: float = 9.5) -> None:
    social_project_root = social_manifest.resolve().parents[2]
    syndication_project_root = syndication_manifest.resolve().parents[2]
    if social_project_root != syndication_project_root:
        raise PipelineError("quality manifests must belong to the same project root")
    with ExitStack() as cleanup:
        gate_manifest = published_social_gate_manifest(social_manifest)
        cleanup.callback(gate_manifest.unlink, missing_ok=True)
        syndication_gate_manifest_path = syndication_gate_manifest(syndication_manifest, actionable_only=True)
        cleanup.callback(syndication_gate_manifest_path.unlink, missing_ok=True)
        social = evaluate_actionable_social(gate_manifest, social_project_root)
        syndication = evaluate_actionable_syndication(syndication_gate_manifest_path, syndication_project_root)
    social_score = float(social["average_score"])
    syndication_score = float(syndication["average_score"])
    warnings = social.get("repetition_warnings") or []
    if social_score < minimum_score:
        raise PipelineError(f"social template score {social_score}/10 is below {minimum_score}/10")
    if syndication_score < minimum_score:
        raise PipelineError(f"syndication score {syndication_score}/10 is below {minimum_score}/10")
    if warnings:
        phrases = ", ".join(f"{item['phrase']} ({item['count']})" for item in warnings if isinstance(item, dict))
        raise PipelineError(f"social repetition warnings: {phrases}")


def distribution_gate(topics_path: Path, social_manifest: Path, syndication_manifest: Path) -> None:
    with ExitStack() as cleanup:
        coverage_manifest = published_social_coverage_manifest(social_manifest)
        cleanup.callback(coverage_manifest.unlink, missing_ok=True)
        actionable_manifest = published_social_gate_manifest(social_manifest)
        cleanup.callback(actionable_manifest.unlink, missing_ok=True)
        syndication_coverage_manifest = syndication_gate_manifest(syndication_manifest, actionable_only=False)
        cleanup.callback(syndication_coverage_manifest.unlink, missing_ok=True)
        syndication_actionable_manifest = syndication_gate_manifest(syndication_manifest, actionable_only=True)
        cleanup.callback(syndication_actionable_manifest.unlink, missing_ok=True)
        try:
            require_distribution_supply(
                topics_path=topics_path,
                social_manifest=coverage_manifest,
                syndication_manifest=syndication_coverage_manifest,
                project_root=topics_path.resolve().parent.parent,
                minimum_score=0.0,
            )
            social = evaluate_actionable_social(actionable_manifest, topics_path.resolve().parent.parent)
            syndication = evaluate_actionable_syndication(
                syndication_actionable_manifest, topics_path.resolve().parent.parent
            )
            low_social = [
                item for item in social.get("posts", [])
                if isinstance(item, dict) and float(item.get("score", 0.0)) < 9.5
            ]
            low_syndication = [
                item for item in syndication.get("drafts", [])
                if isinstance(item, dict) and float(item.get("score", 0.0)) < 9.5
            ]
            if float(social["average_score"]) < 9.5 or low_social:
                raise PipelineError("actionable social distribution quality is below 9.5/10")
            if float(syndication["average_score"]) < 9.5 or low_syndication:
                raise PipelineError("syndication distribution quality is below 9.5/10")
            if social.get("repetition_warnings"):
                raise PipelineError("actionable social distribution has repetition warnings")
        except ValueError as error:
            raise PipelineError(str(error)) from error


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
            releases_path = temp_root / "data" / "app_releases.csv"
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
            create_github_releases(releases_path, dry_run=True)
            generate_all_markdown(topics_path, apps_path, markdown_root, legacy_topics_path)
            generate_all_image_specs(topics_path, apps_path, images_root, legacy_topics_path)
            generate_all_image_assets(topics_path, images_root, assets_root, legacy_topics_path)
            generate_all_internal_links(topics_path, apps_path, metadata_root)
            evaluate_all_articles(topics_path, metadata_root, assets_root, review_root)
            schedule_ready_articles(topics_path, review_root, legacy_topics_path)
            publish_due_articles(topics_path, review_root, legacy_topics_path, site_url=site_url)
            build_site(topics_path, html_root, site_url)
            generate_social_posts(topics_path, social_root, site_url, include_prepublication=True)
            generate_syndication_drafts(
                topics_path, syndication_root, site_url, include_prepublication=True
            )
            quality_gate(social_root / "manifest.json", syndication_root / "manifest.json")
            distribution_gate(topics_path, social_root / "manifest.json", syndication_root / "manifest.json")
            approve_due_distribution(topics_path, social_root / "manifest.json", syndication_root / "manifest.json", dry_run=True)
            deploy_github_pages(topics_path=topics_path, homepage_repo=homepage_repo, dry_run=True)
        return

    create_github_releases()
    generate_all_markdown()
    generate_all_image_specs()
    generate_all_image_assets()
    generate_all_internal_links()
    evaluate_all_articles()
    schedule_ready_articles(require_ready_when_due=True)
    publish_due_articles(site_url=site_url)
    build_site(site_url=site_url)
    generate_social_posts(site_url=site_url, include_prepublication=True)
    generate_syndication_drafts(site_url=site_url, include_prepublication=True)
    quality_gate(ROOT / "generated" / "social" / "manifest.json", ROOT / "generated" / "syndication" / "manifest.json")
    distribution_gate(
        ROOT / "data" / "topics.csv",
        ROOT / "generated" / "social" / "manifest.json",
        ROOT / "generated" / "syndication" / "manifest.json",
    )
    approve_due_distribution()
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
