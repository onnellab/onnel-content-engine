#!/usr/bin/env python3
"""Validate operational files only for apps declaring the ONNELLAB template marker."""
from __future__ import annotations
import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    args = parser.parse_args()
    root = args.app.resolve()
    marker = root / ".onnellab-template-version"
    if not marker.exists():
        print("legacy_app: template contract not required")
        return 0
    version = marker.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("template contract failed: empty .onnellab-template-version")
    required = (
        "AGENTS.md", "CODEX_BOOT.md", "CODEX.md", "SYSTEM/GLOBAL_UI_RULES.md",
        "SKILLS/00_SKILL_INDEX.md", "tool/quality_gate.sh", "tool/verify_patch_notes.sh",
        "docs/app.md", "docs/store_description.md",
    )
    missing = [item for item in required if not (root / item).is_file()]
    if missing:
        raise SystemExit(f"template contract failed: missing {', '.join(missing)}")
    print(f"template_app: contract valid (version {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
