#!/usr/bin/env python3
"""Stage reviewed public-release detail artwork in the existing homepage publisher.

No renderer, store mutation, git push, scheduler, or fallback to old images lives
here. The canonical shared gate owns candidate validation and atomic staging.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def observation_error(checked_at: str, now: datetime) -> str:
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "Public store observation timestamp is missing or invalid"
    if checked.tzinfo is None:
        return "Public store observation timestamp must include its timezone"
    age = now - checked
    if age < timedelta(0):
        return "Public store observation timestamp is in the future"
    if age > timedelta(hours=24):
        return "Public store observation is older than 24 hours; refresh the existing store sync"
    return ""


def eligible_releases(releases: Path, stores: Path, *, now: datetime | None = None) -> list[dict[str, str]]:
    # Reuse the existing independent-public-observation decision. A successful
    # upload, a GitHub Release, or private_test never establishes public status.
    from fill_ready_app_releases import is_store_confirmed, public_store_versions
    observed = public_store_versions(stores)
    now = now or datetime.now(timezone.utc)
    rows = [row for row in read_rows(releases)
            if row.get("status") in {"ready", "released"}
            and is_store_confirmed(row, observed)]
    for row in rows:
        if not SLUG.fullmatch(row["app_slug"]) or not REPOSITORY.fullmatch(row["repository"]):
            raise ValueError("Unsafe app slug or repository in release manifest")
        snapshot = observed[(row["app_id"], row["platform"])]
        if snapshot.get("app_slug") != row["app_slug"]:
            raise ValueError("Store observation app slug differs from release")
        row["store_checked_at"] = snapshot.get("checked_at", "")
        row["store_evidence_error"] = observation_error(row["store_checked_at"], now)
        row["store_url"] = snapshot.get("store_url", "")
    return rows


def checkout(repository: str, work: Path) -> Path:
    if not REPOSITORY.fullmatch(repository):
        raise ValueError("Unsafe repository")
    destination = work / repository.replace("/", "--")
    if destination.exists():
        raise ValueError("Checkout destination already exists; use a fresh run directory")
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    token = env.get("ONNELLAB_RELEASE_TOKEN") or env.get("GITHUB_TOKEN")
    if token:
        # Never put a token in a URL, persisted git config, stdout, or argv.
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                   GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {encoded}")
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-tags", "--", f"https://github.com/{repository}.git",
                    str(destination)], env=env, check=True, capture_output=True, text=True, timeout=300)
    return destination


def locate_project(repository: Path, slug: str) -> Path:
    # The root pubspec assumption is wrong for repos such as onnellab-text/vaultxt.
    # Tracked explicit inventories make discovery bounded and unambiguous.
    names = subprocess.check_output(["git", "-C", str(repository), "ls-files", "-z"], text=True).split("\0")
    found = []
    for name in names:
        if name == "release/artwork.json" or name.endswith("/release/artwork.json"):
            path = repository / name
            if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
                raise ValueError("Unsafe artwork inventory path")
            inventory = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(inventory, dict):
                raise ValueError("Tracked artwork inventory must be a JSON object")
            if inventory.get("app_slug") == slug:
                project = path.parent.parent
                if not (project / "pubspec.yaml").is_file():
                    raise ValueError("Artwork inventory has no adjacent app pubspec")
                found.append(project)
    if len(found) != 1:
        raise ValueError(f"Expected exactly one tracked artwork inventory/pubspec for {slug}; found {len(found)}")
    return found[0]


def run_gate(gate: None, action: str, project: Path, site: Path | None = None) -> None:
    # Only the independently pinned bundle can execute, inside the OS sandbox.
    # An arbitrary root CLI or caller-supplied gate is never a trusted substitute.
    if gate is not None:
        raise ValueError("Caller-supplied artwork gates are not supported")
    from isolated_vendored_artwork import run_verified_gate
    run_verified_gate(project, action, site=site)


def stage_all(releases: Path, stores: Path, site: Path, gate: None, work: Path) -> dict:
    report = {"schema_version": 1, "status": "staged_not_published", "apps": []}
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in eligible_releases(releases, stores):
        grouped.setdefault(row["app_slug"], []).append(row)
    clones: dict[str, Path] = {}
    failures: dict[str, str] = {}
    work.mkdir(parents=True, exist_ok=True)
    for slug, rows in sorted(grouped.items()):
        result = {"app_slug": slug, "status": "blocked"}
        report["apps"].append(result)
        try:
            current_rows = [row for row in rows if not row.get("store_evidence_error")]
            if not current_rows:
                raise ValueError("; ".join(sorted({row["store_evidence_error"] for row in rows})))
            repositories = {row["repository"] for row in rows}
            if len(repositories) != 1:
                raise ValueError("Conflicting repositories for app slug")
            repo = repositories.pop()
            if repo in failures:
                raise ValueError(failures[repo])
            if repo not in clones:
                try:
                    clones[repo] = checkout(repo, work)
                except (OSError, subprocess.SubprocessError, ValueError) as error:
                    # Do not leak network diagnostics or authentication headers.
                    failures[repo] = f"Cannot obtain fresh app checkout ({type(error).__name__})"
                    raise ValueError(failures[repo]) from error
            project = locate_project(clones[repo], slug)
            run_gate(gate, "verify-site", project)
            candidate = json.loads((project / "release/artwork-candidate.json").read_text())
            if candidate.get("app_slug") != slug:
                raise ValueError("Candidate app slug differs from release")
            version = candidate["version"].split("+", 1)[0]
            matched = [row for row in current_rows if row["version"] == version]
            if not matched:
                raise ValueError("Latest reviewed version is not independently public-store confirmed by a fresh observation")
            run_gate(gate, "stage-site", project, site)
            receipt_path = Path("public/release-artwork") / f"{slug}.json"
            receipt = json.loads((site / receipt_path).read_text())
            result.update(status="staged_not_published", expected=receipt,
                          public_store_observations=[{key: row[key] for key in
                            ("release_id", "platform", "version", "store_checked_at", "store_url")}
                            for row in matched],
                          staged_paths=[str(receipt_path)] + [
                              f"src/content/apps/{slug}/assets/screenshots/{asset['site_path']}"
                              for asset in receipt["assets"]])
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            result["reason"] = str(error)
    # The staging header must reflect what was actually staged. The previous
    # unconditional staged_not_published header was misleading when every app
    # was blocked (and the daily Ops workflow subsequently failed).
    staged = sum(app["status"] == "staged_not_published" for app in report["apps"])
    blocked = len(report["apps"]) - staged
    report["staged_count"] = staged
    report["blocked_count"] = blocked
    if not grouped:
        report["status"] = "no_public_store_confirmed_releases"
    elif not staged:
        report["status"] = "blocked_no_candidates"
    elif blocked:
        report["status"] = "partially_staged"
    return report


def stage_git(site: Path, report: dict) -> None:
    paths = []
    for app in report["apps"]:
        if app["status"] != "staged_not_published":
            continue
        slug = app["app_slug"]
        for value in app["staged_paths"]:
            path = Path(value)
            allowed = value == f"public/release-artwork/{slug}.json" or value.startswith(
                f"src/content/apps/{slug}/assets/screenshots/")
            if not SLUG.fullmatch(slug) or path.is_absolute() or ".." in path.parts or not allowed:
                raise ValueError("Unexpected artwork staging path")
            paths.append(value)
    if paths:
        subprocess.run(["git", "-C", str(site), "add", "--", *paths], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "stage-git"))
    parser.add_argument("--releases", type=Path, default=ROOT / "data/app_releases.csv")
    parser.add_argument("--stores", type=Path, default=ROOT / "data/store_versions.csv")
    parser.add_argument("--homepage-repo", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "stage-git":
            stage_git(args.homepage_repo, json.loads(args.report.read_text()))
            return 0
        if not args.work_dir:
            raise ValueError("stage requires --work-dir")
        from isolated_vendored_artwork import sandbox_preflight
        sandbox_preflight()
        report = stage_all(args.releases, args.stores, args.homepage_repo.resolve(),
                           None, args.work_dir.resolve())
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        for app in report["apps"]:
            print(f"{app['app_slug']}: {app['status']} {app.get('reason', '')}")
        # Mandatory live verifier is the terminal gate. Per-app failures remain
        # blocked, while independent valid apps and the existing ops publisher
        # can proceed. No artifact is labelled published at this stage.
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"homepage artwork staging failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
