#!/usr/bin/env python3
"""Prepare bounded recent-commit and code-path evidence for one Doctor finding."""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,}")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")
STOP_WORDS = {
    "about", "after", "again", "app", "build", "crash", "error", "issue", "large",
    "opening", "report", "when", "with", "without",
}


def git(app_path: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(app_path), *args],
        check=check,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def search_terms(finding: dict) -> list[str]:
    text = " ".join(
        [
            str(finding.get("crash", {}).get("title", "")),
            str(finding.get("github_issue", {}).get("title", "")),
        ]
    )
    return sorted({value.lower() for value in TOKEN.findall(text) if value.lower() not in STOP_WORDS})[:8]


def candidate_files(app_path: Path, terms: list[str]) -> list[str]:
    candidates: set[str] = set()
    roots = [name for name in ("lib", "test", "integration_test") if (app_path / name).exists()]
    if not roots:
        return []
    for term in terms:
        result = subprocess.run(
            ["git", "-C", str(app_path), "grep", "-I", "-l", "-i", "-e", term, "--", *roots],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"git grep failed for term: {term}")
        candidates.update(line for line in result.stdout.splitlines() if line)
    return sorted(candidates)[:40]


def prepare(finding_id: str) -> dict:
    if not SAFE_ID.fullmatch(finding_id):
        raise SystemExit("finding ID is invalid")
    findings = json.loads((DATA / "ai_doctor_findings.json").read_text(encoding="utf-8")).get("findings", [])
    finding = next((item for item in findings if item.get("finding_id") == finding_id), None)
    if not finding or finding.get("diagnosis_status") not in {"pending", "STOP"}:
        raise SystemExit("finding must exist and need diagnosis")
    with (DATA / "local_repositories.csv").open(encoding="utf-8", newline="") as handle:
        local = next((row for row in csv.DictReader(handle) if row["app_slug"] == finding.get("app_slug")), None)
    if not local:
        raise SystemExit("finding app has no local repository mapping")
    app_path = Path(local["path"]).expanduser().resolve()
    if not (app_path / local["pubspec_path"]).is_file():
        raise SystemExit(f"mapped Flutter repository is unavailable: {app_path}")
    if git(app_path, "rev-parse", "--is-inside-work-tree", check=False) != "true":
        raise SystemExit(f"mapped Flutter repository is not a Git worktree: {app_path}")
    terms = search_terms(finding)
    commits = []
    for line in git(app_path, "log", "-8", "--format=%H%x09%aI%x09%s").splitlines():
        sha, committed_at, subject = (line.split("\t", 2) + ["", ""])[:3]
        commits.append({"sha": sha, "committed_at": committed_at, "subject": subject})
    entry_rules = [
        name
        for name in ("AGENTS.md", "CODEX_BOOT.md", "CODEX.md", "SKILLS/00_SKILL_INDEX.md")
        if (app_path / name).is_file()
    ]
    return {
        "finding": finding,
        "app_path": str(app_path),
        "repository": local["repository_name"],
        "head_commit": git(app_path, "rev-parse", "HEAD"),
        "recent_commits": commits,
        "search_terms": terms,
        "candidate_files": candidate_files(app_path, terms),
        "entry_rules": entry_rules,
        "constraints": [
            "read-only diagnosis; do not edit app or engine files",
            "do not claim a root cause without reproduction or direct code evidence",
            "do not fetch or store issue bodies, user logs, credentials, or personal data",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("finding_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(prepare(args.finding_id), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"prepared Doctor context for {args.finding_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
