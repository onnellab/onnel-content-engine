#!/usr/bin/env python3
"""Sync app release attention report to one GitHub Issue."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from generate_app_release_report import REPORT_PATH


GITHUB_API = "https://api.github.com"
USER_AGENT = "ONNELLAB content engine"
DEFAULT_TITLE = "ONNELLAB App Release Attention Queue"
ATTENTION_CLEAR_TEXT = "No release automation items need attention."


class AppReleaseIssueError(ValueError):
    """Raised when the app release attention issue cannot be synced."""


def github_token(dry_run: bool = False) -> str:
    if dry_run:
        return "dry-run-token"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("ONNELLAB_RELEASE_TOKEN")
    if not token:
        raise AppReleaseIssueError("GITHUB_TOKEN or ONNELLAB_RELEASE_TOKEN is required")
    return token


def repository_arg(value: str | None) -> str:
    repository = value or os.environ.get("GITHUB_REPOSITORY") or "onnelakin/onnel-content-engine"
    if "/" not in repository:
        raise AppReleaseIssueError("repository must use owner/name format")
    return repository


def github_request(path: str, token: str, method: str = "GET", payload: dict[str, object] | None = None) -> object:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{GITHUB_API}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status == 204:
                return {}
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AppReleaseIssueError(f"HTTP {error.code} from {path}: {detail}") from error


def has_attention(report: str) -> bool:
    return ATTENTION_CLEAR_TEXT not in report


def issue_body(report: str) -> str:
    return "\n".join(
        [
            "<!-- onnel-content-engine:app-release-attention -->",
            "This issue is automatically updated from `generated/reports/app_releases.md`.",
            "",
            report.strip(),
            "",
        ]
    )


def find_issue(repository: str, title: str, token: str) -> dict[str, object] | None:
    query = urllib.parse.urlencode({"state": "all", "per_page": "100"})
    result = github_request(f"/repos/{repository}/issues?{query}", token)
    if not isinstance(result, list):
        raise AppReleaseIssueError("GitHub issues response was not a list")
    for issue in result:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        if issue.get("title") == title:
            return issue
    return None


def sync_app_release_issue(
    report_path: Path = REPORT_PATH,
    repository: str | None = None,
    title: str = DEFAULT_TITLE,
    dry_run: bool = False,
) -> str:
    report = report_path.read_text(encoding="utf-8")
    repo = repository_arg(repository)
    attention = has_attention(report)
    token = github_token(dry_run)
    if dry_run:
        state = "open/update" if attention else "close if open"
        return f"would sync {repo} issue '{title}' with action: {state}"

    issue = find_issue(repo, title, token)
    if attention:
        payload = {"title": title, "body": issue_body(report), "state": "open"}
        if issue:
            number = issue.get("number")
            if not isinstance(number, int):
                raise AppReleaseIssueError("existing issue did not include an issue number")
            github_request(f"/repos/{repo}/issues/{number}", token, "PATCH", payload)
            return f"updated {repo} issue #{number}"
        created = github_request(f"/repos/{repo}/issues", token, "POST", payload)
        if not isinstance(created, dict) or not isinstance(created.get("number"), int):
            raise AppReleaseIssueError("created issue response did not include an issue number")
        return f"created {repo} issue #{created['number']}"

    if issue and issue.get("state") == "open":
        number = issue.get("number")
        if not isinstance(number, int):
            raise AppReleaseIssueError("existing issue did not include an issue number")
        github_request(f"/repos/{repo}/issues/{number}", token, "PATCH", {"state": "closed"})
        return f"closed {repo} issue #{number}"
    return f"no attention items for {repo}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync app release attention report to a GitHub Issue")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--repository")
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        message = sync_app_release_issue(args.report, args.repository, args.title, args.dry_run)
    except (AppReleaseIssueError, OSError, json.JSONDecodeError) as error:
        print(f"sync app release issue failed: {error}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
