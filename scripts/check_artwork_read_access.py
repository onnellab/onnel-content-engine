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
import signal
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


def check_bundles(config: Path, emit=print, *, verify_backend: str | None = None) -> dict:
    """Inspect fresh authorized app copies as data; never execute their root CLIs."""
    if verify_backend not in {None, "docker-readonly"}:
        raise ValueError("Unsupported read-only artwork backend")
    summary = {"registered": 0, "bundles_verified": 0, "gates_verified": 0, "unsupported": 0, "blocked": 0}
    from isolated_vendored_artwork import validate_vendored_bundle, run_verified_gate
    from sync_homepage_release_artwork import checkout, locate_project, read_rows
    with tempfile.TemporaryDirectory(prefix="artwork-read-probe-") as directory:
        work = Path(directory)
        clones = {}
        clone_failures = {}
        rows = read_rows(config)
        summary["registered"] = len(rows)
        for row in rows:
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
                custom_root = str(error) == "Unsupported custom root artwork gate; a separately reviewed bridge is required"
                if verify_backend is not None and not custom_root:
                    summary["blocked"] += 1
                    reason = "inventory_unverified" if phase == "inventory_missing_or_unsupported" else "canonical_bundle_unverified"
                    emit(f"ARTWORK BLOCKED {repo}/{slug} reason={reason} ({type(error).__name__})")
                else:
                    summary["unsupported"] += 1
                    reason = "custom_root_gate" if custom_root else phase
                    emit(f"ARTWORK UNSUPPORTED {repo}/{slug} reason={reason} ({type(error).__name__})")
                continue
            summary["bundles_verified"] += 1
            emit(f"BUNDLE VERIFIED {repo}/{slug} source={bundle.source_commit}")
            if verify_backend is not None:
                try:
                    run_verified_gate(project, "verify-site", backend=verify_backend)
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                    summary["blocked"] += 1
                    # A nonzero Docker attach cannot distinguish a boundary or
                    # runtime failure from rejected artwork evidence. Stop every
                    # subsequent container; never infer a safe per-app rejection.
                    emit(f"ARTWORK BLOCKED {repo}/{slug} reason=runtime_or_gate_unverified")
                    emit("READONLY ARTWORK SUMMARY " + json.dumps(summary, sort_keys=True))
                    raise ValueError("Read-only artwork runtime or gate unverified; remaining probes stopped") from None
                else:
                    summary["gates_verified"] += 1
                    emit(f"ARTWORK VERIFIED {repo}/{slug} backend=docker-readonly")
        if clone_failures:
            raise ValueError("; ".join(clone_failures.values()))
    return summary


def _main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments not in ([], ["--docker-verify"]):
        print("Unsupported read-only artwork probe arguments", file=sys.stderr)
        return 1
    docker_verify = bool(arguments)
    config = ROOT / "data/app_release_config.csv"
    try:
        check(config, os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_TOKEN", ""))
        if docker_verify:
            from check_artwork_docker_isolation import run_trial
            proof = run_trial(inspect_profile_readonly=True)
            if proof.get("status") != "passed" or proof.get("cleanup") != "verified":
                raise ValueError("Synthetic Docker isolation proof was not verified")
            print("ISOLATION VERIFIED: public synthetic Docker proof passed before app execution")
            summary = check_bundles(config, verify_backend="docker-readonly")
            print("READONLY ARTWORK SUMMARY " + json.dumps(summary, sort_keys=True))
            if (summary["gates_verified"] == 0 or summary["blocked"] or summary["unsupported"]
                    or summary["gates_verified"] != summary["registered"]):
                print("Read-only artwork coverage incomplete; no publication performed")
                return 1
            print("Read-only artwork gates verified for the registered apps; no publication performed")
            return 0
        from isolated_vendored_artwork import sandbox_preflight
        sandbox_preflight()
        print("ISOLATION VERIFIED: no app code executed")
        check_bundles(config)
        print("Read-only access/isolation preflight passed; unsupported app evidence remains blocked; no publication performed")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments != ["--docker-verify"]:
        return _main(arguments)
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        return _main(arguments)
    except KeyboardInterrupt:
        print("Read-only artwork probe interrupted; no publication performed", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
