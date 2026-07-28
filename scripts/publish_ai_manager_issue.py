#!/usr/bin/env python3
"""Upsert one GitHub issue with the current AI Manager report."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"


def request(path: str, token: str, method: str = "GET", payload: object | None = None) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(f"{API}{path}", data=data, method=method, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"GitHub notification request failed: {error}") from error


def body(report: dict) -> str:
    summary = report.get("summary", {})
    lines = ["<!-- ai-manager-report: keep this issue open; the automation updates it. -->", "# AI Manager daily operations report", "", f"Generated: `{report.get('generated_at', '')}`", "", "## Summary"]
    lines.extend(f"- {key.replace('_', ' ')}: **{value}**" for key, value in summary.items())
    attention = report.get("requires_attention", [])
    lines.extend(["", "## Requires attention"])
    lines.extend(f"- `{item.get('review_id', 'unknown')}` — {item.get('category', 'unknown')}" for item in attention) if attention else lines.append("- No reported review items require attention.")
    lines.extend(["", "This report is informational. It does not approve replies, code changes, merges, submissions, or releases."])
    return "\n".join(lines) + "\n"


def main() -> int:
    config = json.loads((ROOT / "data/ai_manager_notification_config.json").read_text(encoding="utf-8"))
    if not config.get("enabled"):
        print("AI Manager GitHub notification is disabled")
        return 0
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required when notifications are enabled")
    repository, title = str(config.get("repository", "")), str(config.get("title", ""))
    if "/" not in repository or not title:
        raise SystemExit("notification repository and title are required")
    report = json.loads((ROOT / "data/ai_manager_daily_report.json").read_text(encoding="utf-8"))
    issues = request(f"/repos/{repository}/issues?state=open&per_page=100", token)
    existing = next((item for item in issues if isinstance(item, dict) and item.get("title") == title and "pull_request" not in item), None) if isinstance(issues, list) else None
    payload = {"title": title, "body": body(report)}
    if existing:
        request(f"/repos/{repository}/issues/{existing['number']}", token, "PATCH", payload)
        print(f"updated manager issue #{existing['number']}")
    else:
        created = request(f"/repos/{repository}/issues", token, "POST", payload)
        print(f"created manager issue #{created.get('number')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
