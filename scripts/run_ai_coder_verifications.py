#!/usr/bin/env python3
"""Run every approved AI-Coder verification command and record its exit code."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("app_path", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    commands = packet.get("task", {}).get("ticket", {}).get("verification_commands", [])
    if not isinstance(commands, list) or not commands:
        raise SystemExit("approved task has no verification commands")
    if not args.app_path.is_dir():
        raise SystemExit("app checkout is unavailable")

    results: list[dict[str, object]] = []
    failed = False
    for index, command in enumerate(commands, start=1):
        if not isinstance(command, str) or not command.strip():
            raise SystemExit("verification commands must be non-empty strings")
        print(f"[verification {index}/{len(commands)}] {command}", flush=True)
        completed = subprocess.run(
            ["bash", "-o", "pipefail", "-c", command],
            cwd=args.app_path,
            check=False,
        )
        status = "passed" if completed.returncode == 0 else "failed"
        results.append({"command": command, "status": status, "exit_code": completed.returncode})
        if completed.returncode:
            failed = True
            break

    args.output.write_text(
        json.dumps({"status": "failed" if failed else "passed", "results": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    if failed:
        raise SystemExit("approved verification command failed")
    print(f"all {len(results)} approved verification command(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
