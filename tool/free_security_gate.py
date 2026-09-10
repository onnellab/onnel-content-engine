#!/usr/bin/env python3
"""Fail-closed security gate using only free local scanners."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

EXIT_BLOCKING = 1
EXIT_USAGE = 2
EXIT_UNVERIFIED = 3

LOCK_NAMES = {
    "Cargo.lock",
    "Gemfile.lock",
    "Podfile.lock",
    "composer.lock",
    "gradle.lockfile",
    "package-lock.json",
    "packages.lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pubspec.lock",
    "requirements.txt",
    "yarn.lock",
}
OSV_SUPPORTED_LOCK_NAMES = LOCK_NAMES - {"Podfile.lock"}
REVIEWABLE_SUFFIXES = {
    ".bash", ".c", ".cc", ".cfg", ".cjs", ".conf", ".cpp", ".cs", ".css",
    ".dart", ".gradle", ".graphql", ".h", ".hpp", ".html", ".java",
    ".js", ".json", ".jsx", ".kt", ".kts", ".m", ".md", ".mm",
    ".mjs", ".mts", ".cts", ".php", ".plist", ".properties", ".py",
    ".rb", ".rs", ".sh", ".sql", ".swift", ".toml", ".ts", ".tsx",
    ".xml", ".yaml", ".yml", ".zsh",
}
REVIEWABLE_NAMES = {"Dockerfile", "Gemfile", "Makefile", "Podfile", "Rakefile"}
SEMGREP_SUFFIXES = {
    ".cjs", ".cts", ".dart", ".java", ".js", ".jsx", ".kt", ".kts",
    ".mjs", ".mts", ".py", ".ts", ".tsx",
}
SEMGREP_RULE_IDS = {
    "onnelab-dart-insecure-certificate-callback",
    "onnelab-java-webview-ssl-error-proceed",
    "onnelab-kotlin-webview-ssl-error-proceed",
    "onnelab-node-tls-reject-unauthorized-false",
    "onnelab-python-requests-verify-false",
}
OPAQUE_NAMES = {
    ".env", "auth.json", "credentials.json", "google-services.json",
    "googleservice-info.plist", "key.properties", "service-account.json",
}
OPAQUE_SUFFIXES = {
    ".der", ".jks", ".key", ".keystore", ".mobileprovision", ".p12",
    ".pem", ".pfx",
}
MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_LOCK_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class Scope:
    names: set[str]
    base_commit: str | None


@dataclass(frozen=True)
class Snapshot:
    files: list[str]
    digest: str
    skipped: dict[str, int]
    incomplete: bool


@dataclass(frozen=True)
class ScannerRun:
    status: int
    findings: list[dict]
    covered: int
    errors: list[dict]


def _repo() -> Path:
    value = (
        os.environ.get("FREE_SECURITY_REPOSITORY")
        if "FREE_SECURITY_REPOSITORY" in os.environ
        else os.environ.get("CODEX_SECURITY_REPOSITORY")
    )
    return Path(value).resolve() if value else Path(__file__).resolve().parent.parent


def _base() -> str | None:
    value = (
        os.environ.get("FREE_SECURITY_DIFF_BASE")
        if "FREE_SECURITY_DIFF_BASE" in os.environ
        else os.environ.get("CODEX_SECURITY_DIFF_BASE")
    )
    return value or None


def _git_z(root: Path, *args: str) -> list[str] | None:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or (result.stdout and not result.stdout.endswith(b"\0")):
        return None
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def _git_text(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None


def _scope(root: Path, mode: str, base: str | None) -> Scope | None:
    top = _git_text(root, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != root.resolve():
        return None
    tracked = _git_z(root, "ls-files", "-z")
    untracked = _git_z(root, "ls-files", "--others", "--exclude-standard", "-z")
    if tracked is None or untracked is None:
        return None
    base_commit = None
    if base:
        base_commit = _git_text(
            root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"
        )
        if not base_commit:
            return None
    if mode == "release":
        names = set(tracked) | set(untracked)
    else:
        comparison = base_commit or "HEAD"
        changed = _git_z(
            root,
            "diff",
            "--name-only",
            "-z",
            "--diff-filter=ACMR",
            comparison,
            "--",
        )
        if changed is None:
            return None
        names = set(changed) | set(untracked)
        names.update(name for name in tracked if Path(name).name in LOCK_NAMES)
    return Scope(names=names, base_commit=base_commit)


def _safe_relative(name: str) -> bool:
    if not name or "\0" in name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _classification(name: str) -> str:
    basename = PurePosixPath(name).name
    lowered = basename.casefold()
    opaque_data_name = Path(lowered).suffix in {
        ".json", ".plist", ".properties", ".toml", ".yaml", ".yml"
    } and lowered.startswith(
        (
            "auth.", "auth-", "auth_", "credential", "secret.", "secret-",
            "secret_", "secrets.", "secrets-", "secrets_", "service-account",
            "service_account", "signing-", "signing_",
        )
    )
    if (
        lowered in OPAQUE_NAMES
        or lowered.startswith(".env.")
        or Path(lowered).suffix in OPAQUE_SUFFIXES
        or opaque_data_name
    ):
        return "opaque"
    if basename in LOCK_NAMES:
        return "lock"
    if basename in REVIEWABLE_NAMES or Path(lowered).suffix in REVIEWABLE_SUFFIXES:
        return "reviewable"
    return "binary_or_unreviewable"


def _has_symlink_component(root: Path, name: str) -> bool:
    current = root
    for part in PurePosixPath(name).parts:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except OSError:
            return False
    return False


def _snapshot(root: Path, names: set[str], destination: Path) -> Snapshot | None:
    copied: list[str] = []
    skipped: dict[str, int] = {}
    digest = hashlib.sha256()
    incomplete = False
    root = root.resolve()
    for name in sorted(names):
        if not _safe_relative(name):
            return None
        kind = _classification(name)
        if kind in {"opaque", "binary_or_unreviewable"}:
            skipped[kind] = skipped.get(kind, 0) + 1
            continue
        if _has_symlink_component(root, name):
            skipped["symlink"] = skipped.get("symlink", 0) + 1
            continue
        source = root.joinpath(*PurePosixPath(name).parts)
        limit = MAX_LOCK_BYTES if kind == "lock" else MAX_SOURCE_BYTES
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source, flags)
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
                    skipped["unscanned_reviewable"] = skipped.get("unscanned_reviewable", 0) + 1
                    incomplete = True
                    continue
                data = stream.read(limit + 1)
        except OSError:
            skipped["unscanned_reviewable"] = skipped.get("unscanned_reviewable", 0) + 1
            incomplete = True
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            skipped["unscanned_reviewable"] = skipped.get("unscanned_reviewable", 0) + 1
            incomplete = True
            continue
        if len(data) > limit or b"\0" in data:
            skipped["unscanned_reviewable"] = skipped.get("unscanned_reviewable", 0) + 1
            incomplete = True
            continue
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest.update(os.fsencode(name) + b"\0" + data)
        copied.append(name)
    return Snapshot(files=copied, digest=digest.hexdigest(), skipped=skipped, incomplete=incomplete)


def _finding(scanner: str, rule_id: str, path: str, line: int | None, severity: str) -> dict:
    return {
        "scanner": scanner,
        "rule_id": rule_id[:160],
        "path": path,
        "line": line if type(line) is int and line > 0 else None,
        "severity": severity,
    }


def _safe_rule_id(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 160:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    return value


def _normalized_path(value: object, allowed: set[str], snapshot: Path | None = None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        if snapshot is None:
            return None
        try:
            value = candidate.resolve().relative_to(snapshot.resolve()).as_posix()
        except (OSError, ValueError):
            return None
    else:
        value = value.removeprefix("./")
    return value if _safe_relative(value) and value in allowed else None


def _parse_semgrep(code: int, value: object | None, expected: set[str]) -> tuple[int, list[dict]]:
    if not isinstance(value, dict) or code not in {0, 1}:
        return EXIT_UNVERIFIED, []
    results = value.get("results")
    errors = value.get("errors")
    paths = value.get("paths")
    skipped_rules = value.get("skipped_rules", [])
    if (
        not isinstance(results, list)
        or errors != []
        or not isinstance(paths, dict)
        or not isinstance(paths.get("scanned"), list)
        or skipped_rules != []
        or value.get("engine_requested") != "OSS"
    ):
        return EXIT_UNVERIFIED, []
    scanned: set[str] = set()
    for raw_path in paths["scanned"]:
        path = _normalized_path(raw_path, expected)
        if path is None:
            return EXIT_UNVERIFIED, []
        scanned.add(path)
    if scanned != expected:
        return EXIT_UNVERIFIED, []
    findings: list[dict] = []
    for item in results:
        if not isinstance(item, dict):
            return EXIT_UNVERIFIED, []
        raw_rule_id = item.get("check_id")
        rule_id = next(
            (
                known
                for known in SEMGREP_RULE_IDS
                if isinstance(raw_rule_id, str) and raw_rule_id.endswith(known)
            ),
            None,
        )
        path = _normalized_path(item.get("path"), expected)
        start = item.get("start")
        extra = item.get("extra")
        if (
            rule_id is None
            or path is None
            or not isinstance(start, dict)
            or type(start.get("line")) is not int
            or start["line"] <= 0
            or not isinstance(extra, dict)
        ):
            return EXIT_UNVERIFIED, []
        severity = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}.get(extra.get("severity"))
        if severity is None:
            return EXIT_UNVERIFIED, []
        findings.append(_finding("semgrep", rule_id, path, start.get("line"), severity))
    expected_code = 1 if findings else 0
    return (EXIT_BLOCKING if findings else 0, findings) if code == expected_code else (EXIT_UNVERIFIED, [])


def _semgrep_diagnostics(code: int, value: object | None, expected: set[str]) -> tuple[list[dict], int]:
    if not isinstance(value, dict):
        return [{"code": "invalid-or-missing-json"}], 0
    paths = value.get("paths")
    raw_scanned = paths.get("scanned") if isinstance(paths, dict) else None
    scanned: set[str] = set()
    if isinstance(raw_scanned, list):
        for item in raw_scanned:
            path = _normalized_path(item, expected)
            if path is not None:
                scanned.add(path)
    if value.get("engine_requested") != "OSS":
        return [{"code": "engine-mismatch"}], len(scanned)
    raw_errors = value.get("errors")
    if isinstance(raw_errors, list) and raw_errors:
        errors: list[dict] = []
        for item in raw_errors:
            error: dict = {"code": "scanner-reported-error"}
            if isinstance(item, dict):
                scanner_code = item.get("code")
                if type(scanner_code) is int:
                    error["scanner_code"] = scanner_code
                elif isinstance(scanner_code, str):
                    safe_code = _safe_rule_id(scanner_code)
                    if safe_code is not None and len(safe_code) <= 40:
                        error["scanner_code"] = safe_code
                path = _normalized_path(item.get("path"), expected)
                if path is not None:
                    error["path"] = path
            errors.append(error)
        return errors, len(scanned)
    missing = sorted(expected - scanned)
    if missing:
        return ([{"code": "coverage-mismatch", "path": path} for path in missing], len(scanned))
    if code not in {0, 1}:
        return [{"code": "scanner-exit", "exit_code": code}], len(scanned)
    if value.get("skipped_rules", []) != []:
        return [{"code": "rules-skipped"}], len(scanned)
    return [{"code": "status-or-schema-mismatch"}], len(scanned)


def _semgrep(snapshot: Path, files: list[str]) -> ScannerRun:
    expected = {name for name in files if Path(name).suffix.casefold() in SEMGREP_SUFFIXES}
    if not expected:
        return ScannerRun(0, [], 0, [])
    rules = Path(__file__).resolve().with_name("security_rules.yml")
    if not rules.is_file() or rules.is_symlink():
        return ScannerRun(
            EXIT_UNVERIFIED, [], 0, [{"code": "trusted-rules-unavailable"}]
        )
    environment = os.environ.copy()
    for key in (
        "SEMGREP_API_KEY",
        "SEMGREP_APP_TOKEN",
        "SEMGREP_BASELINE_COMMIT",
        "SEMGREP_DEPLOYMENT_ID",
        "SEMGREP_JOB_URL",
        "SEMGREP_REPOSITORY",
        "SEMGREP_REPO_NAME",
        "SEMGREP_RULES",
        "SEMGREP_SETTINGS_FILE",
        "SEMGREP_URL",
    ):
        environment.pop(key, None)
    environment["SEMGREP_SEND_METRICS"] = "off"
    command = [
        "semgrep", "scan", "--oss-only", "--config", str(rules), "--metrics=off",
        "--disable-version-check", "--strict", "--error", "--json",
        "--no-git-ignore", "--max-target-bytes", "0",
    ]
    findings: list[dict] = []
    covered = 0
    ordered = sorted(expected)
    for offset in range(0, len(ordered), 100):
        batch = set(ordered[offset : offset + 100])
        result = subprocess.run(
            [*command, *(f"./{name}" for name in sorted(batch))],
            cwd=snapshot,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=600,
            check=False,
        )
        try:
            value = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        status, batch_findings = _parse_semgrep(result.returncode, value, batch)
        if status == EXIT_UNVERIFIED:
            errors, batch_covered = _semgrep_diagnostics(
                result.returncode, value, batch
            )
            return ScannerRun(status, [], covered + batch_covered, errors)
        findings.extend(batch_findings)
        covered += len(batch)
    return ScannerRun(EXIT_BLOCKING if findings else 0, findings, covered, [])


def _gitleaks(snapshot: Path, files: list[str], report_dir: Path) -> tuple[int, list[dict], int]:
    template = report_dir / "gitleaks.tmpl"
    report = report_dir / "gitleaks.metadata"
    config = report_dir / "gitleaks.toml"
    ignore = report_dir / "gitleaks.ignore"
    config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
    ignore.write_text("", encoding="utf-8")
    template.write_text(
        '{{- range . }}{{ printf "%q" .RuleID }}{{ "\\t" }}{{ printf "%q" .File }}{{ "\\t" }}{{ .StartLine }}{{ "\\n" }}{{- end }}',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.pop("GITLEAKS_CONFIG", None)
    environment.pop("GITLEAKS_CONFIG_TOML", None)
    result = subprocess.run(
        [
            "gitleaks", "dir", "--no-banner", "--redact=100", "--exit-code", "1",
            "--config", str(config), "--gitleaks-ignore-path", str(ignore),
            "--ignore-gitleaks-allow",
            "--report-format", "template", "--report-template", str(template),
            "--report-path", str(report), ".",
        ],
        cwd=snapshot,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=600,
        check=False,
    )
    if result.returncode not in {0, 1} or not report.is_file():
        return EXIT_UNVERIFIED, [], 0
    allowed = set(files)
    findings: list[dict] = []
    try:
        records = report.read_text(encoding="utf-8").splitlines()
        for record in records:
            fields = record.split("\t")
            if len(fields) != 3:
                return EXIT_UNVERIFIED, [], 0
            rule_id = _safe_rule_id(json.loads(fields[0]))
            path = _normalized_path(json.loads(fields[1]), allowed, snapshot)
            line = int(fields[2])
            if rule_id is None or path is None or line <= 0:
                return EXIT_UNVERIFIED, [], 0
            findings.append(_finding("gitleaks", rule_id, path, line, "high"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return EXIT_UNVERIFIED, [], 0
    expected_code = 1 if findings else 0
    if result.returncode != expected_code:
        return EXIT_UNVERIFIED, [], 0
    return (EXIT_BLOCKING if findings else 0), findings, len(files)


def _osv_severity(vulnerability: dict) -> str:
    database = vulnerability.get("database_specific")
    raw = database.get("severity") if isinstance(database, dict) else None
    if isinstance(raw, str):
        normalized = raw.casefold()
        return {
            "critical": "critical", "high": "high", "moderate": "medium",
            "medium": "medium", "low": "low",
        }.get(normalized, "unknown")
    return "unknown"


def _parse_osv(
    code: int,
    value: object | None,
    lockfiles: str | set[str],
    snapshot: Path | None = None,
) -> tuple[int, list[dict]]:
    if code not in {0, 1} or not isinstance(value, dict) or not isinstance(value.get("results"), list):
        return EXIT_UNVERIFIED, []
    allowed = {lockfiles} if isinstance(lockfiles, str) else lockfiles
    findings: list[dict] = []
    for result in value["results"]:
        if not isinstance(result, dict):
            return EXIT_UNVERIFIED, []
        source = result.get("source")
        if isinstance(source, dict):
            lockfile = _normalized_path(source.get("path"), allowed, snapshot)
        elif len(allowed) == 1:
            lockfile = next(iter(allowed))
        else:
            lockfile = None
        if lockfile is None:
            return EXIT_UNVERIFIED, []
        packages = result.get("packages", [])
        if not isinstance(packages, list):
            return EXIT_UNVERIFIED, []
        for package in packages:
            if not isinstance(package, dict):
                return EXIT_UNVERIFIED, []
            vulnerabilities = package.get("vulnerabilities", [])
            if not isinstance(vulnerabilities, list):
                return EXIT_UNVERIFIED, []
            for vulnerability in vulnerabilities:
                if not isinstance(vulnerability, dict):
                    return EXIT_UNVERIFIED, []
                rule_id = _safe_rule_id(vulnerability.get("id"))
                if rule_id is None:
                    return EXIT_UNVERIFIED, []
                findings.append(
                    _finding("osv-scanner", rule_id, lockfile, None, _osv_severity(vulnerability))
                )
    expected_code = 1 if findings else 0
    return (EXIT_BLOCKING if findings else 0, findings) if code == expected_code else (EXIT_UNVERIFIED, [])


def _run_osv_command(
    snapshot: Path,
    locks: list[str],
    config: Path,
    output: Path,
) -> tuple[int, object | None]:
    command = ["osv-scanner", "scan", "source", "--config", str(config), "--no-ignore"]
    for name in locks:
        command.extend(("--lockfile", name))
    command.extend(("--format", "json", "--output-file", str(output), "--verbosity", "error"))
    result = subprocess.run(
        command,
        cwd=snapshot,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=600,
        check=False,
    )
    try:
        return result.returncode, json.loads(output.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return result.returncode, None


def _osv_error(code: int, value: object | None, path: str) -> dict:
    if value is None and code == 127:
        error = "invalid-lockfile"
    elif value is None and code == 128:
        error = "empty-dependency-set"
    elif value is None:
        error = "scanner-output-unavailable"
    elif not isinstance(value, dict):
        error = "invalid-json"
    else:
        error = "scanner-contract-failed"
    return {"code": error, "path": path}


def _osv(snapshot: Path, files: list[str], report_dir: Path) -> ScannerRun:
    locks = [name for name in files if PurePosixPath(name).name in LOCK_NAMES]
    if not locks:
        return ScannerRun(0, [], 0, [])
    unsupported = sorted(
        name for name in locks if PurePosixPath(name).name not in OSV_SUPPORTED_LOCK_NAMES
    )
    supported = sorted(set(locks) - set(unsupported))
    errors = [{"code": "unsupported-lockfile", "path": name} for name in unsupported]
    if not supported:
        return ScannerRun(EXIT_UNVERIFIED, [], 0, errors)
    config = report_dir / "osv.toml"
    config.write_text("", encoding="utf-8")
    code, value = _run_osv_command(snapshot, supported, config, report_dir / "osv.json")
    status, findings = _parse_osv(code, value, set(supported), snapshot)
    if status == EXIT_UNVERIFIED:
        if len(supported) == 1:
            errors.append(_osv_error(code, value, supported[0]))
            return ScannerRun(EXIT_UNVERIFIED, [], 0, errors)
        findings = []
        covered = 0
        for index, name in enumerate(supported):
            item_code, item_value = _run_osv_command(
                snapshot, [name], config, report_dir / f"osv-{index}.json"
            )
            item_status, item_findings = _parse_osv(
                item_code, item_value, name, snapshot
            )
            if item_status == EXIT_UNVERIFIED:
                errors.append(_osv_error(item_code, item_value, name))
                continue
            covered += 1
            findings.extend(item_findings)
        return ScannerRun(EXIT_UNVERIFIED, findings, covered, errors)
    if errors:
        return ScannerRun(EXIT_UNVERIFIED, findings, len(supported), errors)
    return ScannerRun(status, findings, len(supported), [])


def _emit(status: str, mode: str, **fields: object) -> int:
    print(json.dumps({"status": status, "mode": mode, **fields}, sort_keys=True))
    return {"clean": 0, "blocking": EXIT_BLOCKING, "unverified": EXIT_UNVERIFIED}[status]


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "quick"
    if len(argv) > 2 or mode not in {"quick", "standard", "release"}:
        print("usage: free_security_gate.py [quick|standard|release]", file=sys.stderr)
        return EXIT_USAGE
    if mode == "quick":
        return _emit("clean", mode, coverage={"policy": "quick-excluded", "target_files": 0})
    root = _repo()
    required = ("git", "gitleaks", "semgrep", "osv-scanner")
    if not root.is_dir() or any(shutil.which(tool) is None for tool in required):
        return _emit("unverified", mode, reason="missing-tool-or-repository")
    try:
        scope = _scope(root, mode, _base())
    except subprocess.SubprocessError:
        scope = None
    if scope is None:
        return _emit("unverified", mode, reason="invalid-repository-or-diff-base")
    try:
        with tempfile.TemporaryDirectory(prefix="onnellab-free-security-") as temporary:
            temp = Path(temporary)
            os.chmod(temp, 0o700)
            snapshot_dir = temp / "snapshot"
            report_dir = temp / "reports"
            snapshot_dir.mkdir(mode=0o700)
            report_dir.mkdir(mode=0o700)
            snapshot = _snapshot(root, scope.names, snapshot_dir)
            if snapshot is None:
                return _emit("unverified", mode, reason="unsafe-scope-path")
            if snapshot.incomplete or not snapshot.files:
                return _emit(
                    "unverified", mode, reason="incomplete-or-empty-reviewable-scope",
                    scope_hash=snapshot.digest, input_files=len(snapshot.files), skipped=snapshot.skipped,
                )
            g_status, g_findings, g_covered = _gitleaks(snapshot_dir, snapshot.files, report_dir)
            semgrep_run = _semgrep(snapshot_dir, snapshot.files)
            osv_run = _osv(snapshot_dir, snapshot.files, report_dir)
    except (OSError, subprocess.SubprocessError):
        return _emit("unverified", mode, reason="scanner-execution-failed")
    statuses = [g_status, semgrep_run.status, osv_run.status]
    status = "unverified" if EXIT_UNVERIFIED in statuses else "blocking" if EXIT_BLOCKING in statuses else "clean"
    scanner_names = ("gitleaks", "semgrep", "osv-scanner")
    scanner_targets = (len(snapshot.files), sum(Path(name).suffix.casefold() in SEMGREP_SUFFIXES for name in snapshot.files), len([name for name in snapshot.files if PurePosixPath(name).name in LOCK_NAMES]))
    scanner_covered = (g_covered, semgrep_run.covered, osv_run.covered)
    scanner_statuses = ["unverified" if item == EXIT_UNVERIFIED else "blocking" if item == EXIT_BLOCKING else "clean" for item in statuses]
    scanners = {
        name: {
            "status": state,
            "target_files": target,
            "covered_files": covered,
            "errors": (
                osv_run.errors
                if name == "osv-scanner"
                else semgrep_run.errors
                if name == "semgrep"
                else ([{"code": "scanner-contract-failed"}] if state == "unverified" else [])
            ),
        }
        for name, state, target, covered in zip(scanner_names, scanner_statuses, scanner_targets, scanner_covered)
    }
    return _emit(
        status,
        mode,
        base_commit=scope.base_commit,
        scope_hash=snapshot.digest,
        input_files=len(snapshot.files),
        skipped=snapshot.skipped,
        scanners=scanners,
        findings=g_findings + semgrep_run.findings + osv_run.findings,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
