#!/usr/bin/env python3
"""Read-only preflight for the existing public artwork publisher credentials.

Never creates credentials, reads secret values from GitHub, writes remote state,
or prints HTTP bodies/headers. Executed only on the public engine's trusted main.
"""
from __future__ import annotations
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = re.compile(r"^onnellab/[A-Za-z0-9][A-Za-z0-9_.-]*$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected GitHub API redirect")


def request(path: str, token: str) -> dict:
    req = urllib.request.Request("https://api.github.com/repos/" + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "ONNELLAB artwork read-access preflight"})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
        if response.url != req.full_url:
            raise ValueError("Unexpected GitHub API redirect")
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Oversized read-access response")
        return json.loads(raw)


def check(config: Path, release_token: str, pages_token: str, fetch=request) -> list[str]:
    if not release_token or not pages_token:
        raise ValueError("Existing release and Pages credentials are required")
    with config.open(newline="", encoding="utf-8") as handle:
        repositories = {row["repository"].strip() for row in csv.DictReader(handle)}
    if not repositories or any(not REPO.fullmatch(repo) for repo in repositories):
        raise ValueError("Invalid app repository registry")
    checks = [(repo, release_token) for repo in sorted(repositories | {"onnellab/onnellab-flutter-template"})]
    checks += [("onnellab/onnellab.github.io", pages_token), ("onnellab/onnel-content-engine", pages_token)]
    verified = []
    for repo, token in checks:
        try:
            metadata = fetch(repo, token)
            if metadata.get("full_name", "").lower() != repo.lower():
                raise ValueError("Unexpected repository identity")
            if repo in {"onnellab/onnellab.github.io", "onnellab/onnel-content-engine"} and metadata.get("private") is not False:
                raise ValueError("Publisher/site must remain public for the standard free runner path")
            branch = metadata.get("default_branch", "")
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", branch) or ".." in branch:
                raise ValueError("Invalid default branch")
            tree = fetch(repo + "/git/trees/" + branch, token)
            if not re.fullmatch(r"[a-f0-9]{40}", tree.get("sha", "")) or not isinstance(tree.get("tree"), list):
                raise ValueError("Repository contents read not confirmed")
        except (OSError, ValueError, KeyError, TypeError) as error:
            # Never include a response body, header, token or redirect target.
            raise ValueError(f"Existing credentials cannot verify {repo} ({type(error).__name__})") from None
        verified.append(repo)
    return verified


def main() -> int:
    try:
        for repo in check(ROOT / "data/app_release_config.csv", os.environ.get("GITHUB_TOKEN", ""),
                          os.environ.get("GITHUB_TOKEN", "")):
            print("READ VERIFIED " + repo)
        print("Read-only preflight passed; no artwork, app release or site publication performed")
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
