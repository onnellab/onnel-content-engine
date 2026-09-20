#!/usr/bin/env python3
"""Evaluate store-submission readiness without uploading or submitting anything."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from validate_app_releases import RELEASES_PATH, RELEASE_HEADER, read_csv, validate_app_releases

ROOT = Path(__file__).resolve().parents[1]


def numeric_version(value: str) -> tuple[int, ...]:
    """Return numeric semantic components; non-version text is not evidence."""
    if not re.fullmatch(r"\d+(?:\.\d+){1,}(?:\+\d+)?", value or ""):
        return ()
    return tuple(int(item) for item in re.findall(r"\d+", value))


def public_snapshot_confirmed(snapshot: dict[str, str], release: dict[str, str]) -> bool:
    if snapshot.get("status") not in {"new", "updated", "unchanged"}:
        return False
    if not snapshot.get("checked_at") or not snapshot.get("store_url") or not snapshot.get("version"):
        return False
    if release.get("platform") == "android":
        notes = snapshot.get("notes", "").casefold()
        if "public page lookup failed" in notes or "no stable public lookup" in notes:
            return False
        if "fallback" in notes and "version/update date read from google play public page" not in notes:
            return False
        if "version/update date read from google play public page" not in notes:
            return False
    current, candidate = numeric_version(snapshot["version"]), numeric_version(release.get("version", ""))
    if not current or not candidate:
        return False
    width = max(len(current), len(candidate))
    return current + (0,) * (width - len(current)) >= candidate + (0,) * (width - len(candidate))


def read_public_snapshots(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {(row.get("app_id", ""), row.get("platform", "")): row for row in csv.DictReader(handle)}


def main() -> int:
    validate_app_releases()
    config = json.loads((ROOT / "data/store_submission_config.json").read_text(encoding="utf-8"))
    approvals = {item.get("release_id"): item for item in json.loads((ROOT / "data/store_submission_approvals.json").read_text(encoding="utf-8")).get("approvals", [])}
    snapshots = read_public_snapshots(ROOT / "data/store_versions.csv")
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
        snapshot = snapshots.get((release["app_id"], release["platform"]), {})
        already_available = public_snapshot_confirmed(snapshot, release)
        records.append({"release_id": release["release_id"], "app_slug": release["app_slug"], "platform": release["platform"],
                        "store": store, "status": "already_available" if already_available else "eligible_for_manual_submission" if not reasons else "blocked",
                        "reasons": reasons, "approval": approvals.get(release["release_id"], {}), "public_store_snapshot": snapshot})
    output = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "records": records}
    (ROOT / "data/store_submission_readiness.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"evaluated {len(records)} public binary store submissions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
