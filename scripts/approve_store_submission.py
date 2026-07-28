#!/usr/bin/env python3
"""Record one human approval after a passing QA report; never submit to a store."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_ai_qa_report import main as validate_qa
from validate_app_releases import RELEASES_PATH, read_csv, RELEASE_HEADER

ROOT = Path(__file__).resolve().parents[1]


def require_matching_internal_test(release: dict[str, str], releases: list[dict[str, str]]) -> None:
    config = json.loads((ROOT / "data" / "internal_test_gate_config.json").read_text(encoding="utf-8"))
    enabled = config.get("enabled")
    required_apps = config.get("required_apps")
    if not isinstance(enabled, bool) or not isinstance(required_apps, list) or not all(isinstance(app, str) for app in required_apps):
        raise SystemExit("internal test gate configuration is invalid")
    if not enabled or (required_apps and release["app_slug"] not in required_apps):
        return
    results = json.loads((ROOT / "data" / "internal_test_results.json").read_text(encoding="utf-8")).get("results", [])
    releases_by_id = {item["release_id"]: item for item in releases}
    for result in results:
        tested = releases_by_id.get(result.get("release_id", ""))
        if result.get("status") == "passed" and tested and tested["release_channel"] == "private_test" and all(tested[field] == release[field] for field in ("app_slug", "platform", "version")):
            return
    raise SystemExit("public submission requires a passed internal test for the same app, platform, and version")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    releases = read_csv(RELEASES_PATH, RELEASE_HEADER)
    release = next((item for item in releases if item["release_id"] == args.release_id), None)
    if not release or release["release_type"] != "binary" or release["release_channel"] != "public":
        raise SystemExit("release must be a public binary release")
    require_matching_internal_test(release, releases)
    candidate_path = ROOT / "data" / "release-candidate-reports" / f"{args.task_id}.json"
    if not candidate_path.is_file():
        raise SystemExit(f"release candidate report not found: {candidate_path.relative_to(ROOT)}")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_keys = ("pub_get", "static_analysis", "tests", "android_release_bundle", "ios_unsigned_release_build")
    if candidate.get("task_id") != args.task_id or any(candidate.get(key) != "passed" for key in candidate_keys):
        raise SystemExit("release candidate did not pass every required build check")
    with (ROOT / "data" / "apps_registry.csv").open(encoding="utf-8", newline="") as handle:
        import csv
        app = next((item for item in csv.DictReader(handle) if item["slug"] == release["app_slug"]), None)
    if not app:
        raise SystemExit("release app is missing from registry")
    if "ios" in app.get("platforms", "").split("|"):
        device_path = ROOT / "data" / "ios-device-qa-reports" / f"{args.task_id}.json"
        if not device_path.is_file() or json.loads(device_path.read_text(encoding="utf-8")).get("status") != "PASS":
            raise SystemExit("iOS public release requires a recorded physical-device QA PASS")
    report = ROOT / "data" / "qa-reports" / f"{args.task_id}.json"
    if not report.is_file():
        raise SystemExit(f"QA report not found: {report.relative_to(ROOT)}")
    import sys
    original = sys.argv
    try:
        sys.argv = ["validate_ai_qa_report.py", str(report)]
        if validate_qa() != 0:
            raise SystemExit("QA report did not pass")
    finally:
        sys.argv = original
    if not args.confirm:
        print(f"dry run: would approve store submission for {args.release_id}")
        return 0
    path = ROOT / "data" / "store_submission_approvals.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    approvals = [item for item in payload.get("approvals", []) if item.get("release_id") != args.release_id]
    approvals.append({"release_id": args.release_id, "task_id": args.task_id, "approved_by": args.approver,
                      "approved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "status": "approved_for_submission"})
    path.write_text(json.dumps({"approvals": approvals}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"approved store submission for {args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
