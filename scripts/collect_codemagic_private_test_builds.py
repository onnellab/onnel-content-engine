#!/usr/bin/env python3
"""Read Codemagic status for dispatched private-test builds; never start builds."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sync_codemagic_artifact_urls import build_path, request_json, sync_codemagic_artifact_urls

ROOT = Path(__file__).resolve().parents[1]
REQUESTS_PATH = ROOT / "data" / "private_test_build_requests.json"
STATUS_PATH = ROOT / "data" / "private_test_build_sync_status.json"


def status_values(value: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"status", "buildStatus", "build_status"} and isinstance(item, str):
                values.add(item.strip().lower())
            values.update(status_values(item))
    elif isinstance(value, list):
        for item in value:
            values.update(status_values(item))
    return values


def classify(values: set[str]) -> str:
    if values & {"failed", "failure", "canceled", "cancelled", "error"}:
        return "failed"
    if values & {"succeeded", "success", "successful", "completed"}:
        return "succeeded"
    if values & {"queued", "pending", "running", "in_progress", "in progress"}:
        return "running"
    return "unknown"


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = json.loads(REQUESTS_PATH.read_text(encoding="utf-8"))
    requests = payload.get("requests")
    if not isinstance(requests, list):
        raise SystemExit("private test build requests have invalid shape")
    if not os.environ.get("CODEMAGIC_API_TOKEN"):
        STATUS_PATH.write_text(json.dumps({"checked_at": now, "state": "token_missing", "records": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("CODEMAGIC_API_TOKEN is not configured; no private-test build status collected")
        return 0
    records: list[dict[str, str]] = []
    succeeded = False
    for item in requests:
        if item.get("status") not in {"dispatched", "running", "succeeded"}:
            continue
        build_id = item.get("codemagic_build_id", "")
        if not build_id:
            continue
        try:
            observed = classify(status_values(request_json(build_path(build_id), os.environ["CODEMAGIC_API_TOKEN"])))
        except Exception as error:
            observed = "unknown"
            records.append({"release_id": item.get("release_id", ""), "build_id": build_id, "status": observed, "detail": type(error).__name__})
        else:
            item["status"] = observed
            item["last_checked_at"] = now
            records.append({"release_id": item.get("release_id", ""), "build_id": build_id, "status": observed, "detail": "Codemagic build status"})
            succeeded = succeeded or observed == "succeeded"
    if succeeded:
        try:
            synced = sync_codemagic_artifact_urls()
            synced_ids = {item["release_id"] for item in synced}
            for item in requests:
                if item.get("status") == "succeeded" and item.get("release_id") in synced_ids:
                    item["status"] = "artifact_ready"
        except Exception:
            pass
    REQUESTS_PATH.write_text(json.dumps({"requests": requests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_PATH.write_text(json.dumps({"checked_at": now, "state": "collected", "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"collected {len(records)} private-test build status record(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
