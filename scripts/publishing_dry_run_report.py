#!/usr/bin/env python3
"""Print one dry-run report for all publishing destinations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from approve_social_post import project_root_for_manifest as social_root_for_manifest
from check_publishing_credentials import credential_status
from evaluate_syndication_drafts import DEFAULT_MANIFEST_PATH as DEFAULT_SYNDICATION_MANIFEST_PATH
from post_social_drafts import bluesky_external_card_metadata, x_payload
from post_syndication_drafts import devto_payload, hashnode_payload
from validate_social_posts import DEFAULT_MANIFEST_PATH as DEFAULT_SOCIAL_MANIFEST_PATH
from validate_social_posts import SocialValidationError, validate_social_posts
from validate_syndication_drafts import SyndicationValidationError
from validate_syndication_drafts import project_root_for_manifest as syndication_root_for_manifest
from validate_syndication_drafts import validate_syndication_drafts


SOCIAL_ADAPTERS = {"x": "x", "bluesky": "bluesky", "linkedin": "linkedin"}
SYNDICATION_ADAPTERS = {"devto": "devto", "hashnode": "hashnode", "medium": "medium"}


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def payload_summary(kind: str, item: dict[str, object], project_root: Path) -> str:
    try:
        if kind == "social":
            platform = str(item["platform"])
            if platform == "x":
                payload = x_payload(item, project_root)
                return f"text_length={len(str(payload['text']))}"
            if platform == "bluesky":
                card = bluesky_external_card_metadata(item, project_root)
                return f"text_length={item['weighted_length']} card={card['thumb_path']}"
            if platform == "linkedin":
                return f"manual_text={item['draft_path']} card={item['card_asset_path']}"
        if kind == "syndication":
            platform = str(item["platform"])
            if platform == "devto":
                article = devto_payload(item, project_root)["article"]
                return f"published={article['published']} tags={article['tags']}"
            if platform == "hashnode":
                input_payload = hashnode_payload(item, project_root)["variables"]["input"]
                return f"publication={input_payload['publicationId']} tags={len(input_payload['tags'])}"
            if platform == "medium":
                return "export_only=true"
        return "payload=unavailable"
    except Exception as error:
        return f"payload_error={error}"


def credential_line(adapter: str, live: bool) -> str:
    status = credential_status(adapter, live)
    if status["ready"]:
        value = "ready"
    else:
        value = "not ready"
    if status["live_checked"]:
        value += ", live ok" if status["live_ok"] else ", live failed"
    missing = f", missing={','.join(status['missing'])}" if status["missing"] else ""
    identity = f", identity={status['identity']}" if status["identity"] else ""
    return f"{adapter}: {value}{missing}{identity}"


def publishing_dry_run_report(
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST_PATH,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST_PATH,
    live_credentials: bool = False,
) -> str:
    social_root = social_root_for_manifest(social_manifest)
    syndication_root = syndication_root_for_manifest(syndication_manifest)
    validate_social_posts(social_manifest, social_root)
    validate_syndication_drafts(syndication_manifest, syndication_root)
    social_posts = [post for post in load_json(social_manifest)["posts"] if isinstance(post, dict)]
    syndication_drafts = [draft for draft in load_json(syndication_manifest)["drafts"] if isinstance(draft, dict)]
    approved_social = [post for post in social_posts if post.get("status") == "approved"]
    approved_syndication = [
        draft
        for draft in syndication_drafts
        if draft.get("status") == "approved" and draft.get("platform") != "medium"
    ]
    adapters = sorted(
        {
            SOCIAL_ADAPTERS[str(post["platform"])]
            for post in approved_social
        }
        | {
            SYNDICATION_ADAPTERS[str(draft["platform"])]
            for draft in approved_syndication
        }
    )
    lines = [
        "Publishing dry-run report",
        "",
        f"approved social posts: {len(approved_social)}",
        f"approved syndication drafts: {len(approved_syndication)}",
        "",
        "Credential status:",
    ]
    if adapters:
        for adapter in adapters:
            lines.append(f"- {credential_line(adapter, live_credentials)}")
    else:
        lines.append("- none required")
    lines.extend(["", "Approved social payloads:"])
    if not approved_social:
        lines.append("- none")
    for post in approved_social:
        lines.append(
            f"- {post['topic_id']} {post['platform']} {post['language']} {post['template_id']}: "
            f"{payload_summary('social', post, social_root)} url={post['canonical_url']}"
        )
    lines.extend(["", "Approved syndication payloads:"])
    if not approved_syndication:
        lines.append("- none")
    for draft in approved_syndication:
        lines.append(
            f"- {draft['topic_id']} {draft['platform']} {draft['language']}: "
            f"{payload_summary('syndication', draft, syndication_root)} url={draft['canonical_url']}"
        )
    lines.extend(["", "Blocked or non-posting statuses:"])
    blocked = [
        f"{post['topic_id']} {post['platform']} {post['language']} status={post['status']}"
        + (f" error_type={post['error_type']}" if post.get("error_type") else "")
        for post in social_posts
        if post.get("status") in {"failed", "posted"}
    ] + [
        f"{draft['topic_id']} {draft['platform']} {draft['language']} status={draft['status']}"
        + (f" error_type={draft['error_type']}" if draft.get("error_type") else "")
        for draft in syndication_drafts
        if draft.get("status") in {"failed", "posted"} or draft.get("platform") == "medium"
    ]
    if not blocked:
        lines.append("- none")
    for item in blocked:
        lines.append(f"- {item}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print one dry-run report for all publishing destinations")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST_PATH)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST_PATH)
    parser.add_argument("--live-credentials", action="store_true")
    args = parser.parse_args()
    try:
        print(publishing_dry_run_report(args.social_manifest, args.syndication_manifest, args.live_credentials))
    except (SocialValidationError, SyndicationValidationError, OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"publishing dry-run report failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
