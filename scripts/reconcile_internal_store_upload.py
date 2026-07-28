#!/usr/bin/env python3
"""Resolve an ambiguous private-test upload from human-verified store evidence."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ORCHESTRATIONS_PATH = DATA / "private_test_orchestrations.json"
READINESS_PATH = DATA / "internal_test_readiness.json"
SUBMISSIONS_PATH = DATA / "internal_store_submissions.json"
RECONCILIATIONS_PATH = DATA / "internal_store_upload_reconciliations.json"

CONSOLE_HOSTS = {
    "google_play": {"play.google.com"},
    "app_store": {"appstoreconnect.apple.com"},
}


def load_list(path: Path, key: str) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise SystemExit(f"{path.name} has invalid shape")
    return payload, rows


def require_console_url(value: str, provider: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in CONSOLE_HOSTS[provider]:
        hosts = ", ".join(sorted(CONSOLE_HOSTS[provider]))
        raise SystemExit(f"evidence URL must be an HTTPS store-console URL on: {hosts}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("orchestration_id")
    parser.add_argument("--outcome", choices=("uploaded", "not_uploaded"), required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    orchestrations_payload, orchestrations = load_list(ORCHESTRATIONS_PATH, "orchestrations")
    orchestration = next(
        (item for item in orchestrations if item.get("orchestration_id") == args.orchestration_id),
        None,
    )
    if not orchestration or orchestration.get("status") != "failed":
        raise SystemExit("orchestration must exist and be failed")
    if orchestration.get("failure") != "upload_dispatched_timeout":
        raise SystemExit("only an upload_dispatched_timeout can be reconciled")

    _, readiness = load_list(READINESS_PATH, "records")
    ready = next(
        (
            item
            for item in reversed(readiness)
            if item.get("release_id") == orchestration.get("release_id")
            and item.get("status") == "ready_for_internal_upload"
        ),
        None,
    )
    if not ready:
        raise SystemExit("matching successful internal-test readiness evidence is required")
    provider = ready.get("provider")
    identifier = ready.get("identifier")
    checksum = ready.get("checksum_sha256")
    if provider not in CONSOLE_HOSTS or not isinstance(identifier, str) or not identifier:
        raise SystemExit("readiness provider or identifier is invalid")
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise SystemExit("readiness checksum is invalid")
    expected_provider = "google_play" if orchestration.get("platform") == "android" else "app_store"
    if provider != expected_provider:
        raise SystemExit("readiness provider does not match the orchestration platform")
    require_console_url(args.evidence_url, provider)

    submissions_payload, submissions = load_list(SUBMISSIONS_PATH, "submissions")
    if any(
        item.get("release_id") == orchestration.get("release_id")
        and item.get("status") == "uploaded"
        for item in submissions
    ):
        raise SystemExit("release already has a successful upload record")

    if RECONCILIATIONS_PATH.exists():
        reconciliations_payload, reconciliations = load_list(RECONCILIATIONS_PATH, "reconciliations")
    else:
        reconciliations_payload, reconciliations = {"reconciliations": []}, []

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    reconciliations.append(
        {
            "orchestration_id": args.orchestration_id,
            "release_id": orchestration["release_id"],
            "provider": provider,
            "identifier": identifier,
            "checksum_sha256": checksum,
            "outcome": args.outcome,
            "evidence_url": args.evidence_url,
            "approved_by": args.approver,
            "reconciled_at": now,
            "workflow_run_url": args.run_url,
        }
    )

    previous_failure = orchestration.pop("failure")
    orchestration.setdefault("reconciliation_history", []).append(
        {
            "failure": previous_failure,
            "outcome": args.outcome,
            "approved_by": args.approver,
            "evidence_url": args.evidence_url,
            "reconciled_at": now,
        }
    )
    orchestration["approver"] = args.approver
    orchestration["last_transition_at"] = now

    action = "none"
    if args.outcome == "uploaded":
        submissions.append(
            {
                "release_id": orchestration["release_id"],
                "provider": provider,
                "identifier": identifier,
                "checksum_sha256": checksum,
                "channel": "internal" if provider == "google_play" else "testflight",
                "status": "uploaded",
                "uploaded_at": now,
                "workflow_run_url": args.run_url,
                "source": "store_console_reconciliation",
                "store_console_evidence_url": args.evidence_url,
                "reconciled_by": args.approver,
            }
        )
        orchestration["status"] = "completed"
    else:
        orchestration["status"] = "readiness_dispatched"
        action = "advance"

    ORCHESTRATIONS_PATH.write_text(
        json.dumps(orchestrations_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    SUBMISSIONS_PATH.write_text(
        json.dumps(submissions_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    RECONCILIATIONS_PATH.write_text(
        json.dumps(reconciliations_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.github_output:
        args.github_output.write_text(
            f"action={action}\nrelease_id={orchestration['release_id']}\n", encoding="utf-8"
        )
    print(f"reconciled {args.orchestration_id} as {args.outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
