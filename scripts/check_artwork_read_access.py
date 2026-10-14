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
import tempfile
import subprocess
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


def check(config: Path, release_token: str, pages_token: str, fetch=request, emit=print) -> list[str]:
    if not release_token or not pages_token:
        raise ValueError("Existing release and Pages credentials are required")
    with config.open(newline="", encoding="utf-8") as handle:
        repositories = {row["repository"].strip() for row in csv.DictReader(handle)}
    if not repositories or any(not REPO.fullmatch(repo) for repo in repositories):
        raise ValueError("Invalid app repository registry")
    checks = [(repo, release_token) for repo in sorted(repositories)]
    checks += [("onnellab/onnellab.github.io", pages_token), ("onnellab/onnel-content-engine", pages_token)]
    verified = []
    failures = []
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
            status = (f" HTTP {error.code}" if isinstance(error, urllib.error.HTTPError)
                      and type(error.code) is int and 100 <= error.code <= 599 else "")
            message = f"Existing credentials cannot verify {repo} ({type(error).__name__}{status})"
            failures.append(message)
            emit("READ BLOCKED " + message)
            continue
        verified.append(repo)
        emit("READ VERIFIED " + repo)
    if failures:
        raise ValueError("; ".join(failures))
    return verified


def check_bundles(config: Path, emit=print) -> None:
    """Inspect fresh authorized app copies as data; never execute their root CLIs."""
    from isolated_vendored_artwork import validate_vendored_bundle
    from sync_homepage_release_artwork import checkout, locate_project, read_rows
    with tempfile.TemporaryDirectory(prefix="artwork-read-probe-") as directory:
        work = Path(directory)
        clones = {}
        clone_failures = {}
        for row in read_rows(config):
            repo, slug = row["repository"], row["app_slug"]
            if repo not in clones and repo not in clone_failures:
                try:
                    clones[repo] = checkout(repo, work)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    clone_failures[repo] = f"Fresh app checkout failed: {repo} ({type(error).__name__})"
                    emit("READ BLOCKED " + clone_failures[repo])
            if repo in clone_failures:
                continue
            phase = "inventory_missing_or_unsupported"
            try:
                project = locate_project(clones[repo], slug)
                phase = "canonical_bundle_or_root_gate_untrusted"
                bundle = validate_vendored_bundle(project)
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
                # A missing/custom inventory is a per-app readiness limitation,
                # not proof that the network or credential read failed.
                emit(f"ARTWORK UNSUPPORTED {repo}/{slug} reason={phase} ({type(error).__name__})")
                continue
            emit(f"BUNDLE VERIFIED {repo}/{slug} source={bundle.source_commit}")
        if clone_failures:
            raise ValueError("; ".join(clone_failures.values()))


def main() -> int:
    config = ROOT / "data/app_release_config.csv"
    try:
        check(config, os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_TOKEN", ""))
        from isolated_vendored_artwork import sandbox_preflight
        sandbox_preflight()
        print("ISOLATION VERIFIED: no app code executed")
        check_bundles(config)
        print("Read-only access/isolation preflight passed; unsupported app evidence remains blocked; no publication performed")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
