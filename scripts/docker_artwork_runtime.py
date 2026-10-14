"""Default-off read-only Docker adapter for independently validated artwork gates.

No workflow selects this adapter. It uses existing rootful Docker access, not a
separate user namespace. Production authorization and live read-only proof are
required before any operational selection. Staging is deliberately unsupported.
"""
from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
from pathlib import Path, PurePosixPath
import re
import signal
import tempfile
import uuid

import check_artwork_docker_isolation as policy

# Fixed engine-owned check executes before any allowlisted private gate bytes.
BOUNDARY = '''import ctypes, errno, json, os, pathlib, socket, sys
expected = json.loads(sys.argv.pop(1))
if dict(os.environ) != expected["environment"] or os.getuid() != expected["uid"] or os.getgid() != expected["gid"] or os.getgroups() != [expected["gid"]]:
    raise RuntimeError("Artwork identity/environment mismatch")
for name, parent in expected["namespaces"].items():
    if os.readlink("/proc/self/ns/" + name) == parent:
        raise RuntimeError("Artwork namespace was not isolated")
status = dict(line.split(":", 1) for line in pathlib.Path("/proc/self/status").read_text().splitlines() if ":" in line)
if any(int(status[key].strip(), 16) for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")) or status["NoNewPrivs"].strip() != "1" or status["Seccomp"].strip() != "2":
    raise RuntimeError("Artwork process confinement mismatch")
if pathlib.Path("/proc/self/attr/current").read_text().strip() != "docker-default (enforce)":
    raise RuntimeError("Artwork AppArmor confinement mismatch")
for path in ("/app/.artwork-ro-probe", "/gate/.artwork-ro-probe", "/usr/.artwork-ro-probe"):
    try:
        pathlib.Path(path).write_text("public readonly canary")
    except OSError as error:
        if error.errno != errno.EROFS:
            raise RuntimeError("Artwork mount readonly state unverified") from None
    else:
        raise RuntimeError("Artwork mount unexpectedly writable")
if pathlib.Path("/app/.git/config").read_text() != expected["git_config"]:
    raise RuntimeError("Artwork Git credential mask mismatch")
for path in ("/site", "/var/run/docker.sock", "/run/docker.sock", expected["host_only"]):
    if pathlib.Path(path).exists():
        raise RuntimeError("Unexpected artwork host mount")
if any(line.split()[0] != "lo" for line in pathlib.Path("/proc/net/route").read_text().splitlines()[1:] if line.split()):
    raise RuntimeError("Artwork external route present")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
    connection.settimeout(1)
    if connection.connect_ex(("192.0.2.1", 9)) == 0:
        raise RuntimeError("Artwork external network reachable")
libc = ctypes.CDLL(None, use_errno=True)
if libc.unshare(0x10000000) != -1 or ctypes.get_errno() not in (errno.EPERM, errno.EACCES):
    raise RuntimeError("Artwork nested user namespace not denied")
'''


def _spec(root: Path, repository: Path, relative: PurePosixPath, facts: dict,
          environment: dict[str, str], git_config: str) -> policy.LaunchSpec:
    project = str(PurePosixPath("/app") / relative)
    expected = {"environment": environment, "uid": facts["uid"], "gid": facts["gid"],
                "namespaces": facts["namespaces"], "git_config": git_config,
                "host_only": str(root / "host-only")}
    return policy.LaunchSpec(
        ((repository, "/app", True), (root / "gate", "/gate", True),
         (root / "bootstrap.py", "/probe.py", True),
         (root / "git-config", "/app/.git/config", True)),
        (json.dumps(expected, sort_keys=True), "verify-site", project),
        tuple(environment.items()), project)


