#!/usr/bin/env python3
"""Validate and record one read-only Doctor diagnosis."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("finding_id")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not SAFE_ID.fullmatch(args.finding_id):
        raise SystemExit("finding ID is invalid")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if report.get("finding_id") != args.finding_id or report.get("status") not in {"DIAGNOSED", "STOP"}:
        raise SystemExit("Doctor report identity or status is invalid")
    if not isinstance(report.get("hypotheses"), list) or not isinstance(report.get("evidence"), list):
        raise SystemExit("Doctor report hypotheses and evidence must be lists")
    if report["status"] == "DIAGNOSED" and (not report["hypotheses"] or not report["evidence"]):
        raise SystemExit("a diagnosis requires hypotheses and objective evidence")
    if not report.get("reproduction") or not report.get("risk"):
        raise SystemExit("Doctor report requires reproduction and risk")
    findings_path = ROOT / "data" / "ai_doctor_findings.json"
    payload = json.loads(findings_path.read_text(encoding="utf-8"))
    finding = next((item for item in payload.get("findings", []) if item.get("finding_id") == args.finding_id), None)
    if not finding or finding.get("diagnosis_status") not in {"pending", "STOP"}:
        raise SystemExit("finding is not eligible for diagnosis")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    finding["diagnosis_status"] = report["status"]
    finding["diagnosis"] = report
    finding["diagnosed_at"] = now
    findings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = ROOT / "data" / "ai_doctor_diagnoses" / f"{args.finding_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"recorded_at": now, **report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded Doctor diagnosis for {args.finding_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
