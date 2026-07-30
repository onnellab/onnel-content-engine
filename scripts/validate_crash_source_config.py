#!/usr/bin/env python3
"""Validate crash-provider coverage against every registered release app."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> list[str]:
    with (root / "data/app_release_config.csv").open(encoding="utf-8", newline="") as handle:
        apps = {row["app_slug"] for row in csv.DictReader(handle)}
    errors: list[str] = []
    for filename, source_key in (
        ("crashlytics_crash_sources.json", "apps"),
        ("sentry_crash_sources.json", "projects"),
    ):
        payload = json.loads((root / "data" / filename).read_text(encoding="utf-8"))
        sources = payload.get(source_key, [])
        coverage = payload.get("coverage", [])
        covered = [str(item.get("app_slug", "")) for item in coverage if isinstance(item, dict)]
        if len(covered) != len(set(covered)):
            errors.append(f"{filename}: duplicate coverage app_slug")
        missing = sorted(apps - set(covered))
        unknown = sorted(set(covered) - apps)
        if missing:
            errors.append(f"{filename}: missing coverage for {', '.join(missing)}")
        if unknown:
            errors.append(f"{filename}: unknown coverage for {', '.join(unknown)}")
        source_apps = {str(item.get("app_slug", "")) for item in sources if isinstance(item, dict)}
        for item in coverage:
            if not isinstance(item, dict):
                errors.append(f"{filename}: coverage entries must be objects")
                continue
            state = item.get("state")
            if state not in {"configured", "not_applicable"}:
                errors.append(f"{filename}: {item.get('app_slug')} has invalid state")
            if not str(item.get("reason", "")).strip():
                errors.append(f"{filename}: {item.get('app_slug')} needs a reason")
            if state == "configured" and item.get("app_slug") not in source_apps:
                errors.append(f"{filename}: {item.get('app_slug')} is configured without a source")
        if source_apps - apps:
            errors.append(f"{filename}: source references an unknown app")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        raise SystemExit("\n".join(errors))
    print("crash source configuration validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
