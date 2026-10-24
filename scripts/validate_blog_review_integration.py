#!/usr/bin/env python3
"""Check the closed 2026-10-24 review integration in a disposable copy only."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import prepare_tagweaver_preview as tag
import prepare_vaultxt_preview as vault
from prepare_research_preview import (
    source_inventory, copy_source, safe_native_path, read_native_bytes,
    native_entry, MAX_NATIVE_BYTES,
)
from schedule_ready_articles import current_review_score
from evaluate_article import DEFAULT_THRESHOLD

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = "preview/integration-qa-20261024.json"
BUNDLES = (("tag", tag), ("vault", vault))


def validate_rows(rows):
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate topic IDs")
    for _, profile in BUNDLES:
        group = [row for row in rows if row["slug"] == profile.SLUG]
        if len(group) != 9 or {row["primary_language"] for row in group} != set(profile.LOCALES):
            raise ValueError("Each required bundle needs exactly nine locales")
        for row in group:
            canonical = f"generated/markdown/{row['primary_language']}/{profile.CATEGORY}/{profile.SLUG}.md"
            if (row["status"] != "review" or row["category"] != profile.CATEGORY
                    or row["related_apps"] != profile.RELATED_APP
                    or row["canonical_path"] != canonical
                    or any(row[field] for field in ("scheduled_at", "published_at", "published_url"))):
                raise ValueError("Required bundle must be an exact unscheduled review registration")
    if sum(row["status"] == "idea" for row in rows) < 8:
        raise ValueError("At least eight ideas required")


def validate_fingerprints(root, receipt):
    manifests = receipt["native_manifests"]
    if set(manifests) != {"tag", "vault"}:
        raise ValueError("Both closed native manifests are required")
    count = 0
    for key, profile in BUNDLES:
        manifest = profile.validate_native_manifest(manifests[key])
        for entry in manifest["files"]:
            path = safe_native_path(root, entry["path"], required=True)
            actual = native_entry(entry["path"], read_native_bytes(path, MAX_NATIVE_BYTES))
            if actual != entry:
                raise ValueError(f"Native fingerprint mismatch: {entry['path']}")
            count += 1
    if count != 144:
        raise ValueError("Exactly 144 native fingerprints required")
    return count


def run_gates(stage):
    for arguments in vault.GATES:
        print("AGGREGATE_GATE " + " ".join(arguments), flush=True)
        subprocess.run([sys.executable, str(stage / "scripts" / arguments[0]), *arguments[1:]],
                       cwd=stage, check=True, timeout=180)


def validate_integration(source=ROOT):
    source = Path(source)
    before = source_inventory(source)
    receipt = json.loads((source / RECEIPT).read_text(encoding="utf-8"))
    with (source / "data/topics.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    validate_rows(rows)
    count = validate_fingerprints(source, receipt)
    try:
        with tempfile.TemporaryDirectory(prefix="blog-review-aggregate-") as temporary:
            stage = Path(temporary) / "engine"
            copy_source(source, stage, before)
            validate_fingerprints(stage, receipt)
            run_gates(stage)
            for _, profile in BUNDLES:
                for row in rows:
                    if row["slug"] == profile.SLUG:
                        score = current_review_score(row, stage / "data/topics.csv",
                                                     stage / "generated/reviews", DEFAULT_THRESHOLD)
                        if score is None or score < DEFAULT_THRESHOLD:
                            raise ValueError("Required article failed current-input review checks")
                        print(f"AGGREGATE_REVIEW {row['id']} {row['primary_language']} {score}", flush=True)
            validate_fingerprints(source, receipt)
    finally:
        if source_inventory(source) != before:
            raise ValueError("Aggregate QA changed source files")
    print(f"AGGREGATE_PASS bundles=2 locales_each=9 native_fingerprints={count} gates=5 source_unchanged=true")


if __name__ == "__main__":
    validate_integration()
