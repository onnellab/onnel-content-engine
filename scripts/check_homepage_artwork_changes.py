#!/usr/bin/env python3
"""Detect real reviewed artwork changes before the automatic publisher can run.

This is a local-only preflight for the existing automatic-artwork-only path.
The existing manual publisher is unchanged. Approved app checkouts reuse the
read step's already-bound credential; isolated app-vendored gates validate
reviewed evidence without private-template access. This helper never commits,
pushes, renders, approves candidates, or requests credentials/permissions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from isolated_vendored_artwork import sandbox_preflight
from sync_homepage_release_artwork import stage_all
from verify_homepage_release_artwork import LOCALES

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = Path("data/artwork-change-trigger.json")
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
RUN_ID = re.compile(r"[1-9][0-9]*")
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9]+)?")
RECEIPT_PATH = re.compile(rf"public/release-artwork/{SLUG}\.json")
IMAGE_PATH = re.compile(rf"src/content/apps/{SLUG}/assets/screenshots/[A-Za-z]+(?:-[A-Za-z]+)?/[A-Za-z0-9_-]+\.png")
APP_KEYS = {"app_slug", "candidate_sha256", "version", "source_commit"}


class PreflightBlocked(ValueError):
    """A required read-only dependency failed; never a successful no-op."""

    def __init__(self, report: dict):
        super().__init__(report["reason"])
        self.report = report


def matches(pattern: re.Pattern | str, value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def app_identity(value: object) -> dict:
    if not isinstance(value, dict) or not all((
        matches(SLUG, value.get("app_slug")),
        matches(SHA256, value.get("candidate_sha256")),
        matches(VERSION, value.get("version")),
        matches(COMMIT, value.get("source_commit")),
    )):
        raise ValueError("Invalid staged artwork identity")
    return {key: value[key] for key in sorted(APP_KEYS)}


def gate_auto_publication(trigger: object, source_run_id: str, source_run_attempt: str) -> bool:
    """Fail closed unless a complete sanitized receipt belongs to this run.

    The caller applies this only to the automatic-artwork-only run title.
    Ordinary manual publication must not depend on this gate.
    """
    if (not matches(RUN_ID, source_run_id) or not matches(RUN_ID, source_run_attempt)
            or not isinstance(trigger, dict)
            or set(trigger) != {"schema_version", "run_id", "run_attempt", "status", "apps"}
            or type(trigger.get("schema_version")) is not int
            or trigger["schema_version"] != 1
            or trigger.get("run_id") != source_run_id
            or trigger.get("run_attempt") != source_run_attempt
            or trigger.get("status") != "artwork_changed"
            or not isinstance(trigger.get("apps"), list) or not trigger["apps"]):
        return False
    seen = set()
    try:
        for app in trigger["apps"]:
            identity = app_identity(app)
            if set(app) != APP_KEYS or identity["app_slug"] in seen:
                return False
            seen.add(identity["app_slug"])
    except (TypeError, ValueError):
        return False
    return True


def safe_file(root: Path, relative: str) -> Path:
    """Never follow a symlink, even one that points back inside the checkout."""
    part = Path(relative)
    if part.is_absolute() or str(part) != relative or any(p in {"..", "."} for p in part.parts):
        raise ValueError("Unsafe artwork file path")
    path = root
    for component in part.parts:
        path = path / component
        if path.is_symlink():
            raise ValueError("Symlink in artwork file path")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artwork file escaped checkout")
    if path.exists() and not path.is_file():
        raise ValueError("Artwork destination is not a regular file")
    return path


def git_names(site: Path, *args: str) -> set[str]:
    raw = subprocess.check_output(["git", "--literal-pathspecs", "-C", str(site), *args],
                                  stderr=subprocess.PIPE, timeout=60)
    return {name.decode("utf-8") for name in raw.split(b"\0") if name}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(site: Path) -> dict[str, tuple[str, object]]:
    """Snapshot only bounded artwork files, not Ops/status or unrelated paths.

    Untracked (including ignored) pre-existing artwork is included so merely
    rewriting it cannot manufacture a change. Git's post-stage diff below is a
    second check that a candidate actually differs from the tracked site.
    """
    names = git_names(site, "ls-files", "-z", "--cached", "--others")
    before = {}
    for name in names:
        if not (RECEIPT_PATH.fullmatch(name) or IMAGE_PATH.fullmatch(name)):
            continue
        try:
            path = safe_file(site, name)
            if not path.is_file():
                continue
            raw = path.read_bytes()
        except (OSError, ValueError):
            # Unselected apps must not block independent valid releases. The
            # shared gate rejects unsafe destinations before writing, and each
            # successful app is checked again by expected_paths below.
            continue
        identity = None
        if RECEIPT_PATH.fullmatch(name):
            try:
                identity = app_identity(json.loads(raw))
            except (ValueError, TypeError):
                pass
        before[name] = (digest(raw), identity)
    return before


def expected_paths(app: dict, site: Path) -> tuple[dict, list[str]]:
    """Bind exact expected receipt/image files to the shared gate's report."""
    receipt = app.get("expected")
    identity = app_identity(receipt)
    slug = identity["app_slug"]
    if app.get("app_slug") != slug or receipt.get("status") != "staged_not_published":
        raise ValueError("Staging report identity or status mismatch")
    if not isinstance(receipt.get("assets"), list) or not receipt["assets"]:
        raise ValueError("Staging report has no expected images")
    receipt_name = f"public/release-artwork/{slug}.json"
    paths = [receipt_name]
    for asset in receipt["assets"]:
        if not isinstance(asset, dict):
            raise ValueError("Invalid expected image")
        locale, relative = asset.get("locale"), asset.get("site_path")
        if (not isinstance(locale, str) or locale not in LOCALES
                or not matches(re.escape(locale) + r"/[A-Za-z0-9_-]+\.png", relative)
                or not matches(SHA256, asset.get("sha256"))):
            raise ValueError("Unsafe or invalid expected image path/hash")
        name = f"src/content/apps/{slug}/assets/screenshots/{relative}"
        if name in paths:
            raise ValueError("Duplicate expected artwork path")
        path = safe_file(site, name)
        if not path.is_file() or digest(path.read_bytes()) != asset["sha256"]:
            raise ValueError("Staged image does not match expected bytes")
        paths.append(name)
    staged_paths = app.get("staged_paths")
    if (not isinstance(staged_paths, list) or not all(isinstance(p, str) for p in staged_paths)
            or len(staged_paths) != len(paths) or set(staged_paths) != set(paths)):
        raise ValueError("Staging report paths differ from exact expected artwork files")
    actual = json.loads(safe_file(site, receipt_name).read_bytes())
    if actual != receipt:
        raise ValueError("Staged receipt differs from shared gate result")
    return identity, paths


