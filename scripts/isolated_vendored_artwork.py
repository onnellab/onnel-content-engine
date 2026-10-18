#!/usr/bin/env python3
"""Run exact, engine-allowlisted app-vendored artwork gates in a closed sandbox.

The public engine contains hashes, never private-template implementation code.
An app's provenance declaration is checked against that independent allowlist;
it cannot authorize new code. No template checkout or unisolated fallback exists.
Only verification and local website staging are exposed, never capture/render.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "data/canonical_artwork_hashes.json"
VENDORED = Path("assets/store_promo/onnellab_shared_v20261011")
GATE_SHA256 = "7d28497c40140d8a5f55577c327be1edd258554fedb838f35aa6befb470b1391"
ROOT_ADAPTER = Path("assets/store_promo/release_artwork.py")
ROOT_ADAPTER_SHA256 = "55c9afcbc66bf13b3e5f7033f0358b5ecfb146a740e6c445253fac05e769846c"
# Two individually reviewed, indivisible bundles. Source aliases are accepted
# only for the exact corresponding complete map, never interchangeable files.
BUNDLE_PINS = {
    "legacy_v20261011": {
        "source_commits": frozenset({"b6d2332c162a00285c3aa05186a47c0f6b18f5b4",
                                     "e1744e271c6d669441e7ed35f97e109c990c14fc"}),
        "gate_sha256": "9364e6e4db207e8c290fd3dba8e29f3d19f582aab5389e9ca527b25225445e4e",
        "file_map_sha256": "e19c7f63242e270cffea804249081d7b189885ce5fb9d8513b1e92d47d66b9fd",
    },
    "unchanged_screen_v20261018": {
        "source_commits": frozenset({"0d8a37eefa4283e82e2c7ea803580a7c5eed1835"}),
        "gate_sha256": GATE_SHA256,
        "file_map_sha256": "ba0baadc8895e9883c0a208b9e730a0df0d20b562346a31645e9768da57be16e",
    },
}
SOURCE_COMMITS = frozenset(commit for pin in BUNDLE_PINS.values() for commit in pin["source_commits"])
BWRAP = Path("/usr/bin/bwrap")
PYTHON = Path("/usr/bin/python3")
MAX_FILE_BYTES = 2 * 1024 * 1024
CHILD_ENV = {"PATH": "/usr/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
             "TMPDIR": "/tmp", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_ATTR_NOSYSTEM": "1",
             "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
             "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
             "GIT_CONFIG_VALUE_0": "/app"}
LAUNCH_ENV = {"PATH": "/usr/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
GIT_CONFIG = ("[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
              "\tfilemode = true\n\thooksPath = /dev/null\n\tfsmonitor = false\n")

# This is engine-owned startup code, not implementation copied from the template.
# -S also excludes sitecustomize and third-party site packages from /usr.
BOOTSTRAP = '''import os, pathlib, runpy, sys
sys.path[:] = ["/gate"] + [p for p in sys.path if p.startswith("/usr/")]
if not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode:
    raise RuntimeError("Isolated Python startup is required")
action, project = sys.argv[1:3]
if action not in {"verify-site", "stage-site"}:
    raise RuntimeError("Unsupported artwork action")
if project != "/app" and not project.startswith("/app/"):
    raise RuntimeError("Unsafe project mount")
paths = [".", ":(exclude)assets/store_promo/**", ":(exclude)release/artwork*.json",
         ":(exclude)assets/onnellab_release_identity.json"]
allowed_git = [["git", "-C", project, "diff", "HEAD", "--name-only", "--", *paths],
               ["git", "-C", project, "log", "-1", "--format=%H", "--", *paths]]
def audit(event, args):
    if event == "subprocess.Popen":
        executable, argv, cwd, env = args
        if executable != "git" or argv not in allowed_git or env is not None:
            raise RuntimeError("Only source-identity Git reads are allowed")
    elif event in {"os.system", "os.exec", "os.posix_spawn", "os.forkpty"}:
        raise RuntimeError("Unexpected process execution is forbidden")
sys.addaudithook(audit)
sys.argv = ["/gate/release_artwork.py", action, "--project", project]
if action == "stage-site":
    sys.argv += ["--site", "/site"]
runpy.run_path("/gate/release_artwork.py", run_name="__main__")
'''

SELF_TEST = '''import errno, json, os, pathlib, socket, sys
expected_env = json.loads(sys.argv[1])
parent_net, parent_pid, hidden = sys.argv[2:5]
if dict(os.environ) != expected_env:
    raise RuntimeError("Sandbox environment differs from the fixed allowlist")
if os.readlink("/proc/self/ns/net") == parent_net or os.readlink("/proc/self/ns/pid") == parent_pid:
    raise RuntimeError("Network or PID namespace was not isolated")
if not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode:
    raise RuntimeError("Python startup is not isolated")
if any(p in {"", "/app", "/gate"} for p in sys.path):
    raise RuntimeError("Application directory was added to the import path")
for path in ("/home", "/root", "/workspace", "/site", hidden):
    if pathlib.Path(path).exists():
        raise RuntimeError("Unexpected host path is visible: " + path)
for path in ("/app/sandbox-write-probe", "/gate/sandbox-write-probe", "/usr/sandbox-write-probe"):
    try:
        pathlib.Path(path).write_text("must not be written")
    except OSError as exc:
        if exc.errno != errno.EROFS:
            raise RuntimeError("Mount is not demonstrably read-only") from exc
    else:
        raise RuntimeError("Read-only mount was writable")
if "SECRET" in pathlib.Path("/app/.git/config").read_text():
    raise RuntimeError("Checkout Git credentials were not hidden")
# Only loopback may exist; no route can reach the host or an external network.
routes = pathlib.Path("/proc/net/route").read_text().splitlines()[1:]
if any(line.split()[0] != "lo" for line in routes if line.split()):
    raise RuntimeError("Sandbox has an external network route")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
    connection.settimeout(1)
    if connection.connect_ex(("192.0.2.1", 9)) == 0:
        raise RuntimeError("Sandbox unexpectedly reached an external address")
print("ARTWORK_SANDBOX_OK")
'''


@dataclass(frozen=True)
class ValidatedBundle:
    repository_root: Path
    project_relative: PurePosixPath
    source_commit: str
    file_hashes: dict[str, str]
    files: dict[str, bytes]


def _no_symlink_path(path: Path) -> Path:
    """Check the lexical path before resolve(), including every ancestor."""
    if ".." in Path(path).parts:
        raise ValueError("Parent traversal paths are not accepted")
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Symlink paths are not accepted: {part}")
    return path.resolve(strict=True)


def _read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        with os.fdopen(os.open(path, flags), "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                raise ValueError(f"Expected a bounded regular file: {path.name}")
            data = handle.read(MAX_FILE_BYTES + 1)
    except OSError as error:
        raise ValueError(f"Cannot read regular artwork file: {path.name}") from error
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Artwork dependency exceeds the size limit")
    return data


def _json(data: bytes) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Duplicate JSON key: {key}")
            value[key] = item
        return value
    value = json.loads(data, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Expected an artwork JSON object")
    return value


def _file_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError("Canonical file hashes are missing")
    for name, digest in value.items():
        if (not isinstance(name, str)
                or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:py|svg|json|md)", name)
                or ".." in name or not isinstance(digest, str)
                or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("Unsafe canonical file name or hash")
    return value


def load_allowlist() -> dict:
    data = _json(_read_regular(_no_symlink_path(ALLOWLIST)))
    if (set(data) != {"schema_version", "repository", "source_directory", "bundles", "root_adapter"}
            or type(data.get("schema_version")) is not int or data["schema_version"] != 2
            or data.get("repository") != "onnellab/onnellab-flutter-template"
            or data.get("source_directory") != "template/assets/store_promo"
            or not isinstance(data.get("bundles"), dict)
            or set(data["bundles"]) != set(BUNDLE_PINS)):
        raise ValueError("Unrecognized canonical artwork allowlist")
    seen_sources = set()
    for name, pin in BUNDLE_PINS.items():
        bundle = data["bundles"][name]
        if (not isinstance(bundle, dict) or set(bundle) != {"source_commits", "sha256"}
                or not isinstance(bundle["source_commits"], list)
                or not all(isinstance(source, str) for source in bundle["source_commits"])
                or set(bundle["source_commits"]) != pin["source_commits"]
                or len(bundle["source_commits"]) != len(pin["source_commits"])
                or seen_sources.intersection(bundle["source_commits"])):
            raise ValueError("Canonical bundle source pins differ from reviewed sources")
        seen_sources.update(bundle["source_commits"])
        hashes = _file_map(bundle["sha256"])
        fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (len(hashes) != 27 or hashes.get("release_artwork.py") != pin["gate_sha256"]
                or fingerprint != pin["file_map_sha256"]):
            raise ValueError("Canonical bundle file map differs from the complete reviewed bundle")
    if data.get("root_adapter") != {"path": ROOT_ADAPTER.as_posix(), "sha256": ROOT_ADAPTER_SHA256}:
        raise ValueError("Canonical root adapter differs from the reviewed thin shim")
    return data


def _repository(project: Path) -> Path:
    for ancestor in (project, *project.parents):
        git = ancestor / ".git"
        if git.exists() or git.is_symlink():
            if git.is_symlink() or not git.is_dir():
                raise ValueError("Expected a fresh standalone Git checkout, not a linked worktree")
            if not (git / "HEAD").is_file() or not (git / "objects").is_dir():
                raise ValueError("Incomplete app Git checkout")
            for name in ("commondir", "config.worktree", "objects/info/alternates", "objects/info/http-alternates"):
                if (git / name).exists() or (git / name).is_symlink():
                    raise ValueError("External or worktree Git metadata is not supported")
            return ancestor
    raise ValueError("App must be inside a fresh cloned Git repository")


def _regular_tree(root: Path) -> None:
    """Fresh clone only: no symlink escapes, sockets, devices, or FIFOs."""
    def failed(error):
        raise error
    for directory, folders, files in os.walk(root, followlinks=False, onerror=failed):
        for name in (*folders, *files):
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"Non-regular or symlink checkout path: {path.relative_to(root)}")


def validate_vendored_bundle(project: Path) -> ValidatedBundle:
    project = _no_symlink_path(project)
    if not project.is_dir() or not (project / "pubspec.yaml").is_file():
        raise ValueError("Artwork project must be an existing Flutter app")
    repository = _repository(project)
    _regular_tree(repository)
    relative = PurePosixPath(project.relative_to(repository).as_posix())
    bundle = _no_symlink_path(project / VENDORED)
    if not bundle.is_dir():
        raise ValueError("Canonical vendored artwork directory is missing")
    ledger = load_allowlist()
    # A custom root gate may impose additional app-specific safety checks.
    # Never bypass it by running a generic vendored copy, even when that copy
    # itself is canonical. A separately reviewed bridge is required first.
    adapter = _read_regular(project / ROOT_ADAPTER)
    if hashlib.sha256(adapter).hexdigest() != ROOT_ADAPTER_SHA256:
        raise ValueError("Unsupported custom root artwork gate; a separately reviewed bridge is required")
    metadata = _json(_read_regular(bundle / "TEMPLATE_SOURCE.json"))
    legacy_keys = {"repository", "commit", "sha256"}
    rich_keys = legacy_keys | {"source_directory", "preserved_safety_hardening"}
    if set(metadata) not in (legacy_keys, rich_keys):
        raise ValueError("Unsupported vendored source metadata shape")
    if (metadata.get("repository") != ledger["repository"]
            or (set(metadata) == rich_keys and (
                metadata["source_directory"] != ledger["source_directory"]
                or metadata["preserved_safety_hardening"] != []))):
        raise ValueError("Vendored source pin or custom hardening is not approved for this gate")
    selected = [entry for entry in ledger["bundles"].values()
                if metadata.get("commit") in entry["source_commits"]]
    if len(selected) != 1:
        raise ValueError("Vendored source pin is not uniquely approved for this gate")
    approved = selected[0]["sha256"]
    if _file_map(metadata.get("sha256")) != approved:
        raise ValueError("App-declared hashes differ from the independent canonical allowlist")
    # Do not merely search for .py: native libraries, .pth, bytecode, packages,
    # extensionless executables and unusual names must also fail closed.
    allowed = set(approved) | {"TEMPLATE_SOURCE.json", "SYNC_STATUS.md"}
    actual = {path.name for path in bundle.iterdir()}
    if actual - allowed:
        raise ValueError(f"Unexpected vendored code or file: {sorted(actual - allowed)}")
    if set(approved) - actual:
        raise ValueError(f"Missing canonical dependencies: {sorted(set(approved) - actual)}")
    files = {}
    for name, expected in approved.items():
        payload = _read_regular(bundle / name)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"Noncanonical artwork dependency: {name}")
        files[name] = payload
    if "SYNC_STATUS.md" in actual:
        _read_regular(bundle / "SYNC_STATUS.md")
    return ValidatedBundle(repository, relative, metadata["commit"], dict(approved), files)


def _runtime() -> None:
    if not sys.platform.startswith("linux"):
        raise ValueError("Artwork verification requires the Linux bubblewrap sandbox")
    for executable in (BWRAP, PYTHON):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError(f"Required sandbox executable is unavailable: {executable}; no unisolated fallback")


def _sandbox_command(repository: Path, bundle: Path, bootstrap: Path, git_config: Path,
                     arguments: list[str], *, project_relative: PurePosixPath = PurePosixPath("."),
                     site: Path | None = None) -> list[str]:
    _runtime()
    # Bubblewrap --clearenv retains PWD; remove it without loosening CHILD_ENV.
    command = [str(BWRAP), "--die-with-parent", "--new-session", "--unshare-user",
               "--unshare-pid", "--unshare-net", "--unshare-ipc", "--unshare-uts",
               "--unshare-cgroup", "--disable-userns", "--cap-drop", "ALL", "--clearenv",
               "--unsetenv", "PWD"]
    for name in ("/usr", "/lib", "/lib64"):
        if Path(name).exists():
            command += ["--ro-bind", name, name]
    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--ro-bind", str(repository), "/app", "--ro-bind", str(bundle), "/gate",
                "--ro-bind", str(bootstrap), "/bootstrap.py",
                "--ro-bind", str(git_config), "/app/.git/config"]
    if site is not None:
        command += ["--bind", str(site), "/site"]
        # actions/checkout normally persists a token in .git/config. The gate
        # never needs website Git metadata; hide all of it, including worktrees.
        if (site / ".git").exists():
            if (site / ".git").is_dir():
                command += ["--tmpfs", "/site/.git", "--remount-ro", "/site/.git"]
            else:
                command += ["--ro-bind", str(git_config), "/site/.git"]
    for key, value in CHILD_ENV.items():
        command += ["--setenv", key, value]
    project = str(PurePosixPath("/app") / project_relative)
    return command + ["--chdir", project, "--", str(PYTHON), "-I", "-S", "-B", "/bootstrap.py", *arguments]


def _run(command: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, env=dict(LAUNCH_ENV), cwd="/", stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                timeout=timeout, close_fds=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"Artwork sandbox could not run ({type(error).__name__}); no unisolated fallback") from None
    if result.returncode:
        # This engine can publish diagnostics to public CI. Never forward child
        # output: an unexpected traceback contains private canonical source, and
        # even handled evidence errors can quote app-owned content or paths.
        output = (result.stderr or "") + (result.stdout or "")
        category = "sandbox_or_canonical_validation_failed"
        for marker, value in (
                ("Independent visual review missing/stale/incomplete", "independent_review_required"),
                ("Artwork candidate is stale", "artwork_candidate_stale"),
                ("Stale capture version/commit", "capture_source_stale"),
                ("Missing genuine device/locale validation", "capture_evidence_missing"),
                ("ARTWORK RELEASE BLOCKED:", "canonical_evidence_rejected"),
                ("bwrap:", "sandbox_startup_failed")):
            if marker in output:
                category = value
                break
        raise ValueError(f"Artwork sandbox blocked: {category} (exit {result.returncode}); no unisolated fallback")
    return result


def _self_test_failure(stderr: str) -> dict[str, str]:
    """Classify trusted public probe failures, never return captured text/paths.

    These signatures come from upstream bubblewrap v0.9.0 and SELF_TEST. A
    permission error alone cannot establish that AppArmor caused the failure.
    This classifier is deliberately separate from the private gate sanitizer.
    """
    lines = [line.lower() for line in stderr.splitlines() if line.startswith("bwrap:")]
    text = "\n".join(lines)
    category = "self_test_program_failed" if not lines else "bwrap_startup_unclassified"
    signatures = (
        (("unknown option",), "bwrap_option_unsupported"),
        (("requires --", "not compatible", "takes one argument", "takes two arguments"), "bwrap_arguments_invalid"),
        (("loopback:", "netlink_route"), "network_namespace_setup_failed"),
        (("cgroup namespace", "stat on /proc/self/ns/cgroup failed"), "cgroup_namespace_setup_failed"),
        (("kernel does not support user namespaces",), "user_namespace_unsupported"),
        (("max_*_namespaces exceeded", "nesting depth"), "namespace_limit_exceeded"),
        (("no permissions to creating new namespace", "no permissions to create a new namespace"), "namespace_creation_denied"),
        (("creating new namespace failed",), "namespace_creation_failed"),
        (("setting up uid map", "setting up gid map", "setgroups"), "user_namespace_id_map_failed"),
        (("max_user_namespaces", "sysctl user.max_user_namespaces", "unshare user ns"), "nested_user_namespace_setup_failed"),
        (("can't find source path", "can't get type of source"), "sandbox_mount_source_unavailable"),
        (("can't mount", "can't bind mount", "can't remount", "mounting"), "sandbox_mount_setup_failed"),
        (("can't mkdir", "can't create file", "can't make symlink"), "sandbox_destination_setup_failed"),
        (("chdir", "change directory"), "sandbox_working_directory_failed"),
        (("execvp",), "sandbox_interpreter_exec_failed"),
    )
    for markers, value in signatures:
        if any(marker in text for marker in markers):
            category = value
            break
    if not lines:
        assertions = (
            ("Sandbox environment differs", "self_test_environment_failed"),
            ("namespace was not isolated", "self_test_namespace_isolation_failed"),
            ("Python startup is not isolated", "self_test_interpreter_isolation_failed"),
            ("import path", "self_test_import_isolation_failed"),
            ("host path is visible", "self_test_filesystem_visibility_failed"),
            ("read-only", "self_test_readonly_mount_failed"),
            ("Read-only", "self_test_readonly_mount_failed"),
            ("Git credentials were not hidden", "self_test_git_metadata_failed"),
            ("external network", "self_test_network_isolation_failed"),
            ("external address", "self_test_network_isolation_failed"),
        )
        category = next((value for marker, value in assertions if marker in stderr), category)
    error = next((value for marker, value in (
        ("operation not permitted", "EPERM"), ("permission denied", "EACCES"),
        ("no such file or directory", "ENOENT"), ("read-only file system", "EROFS"),
        ("invalid argument", "EINVAL"), ("no space left on device", "ENOSPC"))
        if marker in text), "unclassified")
    return {"category": category, "errno_hint": error}


def _self_test_host_capabilities() -> dict:
    """Read fixed public host facts; never mutate security or create a sandbox."""
    facts = {}
    for option in ("--version", "--help"):
        try:
            result = subprocess.run([str(BWRAP), option], env=dict(LAUNCH_ENV), cwd="/",
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, timeout=5, close_fds=True)
            output = result.stdout if result.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            output = ""
        if option == "--version":
            match = re.fullmatch(r"bubblewrap ([0-9]{1,3}(?:\.[0-9]{1,3}){1,3})\s*", output)
            facts["bwrap_version"] = match[1] if match else "unavailable"
        else:
            required = ("--die-with-parent", "--new-session", "--unshare-user", "--unshare-pid",
                        "--unshare-net", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup",
                        "--disable-userns", "--cap-drop", "--clearenv", "--unsetenv",
                        "--ro-bind", "--bind",
                        "--proc", "--dev", "--tmpfs", "--remount-ro", "--setenv", "--chdir")
            supported = set(re.findall(r"(?m)^\s*(--[a-z-]+)(?=\s|$)", output))
            facts["bwrap_help"] = "read" if supported else "unavailable"
            facts["required_options_missing"] = [flag for flag in required if flag not in supported] if supported else []

    def read(path):
        try:
            with Path(path).open(encoding="utf-8") as handle:
                text = handle.read(4097)
            return text.strip() if len(text) <= 4096 else ""
        except (OSError, UnicodeError):
            return ""

    for key, path in (
            ("unprivileged_userns_clone", "/proc/sys/kernel/unprivileged_userns_clone"),
            ("apparmor_restrict_unprivileged_userns", "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"),
            ("max_user_namespaces", "/proc/sys/user/max_user_namespaces")):
        value = read(path)
        facts[key] = int(value) if re.fullmatch(r"[0-9]{1,10}", value) else "unavailable"
    enabled = read("/sys/module/apparmor/parameters/enabled")
    facts["apparmor_enabled"] = {"Y": True, "N": False}.get(enabled, "unavailable")
    profile = read("/proc/self/attr/current")
    facts["parent_apparmor_state"] = ("unconfined" if profile == "unconfined" else
                                        "confined" if profile else "unavailable")
    try:
        facts["bwrap_apparmor_profile_file"] = "present" if Path("/etc/apparmor.d/bwrap-userns-restrict").is_file() else "absent"
    except OSError:
        facts["bwrap_apparmor_profile_file"] = "unavailable"
    # File presence does not prove profile loading or that AppArmor denied us.
    return facts


def _run_self_test(command: list[str]) -> subprocess.CompletedProcess:
    """One unchanged sandbox attempt; only public SELF_TEST is eligible here."""
    try:
        result = subprocess.run(command, env=dict(LAUNCH_ENV), cwd="/", stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                timeout=30, close_fds=True)
    except (OSError, subprocess.SubprocessError) as error:
        detail = {"category": "self_test_timeout" if isinstance(error, subprocess.TimeoutExpired)
                  else "self_test_launch_failed", "errno_hint": "unclassified"}
        result = None
    else:
        if result.returncode == 0:
            return result
        detail = _self_test_failure(result.stderr or "")
    detail["host"] = _self_test_host_capabilities()
    code = f"exit {result.returncode}" if result is not None else "not_completed"
    raise ValueError("Artwork sandbox self-test blocked (" + code + "): " +
                     json.dumps(detail, sort_keys=True, separators=(",", ":")) +
                     "; no unisolated fallback") from None


def sandbox_preflight() -> dict[str, str]:
    """Exercise OS isolation with trusted probe code, no template/app execution."""
    _runtime()
    with tempfile.TemporaryDirectory(prefix="artwork-sandbox-probe-") as tmp:
        root = Path(tmp)
        repository, bundle = root / "app", root / "gate"
        (repository / ".git").mkdir(parents=True)
        bundle.mkdir()
        (repository / ".git/config").write_text("SECRET probe, must be hidden")
        (repository / "sitecustomize.py").write_text("raise RuntimeError('untrusted startup code')\n")
        hidden = root / "unmounted-private-file"
        hidden.write_text("SECRET probe, must never be mounted")
        bootstrap, config = root / "bootstrap.py", root / "git-config"
        bootstrap.write_text(SELF_TEST)
        config.write_text(GIT_CONFIG)
        arguments = [json.dumps(CHILD_ENV, sort_keys=True), os.readlink("/proc/self/ns/net"),
                     os.readlink("/proc/self/ns/pid"), str(hidden)]
        result = _run_self_test(_sandbox_command(repository, bundle, bootstrap, config, arguments))
        if result.stdout.strip() != "ARTWORK_SANDBOX_OK":
            raise ValueError("Artwork sandbox self-test did not confirm isolation")
    return {"status": "verified", "isolation": "bubblewrap", "network": "unshared",
            "environment": "allowlisted", "app": "read_only"}


def run_verified_gate(project: Path, action: str, site: Path | None = None, *,
                      backend: str = "bubblewrap") -> None:
    if action not in {"verify-site", "stage-site"}:
        raise ValueError("Only verify-site and stage-site are permitted")
    if (action == "stage-site") != (site is not None):
        raise ValueError("A website destination is required only for stage-site")
    if backend not in {"bubblewrap", "docker-readonly"}:
        raise ValueError("Unsupported artwork isolation backend")
    if backend == "docker-readonly":
        if action != "verify-site" or site is not None:
            raise ValueError("Docker artwork staging is not enabled")
        from docker_artwork_runtime import verify
        verify(project)
        return
    verified = validate_vendored_bundle(project)
    destination = _no_symlink_path(site) if site is not None else None
    if destination is not None:
        if not destination.is_dir() or destination == Path("/"):
            raise ValueError("Website destination must be an existing dedicated checkout")
        if (destination.is_relative_to(verified.repository_root)
                or verified.repository_root.is_relative_to(destination)
                or ROOT.is_relative_to(destination)):
            raise ValueError("Website checkout must be separate from the app and engine")
        if not (destination / ".git").exists():
            raise ValueError("Website destination must be a dedicated Git checkout")
        if (destination / ".git").is_symlink():
            raise ValueError("Website Git metadata must not be a symlink")
    with tempfile.TemporaryDirectory(prefix="verified-artwork-gate-") as tmp:
        root = Path(tmp)
        bundle = root / "gate"
        bundle.mkdir()
        # Write verified bytes, never copy/reopen the potentially changed source.
        for name, payload in verified.files.items():
            path = bundle / name
            path.write_bytes(payload)
            path.chmod(0o444)
        bootstrap, config = root / "bootstrap.py", root / "git-config"
        bootstrap.write_text(BOOTSTRAP)
        config.write_text(GIT_CONFIG)
        sandbox_project = str(PurePosixPath("/app") / verified.project_relative)
        _run(_sandbox_command(verified.repository_root, bundle, bootstrap, config,
                              [action, sandbox_project], project_relative=verified.project_relative,
                              site=destination))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("self-test", "validate", "verify-site", "stage-site"))
    parser.add_argument("--project", type=Path)
    parser.add_argument("--site", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "self-test":
            if args.project or args.site:
                raise ValueError("Sandbox self-test does not accept application or website inputs")
            print(json.dumps(sandbox_preflight(), sort_keys=True))
        elif args.project is None:
            raise ValueError("--project required")
        elif args.action == "validate":
            if args.site:
                raise ValueError("validate is read-only and does not accept --site")
            value = validate_vendored_bundle(args.project)
            print(json.dumps({"status": "canonical_hashes_verified", "source_commit": value.source_commit,
                              "files": len(value.file_hashes), "gate_sha256": value.file_hashes["release_artwork.py"]}))
        else:
            run_verified_gate(args.project, args.action, args.site)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"ARTWORK ISOLATION BLOCKED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
