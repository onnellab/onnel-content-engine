#!/usr/bin/env python3
"""Evaluate store-submission readiness without uploading or submitting anything."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from validate_app_releases import RELEASES_PATH, RELEASE_HEADER, read_csv, validate_app_releases

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    validate_app_releases()
    config = json.loads((ROOT / "data/store_submission_config.json").read_text(encoding="utf-8"))
    approvals = {item.get("release_id"): item for item in json.loads((ROOT / "data/store_submission_approvals.json").read_text(encoding="utf-8")).get("approvals", [])}
    records = []
    for release in read_csv(RELEASES_PATH, RELEASE_HEADER):
        if release["release_type"] != "binary" or release["release_channel"] != "public" or release["status"] not in {"planned", "ready"}:
            continue
        store = "google_play" if release["platform"] == "android" else "app_store" if release["platform"] == "ios" else ""
        reasons = []
        if release["status"] != "ready": reasons.append("release artifact and public release readiness are not complete")
        if release["release_id"] not in approvals: reasons.append("human submission approval with QA PASS is missing")
        if not store: reasons.append("platform has no store submission adapter")
        elif not config.get(store, {}).get("enabled"): reasons.append(f"{store} connection is not enabled")
        records.append({"release_id": release["release_id"], "app_slug": release["app_slug"], "platform": release["platform"],
                        "store": store, "status": "eligible_for_manual_submission" if not reasons else "blocked",
                        "reasons": reasons, "approval": approvals.get(release["release_id"], {})})
    output = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "records": records}
    (ROOT / "data/store_submission_readiness.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"evaluated {len(records)} public binary store submissions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