def changed_apps(site: Path, before: dict, report: dict) -> list[dict]:
    apps = report.get("apps")
    if not isinstance(apps, list):
        raise ValueError("Malformed shared artwork staging report")
    seen = set()
    changes = []
    for app in apps:
        if not isinstance(app, dict):
            raise ValueError("Malformed shared artwork app result")
        if app.get("status") != "staged_not_published":
            # Preserve blocked app reasons from the existing shared-gate flow.
            continue
        try:
            identity, paths = expected_paths(app, site)
            slug = identity["app_slug"]
            if slug in seen:
                raise ValueError("Duplicate staged artwork app")
            seen.add(slug)
            pending = git_names(site, "diff", "--name-only", "--no-renames", "-z", "HEAD", "--", *paths)
            pending |= git_names(site, "ls-files", "--others", "--exclude-standard", "-z", "--", *paths)
            changed = [name for name in paths if name in pending and
                       before.get(name, (None, None))[0] != digest(safe_file(site, name).read_bytes())]
            # Receipt formatting/observation timestamps alone are not artwork.
            # A new receipt, changed reviewed candidate, or changed image bytes
            # must accompany a real Git difference made by this preflight.
            old_identity = before.get(paths[0], (None, None))[1]
            candidate_changed = (paths[0] in changed and (old_identity is None or
                                 old_identity["candidate_sha256"] != identity["candidate_sha256"]))
            app["changed"] = candidate_changed or any(name != paths[0] for name in changed)
            app["changed_paths"] = changed if app["changed"] else []
            if app["changed"]:
                changes.append(identity)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            # Never echo checkout/subprocess stderr, which can include auth data.
            app.update(status="blocked", changed=False,
                       reason="Staged artwork could not be verified against exact allowed site files")
    return sorted(changes, key=lambda app: app["app_slug"])


