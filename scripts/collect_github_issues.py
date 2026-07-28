#!/usr/bin/env python3
"""Collect privacy-minimized GitHub issue metadata from configured app repositories."""
from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG_PATH = DATA / "github_issue_monitor_config.json"
REPOSITORIES_PATH = DATA / "app_release_config.csv"
OUTPUT_PATH = DATA / "github_issues.json"
STATUS_PATH = DATA / "github_issue_sync_status.json"
API = "https://api.github.com"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def configured_repositories(config: dict) -> list[dict[str, str]]:
    selected = {str(item).strip() for item in config.get("repositories", []) if str(item).strip()}
    with REPOSITORIES_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    repositories = [
        {"app_slug": row["app_slug"], "repository": row["repository"]}
        for row in rows
        if not selected or row["repository"] in selected
    ]
    if selected - {item["repository"] for item in repositories}:
        raise ValueError("GitHub issue monitor contains an unknown app repository")
    return repositories


def request_page(url: str, token: str, opener=None) -> tuple[list[dict], str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ONNELLAB-AI-Scout/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with (opener or urllib.request.urlopen)(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
        link = str(response.headers.get("Link", ""))
    if not isinstance(payload, list):
        raise ValueError("GitHub issues response must be a list")
    next_url = ""
    for part in link.split(","):
        if 'rel="next"' in part:
            next_url = part.split(";", 1)[0].strip().strip("<>")
    return payload, next_url


def fetch_open_issues(repository: str, token: str, opener=None) -> list[dict]:
    owner_repo = urllib.parse.quote(repository, safe="/")
    url = f"{API}/repos/{owner_repo}/issues?state=open&per_page=100&sort=updated&direction=desc"
    issues: list[dict] = []
    seen_urls: set[str] = set()
    while url:
        if url in seen_urls:
            raise ValueError("GitHub issue pagination repeated a URL")
        seen_urls.add(url)
        page, url = request_page(url, token, opener)
        issues.extend(item for item in page if isinstance(item, dict) and "pull_request" not in item)
    return issues


def collect(config: dict, existing: list[dict], token: str, *, checked_at: str, opener=None) -> list[dict]:
    index = {item.get("issue_id"): item for item in existing if isinstance(item, dict)}
    monitored_repositories = configured_repositories(config)
    seen: set[str] = set()
    for source in monitored_repositories:
        for issue in fetch_open_issues(source["repository"], token, opener):
            number = issue.get("number")
            if not isinstance(number, int) or number < 1:
                continue
            issue_id = f"github:{source['repository']}#{number}"
            seen.add(issue_id)
            previous = index.get(issue_id, {})
            labels = sorted(
                {
                    str(item.get("name", "")).strip()
                    for item in issue.get("labels", [])
                    if isinstance(item, dict) and str(item.get("name", "")).strip()
                }
            )
            index[issue_id] = {
                "issue_id": issue_id,
                "app_slug": source["app_slug"],
                "repository": source["repository"],
                "number": number,
                "title": str(issue.get("title", "")).strip()[:300],
                "labels": labels,
                "url": str(issue.get("html_url", "")).strip(),
                "status": "open",
                "github_created_at": str(issue.get("created_at", "")).strip(),
                "github_updated_at": str(issue.get("updated_at", "")).strip(),
                "first_seen_at": previous.get("first_seen_at", checked_at),
                "last_seen_at": checked_at,
                "closed_observed_at": "",
            }
    monitored = {item["repository"] for item in monitored_repositories}
    for issue_id, item in index.items():
        if item.get("repository") in monitored and issue_id not in seen and item.get("status") == "open":
            item["status"] = "closed"
            item["closed_observed_at"] = checked_at
    return sorted(index.values(), key=lambda item: (item.get("repository", ""), int(item.get("number", 0))))


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("enabled"):
        STATUS_PATH.write_text(
            json.dumps({"checked_at": now_iso(), "state": "disabled", "open_issues": 0}, indent=2) + "\n",
            encoding="utf-8",
        )
        print("GitHub issue monitor is disabled")
        return 0
    existing_payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.exists() else {"issues": []}
    existing = existing_payload.get("issues")
    if not isinstance(existing, list):
        raise SystemExit("GitHub issue audit has invalid shape")
    checked_at = now_iso()
    try:
        issues = collect(config, existing, os.environ.get("GITHUB_TOKEN", ""), checked_at=checked_at)
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise SystemExit(f"GitHub issue collection failed: {error}") from error
    OUTPUT_PATH.write_text(json.dumps({"issues": issues}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = {
        "checked_at": checked_at,
        "state": "collected",
        "repositories": len(configured_repositories(config)),
        "open_issues": sum(item.get("status") == "open" for item in issues),
    }
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"collected {status['open_issues']} open GitHub issue(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
