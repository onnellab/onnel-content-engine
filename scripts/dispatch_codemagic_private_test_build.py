#!/usr/bin/env python3
"""Start one approved private-test build through Codemagic's Builds API."""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sync_codemagic_artifact_urls import CODEMAGIC_BUILDS_HEADER, CODEMAGIC_BUILDS_PATH, read_csv, write_csv
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, read_csv as read_releases

ROOT = Path(__file__).resolve().parents[1]
REQUESTS_PATH = ROOT / "data" / "private_test_build_requests.json"


def start_build(app_id: str, workflow_id: str, tag: str) -> str:
    token = os.environ.get("CODEMAGIC_API_TOKEN")
    if not token:
        raise SystemExit("CODEMAGIC_API_TOKEN is required")
    request = urllib.request.Request(
        "https://api.codemagic.io/builds",
        data=json.dumps({"appId": app_id, "workflowId": workflow_id, "tag": tag, "labels": ["onnellab-private-test"]}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json", "x-auth-token": token, "User-Agent": "ONNELLAB content engine"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Codemagic start-build request failed with HTTP {error.code}") from error
    build_id = value.get("buildId")
    if not isinstance(build_id, str) or not build_id:
        raise SystemExit("Codemagic start-build response did not include buildId")
    return build_id


def branch_head(repository: str, branch: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to verify the build branch")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/commits/{urllib.parse.quote(branch, safe='')}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "ONNELLAB content engine"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            sha = json.loads(response.read().decode("utf-8")).get("sha")
    except urllib.error.HTTPError as error:
        raise SystemExit(f"GitHub branch-head lookup failed with HTTP {error.code}") from error
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit("GitHub branch-head response did not include a full commit SHA")
    return sha


def create_immutable_tag(repository: str, release_id: str, commit: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to create the private-test tag")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", release_id):
        raise SystemExit("release ID cannot be used in a Git tag")
    tag = f"private-test/{release_id}-{commit[:12]}"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/git/refs",
        data=json.dumps({"ref": f"refs/tags/{tag}", "sha": commit}).encode(),
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "ONNELLAB content engine"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60):
            return tag
    except urllib.error.HTTPError as error:
        if error.code != 422:
            raise SystemExit(f"GitHub private-test tag creation failed with HTTP {error.code}") from error
        verify = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/git/ref/tags/{urllib.parse.quote(tag, safe='')}",
            headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "ONNELLAB content engine"},
        )
        try:
            with urllib.request.urlopen(verify, timeout=60) as response:
                existing = json.loads(response.read().decode("utf-8")).get("object", {}).get("sha")
        except urllib.error.HTTPError as verify_error:
            raise SystemExit(f"GitHub private-test tag verification failed with HTTP {verify_error.code}") from verify_error
        if existing != commit:
            raise SystemExit("existing private-test tag does not match the recorded merge commit")
        return tag


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--approver", required=True)
    args = parser.parse_args()
    releases = read_releases(RELEASES_PATH, RELEASE_HEADER)
    release = next((item for item in releases if item["release_id"] == args.release_id), None)
    tasks = json.loads((ROOT / "data" / "ai_coder_tasks.json").read_text(encoding="utf-8")).get("tasks", [])
    task = next((item for item in tasks if item.get("task_id") == args.task_id), None)
    if not release or release["platform"] != "ios" or release["release_type"] != "binary" or release["release_channel"] != "private_test" or release["status"] != "planned":
        raise SystemExit("release must be a planned iOS private_test binary")
    if not task or task.get("status") != "merged" or task.get("app_slug") != release["app_slug"] or task.get("repository") != release["repository"]:
        raise SystemExit("merged Coder task must match the selected private-test release app")
    builds = read_csv(CODEMAGIC_BUILDS_PATH, CODEMAGIC_BUILDS_HEADER)
    build = next((item for item in builds if item["release_id"] == args.release_id), None)
    if not build or not build["codemagic_app_id"] or not build["workflow_id"] or not build["branch"] or build["build_id"]:
        raise SystemExit("release requires an unused Codemagic app/workflow/branch mapping")
    if not re.fullmatch(r"[0-9a-f]{40}", task.get("merge_commit", "")) or branch_head(release["repository"], build["branch"]) != task["merge_commit"]:
        raise SystemExit("configured Codemagic branch is not exactly the recorded merged commit")
    payload = json.loads(REQUESTS_PATH.read_text(encoding="utf-8"))
    requests = payload.get("requests")
    if not isinstance(requests, list) or any(item.get("release_id") == args.release_id and item.get("status") != "retry_superseded" for item in requests):
        raise SystemExit("private test build request is invalid or already active")
    tag = create_immutable_tag(release["repository"], args.release_id, task["merge_commit"])
    build_id = start_build(build["codemagic_app_id"], build["workflow_id"], tag)
    build["build_id"] = build_id
    build["notes"] = f"Private-test build requested for {args.task_id}."
    write_csv(CODEMAGIC_BUILDS_PATH, CODEMAGIC_BUILDS_HEADER, builds)
    requests.append({"task_id": args.task_id, "release_id": args.release_id, "codemagic_build_id": build_id, "branch": build["branch"], "tag": tag, "merge_commit": task["merge_commit"], "status": "dispatched", "approved_by": args.approver, "dispatched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    REQUESTS_PATH.write_text(json.dumps({"requests": requests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dispatched Codemagic private-test build {build_id} for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