def write_json_if_changed(path: Path, value: dict) -> bool:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if path.is_symlink():
        raise ValueError("Output must not be a symlink")
    if path.exists() and path.read_bytes() == raw:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".artwork-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def stage_changes(site: Path, run_id: str, run_attempt: str, work_dir: Path, trigger: Path, *,
                  releases: Path | None = None, stores: Path | None = None) -> dict:
    if not matches(RUN_ID, run_id) or not matches(RUN_ID, run_attempt):
        raise ValueError("Expected positive numeric source run ID and attempt")
    canonical_trigger = safe_file(ROOT.resolve(), TRIGGER.as_posix())
    if trigger.absolute() != canonical_trigger.absolute():
        raise ValueError("Only data/artwork-change-trigger.json may be written as the trigger")
    site = site.resolve(strict=True)
    before = snapshot(site)
    work_dir.mkdir(parents=True, exist_ok=True)
    # Every invocation gets a fresh directory for approved app checkouts,
    # including reruns. Prove isolation before any app-vendored gate can run.
    with tempfile.TemporaryDirectory(prefix="artwork-change-", dir=work_dir) as directory:
        work = Path(directory)
        try:
            sandbox_preflight()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            # Keep denied/unavailable isolation visible. Do not retry without
            # the sandbox or obtain another repository/credential/permission.
            raise PreflightBlocked({
                "schema_version": 1, "run_id": run_id, "run_attempt": run_attempt,
                "status": "blocked", "changed": False, "apps": [],
                "reason": f"Artwork sandbox unavailable ({type(error).__name__})",
            }) from error
        report = stage_all(releases or ROOT / "data/app_releases.csv",
                           stores or ROOT / "data/store_versions.csv", site, None, work / "apps")
    changes = changed_apps(site, before, report)
    report.update(run_id=run_id, run_attempt=run_attempt, changed=bool(changes))
    report["status"] = "artwork_changed" if changes else "no_artwork_changes"
    if changes:
        receipt = {"schema_version": 1, "run_id": run_id, "run_attempt": run_attempt,
                   "status": "artwork_changed", "apps": changes}
        if not gate_auto_publication(receipt, run_id, run_attempt):
            raise ValueError("Generated artwork trigger failed validation")
        write_json_if_changed(canonical_trigger, receipt)
    # A no-op never writes/deletes an old trigger or generates timestamp state.
    return report


def github_output(path: Path | None, key: str, value: bool) -> None:
    if path is not None:
        if path.is_symlink():
            raise ValueError("GitHub output must not be a symlink")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{key}={'true' if value else 'false'}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    stage = sub.add_parser("stage", help="Preflight the automatic-artwork-only path locally")
    stage.add_argument("--site", type=Path, required=True)
    stage.add_argument("--run-id", required=True)
    stage.add_argument("--run-attempt", required=True)
    stage.add_argument("--work-dir", type=Path, required=True)
    stage.add_argument("--trigger", type=Path, default=ROOT / TRIGGER)
    stage.add_argument("--report", type=Path, required=True)
    stage.add_argument("--github-output", type=Path)
    authorize = sub.add_parser("authorize", help="Check the automatic publisher's exact source run")
    authorize.add_argument("--trigger", type=Path, default=ROOT / TRIGGER)
    authorize.add_argument("--source-run-id", required=True)
    authorize.add_argument("--source-run-attempt", required=True)
    authorize.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        # Output/report aliases must not mutate the authorization receipt,
        # including through .. or symlinked parent paths on a no-op run.
        if args.github_output is not None and args.github_output.resolve() == args.trigger.resolve():
            raise ValueError("GitHub output and trigger destinations must differ")
        if args.action == "authorize":
            try:
                receipt = json.loads(args.trigger.read_bytes()) if not args.trigger.is_symlink() else None
            except (OSError, ValueError):
                receipt = None
            authorized = gate_auto_publication(receipt, args.source_run_id, args.source_run_attempt)
            github_output(args.github_output, "authorized", authorized)
            print("Automatic artwork publication authorized" if authorized else
                  "Automatic artwork publication skipped: no valid trigger for this source run")
            return 0
        if args.report.resolve() == args.trigger.resolve():
            raise ValueError("Report and trigger destinations must differ")
        if args.github_output is not None and args.github_output.resolve() == args.report.resolve():
            raise ValueError("GitHub output and report destinations must differ")
        try:
            report = stage_changes(args.site, args.run_id, args.run_attempt, args.work_dir, args.trigger)
        except PreflightBlocked as error:
            write_json_if_changed(args.report, error.report)
            github_output(args.github_output, "changed", False)
            print(error.report["reason"], file=sys.stderr)
            return 1
        write_json_if_changed(args.report, report)
        github_output(args.github_output, "changed", report["changed"])
        print("Reviewed artwork changes found" if report["changed"] else "No reviewed artwork changes")
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        # Fail closed without exposing a clone's URL, token or authentication
        # diagnostics. Failed steps cannot become publication authorization.
        print(f"Artwork change preflight failed ({type(error).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
