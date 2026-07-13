#!/usr/bin/env python3
"""Run a command after loading local export lines from an ignored env file."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / "docs" / "environment variables.md"
EXPORT_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$")
PLACEHOLDERS = {"", "...", "<redacted>", "redacted", "REDACTED"}


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        match = EXPORT_PATTERN.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        try:
            parsed = shlex.split(raw_value, comments=False, posix=True)
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: invalid shell value for {key}") from error
        value = parsed[0] if parsed else ""
        if value.strip() in PLACEHOLDERS:
            continue
        values[key] = value
    return values


def run_with_local_env(command: list[str], env_file: Path = DEFAULT_ENV_FILE, dry_run: bool = False) -> int:
    if not env_file.exists():
        raise FileNotFoundError(f"local env file not found: {env_file}")
    loaded = parse_env_file(env_file)
    if dry_run:
        print(f"would load {len(loaded)} environment variable(s) from {env_file}")
        for key in sorted(loaded):
            print(key)
        return 0
    env = os.environ.copy()
    env.update(loaded)
    return subprocess.run(command, cwd=ROOT, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Load ignored local env exports, then run a command")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--dry-run", action="store_true", help="List loaded variable names without running a command")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not args.dry_run and not command:
        parser.error("command is required unless --dry-run is used")
    try:
        return run_with_local_env(command, args.env_file, args.dry_run)
    except (OSError, ValueError) as error:
        print(f"local env load failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