def _attach_gate(client: policy.Client, identity: str) -> None:
    """Drain and discard private output with a hard combined streaming byte cap."""
    try:
        process = subprocess.Popen(
            client.prefix + ["container", "start", "--attach", identity],
            env=dict(client.env), cwd="/", stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
            close_fds=True, shell=False)
    except OSError:
        policy._blocked("readonly_artwork_gate_unavailable")
    deadline = time.monotonic() + 300
    total = 0
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                selector.register(stream, selectors.EVENT_READ)
            active = 2
            while active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    policy._blocked("readonly_artwork_gate_timeout")
                for key, _ in selector.select(remaining):
                    # No private output is retained, decoded, returned or logged.
                    chunk = os.read(key.fileobj.fileno(), min(4096, policy.MAX_OUTPUT + 1 - total))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        active -= 1
                    else:
                        total += len(chunk)
                        if total > policy.MAX_OUTPUT:
                            policy._blocked("readonly_artwork_gate_output_limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                policy._blocked("readonly_artwork_gate_timeout")
            if process.wait(timeout=remaining) != 0:
                policy._blocked("readonly_artwork_gate_failed")
    except subprocess.TimeoutExpired:
        policy._blocked("readonly_artwork_gate_timeout")
    except OSError:
        policy._blocked("readonly_artwork_gate_io_unavailable")
    finally:
        try:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            policy._blocked("readonly_artwork_client_cleanup_unverified")
        finally:
            process.stdout.close()
            process.stderr.close()
    # Caller always removes/verifies its labelled container in a separate finally.


def verify(project: Path) -> None:
    """Validate again at this public boundary; execute only exact approved bytes."""
    import isolated_vendored_artwork as gate
    verified = gate.validate_vendored_bundle(project)
    # All launch paths are non-symlink, standalone repository paths validated by
    # the existing gate. Docker's CSV mount syntax must not reinterpret a path.
    if any(c in str(verified.repository_root) for c in (",", "\n", "\r")):
        raise ValueError("Artwork checkout path is unsupported for Docker binds")
    name = "onnellab-artwork-verify-" + uuid.uuid4().hex
    token = uuid.uuid4().hex
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        with tempfile.TemporaryDirectory(prefix="artwork-docker-verify-", dir="/tmp") as temporary:
            root = Path(temporary).resolve()
            config = root / "client"
            config.mkdir(mode=0o700)
            (config / "config.json").write_text("{}\n")
            (config / "config.json").chmod(0o600)
            client = policy.Client(config)
            facts = policy._readiness(client, inspect_profile_readonly=True)
            client.call(["image", "pull", "--platform=linux/amd64", policy.APPROVED_IMAGE],
                        "image_pull_failed", timeout=180)
            image_id = policy._validate_image(client.read_json(
                ["image", "inspect", policy.APPROVED_IMAGE], "image_inspect_failed"))
            (root / "gate").mkdir()
            for name_in_bundle, payload in verified.files.items():
                path = root / "gate" / name_in_bundle
                path.write_bytes(payload)
                path.chmod(0o444)
            (root / "bootstrap.py").write_text(BOUNDARY + gate.BOOTSTRAP)
            (root / "git-config").write_text(gate.GIT_CONFIG)
            (root / "host-only").write_text("public unmounted host canary\n")
            spec = _spec(root, verified.repository_root, verified.project_relative,
                         facts, dict(gate.CHILD_ENV), gate.GIT_CONFIG)
            policy._profile_loaded(inspect_profile_readonly=True)
            identity = None
            attempted = False
            try:
                attempted = True
                result = client.call(policy._create_args(name, token, root, facts, spec=spec),
                                     "container_create_failed")
                identity = result.stdout.strip()
                if not re.fullmatch(r"[0-9a-f]{64}", identity):
                    identity = None
                    policy._blocked("container_identity_invalid")
                policy._validate_container(client.read_json(["container", "inspect", identity],
                    "container_inspect_failed"), identity, name, token, root, facts, image_id, spec=spec)
                policy._profile_loaded(inspect_profile_readonly=True)
                # Private gate stdout/stderr are never forwarded or persisted.
                _attach_gate(client, identity)
                final = client.read_json(["container", "inspect", identity], "gate_exit_unverifiable")
                if (not isinstance(final, list) or len(final) != 1 or final[0].get("Id") != identity
                        or final[0].get("State", {}).get("Running") is not False
                        or final[0].get("State", {}).get("ExitCode") != 0
                        or final[0].get("State", {}).get("Status") != "exited"):
                    policy._blocked("readonly_artwork_gate_exit_unverified")
            finally:
                if attempted:
                    policy._cleanup(client, name, token, identity)
    except policy.TrialBlocked as error:
        raise ValueError("Docker artwork verification blocked: " + str(error)) from None
    finally:
        signal.signal(signal.SIGTERM, previous)
