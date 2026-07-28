#!/usr/bin/env python3
"""Start one approved private-test build through Codemagic's Builds API."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sync_codemagic_artifact_urls import CODEMAGIC_BUILDS_HEADER, CODEMAGIC_BUILDS_PATH, read_csv, write_csv
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, read_csv as read_releases

ROOT = Path(__file__).resolve().parents[1]
REQUESTS_PATH = ROOT / "data" / "private_test_build_requests.json"


def start_build(app_id: str, workflow_id: str, branch: str) -> str:
    token = os.environ.get("CODEMAGIC_API_TOKEN")
    if not token:
        raise SystemExit("CODEMAGIC_API_TOKEN is required")
    request = urllib.request.Request(
        "https://api.codemagic.io/builds",
        data=json.dumps({"appId": app_id, "workflowId": workflow_id, "branch": branch, "labels": ["onnellab-private-test"]}).encode(),
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
    if not release or release["release_type"] != "binary" or release["release_channel"] != "private_test" or release["status"] != "planned":
        raise SystemExit("release must be a planned private_test binary")
    if not task or task.get("status") != "merged" or task.get("app_slug") != release["app_slug"] or task.get("repository") != release["repository"]:
        raise SystemExit("merged Coder task must match the selected private-test release app")
    builds = read_csv(CODEMAGIC_BUILDS_PATH, CODEMAGIC_BUILDS_HEADER)
    build = next((item for item in builds if item["release_id"] == args.release_id), None)
    if not build or not build["codemagic_app_id"] or not build["workflow_id"] or not build["branch"] or build["build_id"]:
        raise SystemExit("release requires an unused Codemagic app/workflow/branch mapping")
    payload = json.loads(REQUESTS_PATH.read_text(encoding="utf-8"))
    requests = payload.get("requests")
    if not isinstance(requests, list) or any(item.get("release_id") == args.release_id for item in requests):
        raise SystemExit("private test build request is invalid or already recorded")
    build_id = start_build(build["codemagic_app_id"], build["workflow_id"], build["branch"])
    build["build_id"] = build_id
    build["notes"] = f"Private-test build requested for {args.task_id}."
    write_csv(CODEMAGIC_BUILDS_PATH, CODEMAGIC_BUILDS_HEADER, builds)
    requests.append({"task_id": args.task_id, "release_id": args.release_id, "codemagic_build_id": build_id, "branch": build["branch"], "status": "dispatched", "approved_by": args.approver, "dispatched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    REQUESTS_PATH.write_text(json.dumps({"requests": requests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dispatched Codemagic private-test build {build_id} for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
