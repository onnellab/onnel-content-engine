#!/usr/bin/env python3
"""Opt-in, public synthetic Docker isolation trial; never an artwork backend.

No app checkout, private gate, credentials or publication is accepted by this
module. Docker is contacted only through the existing local socket. Missing
access, policy, runtime or isolation fails closed; nothing repairs the host.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import uuid

DOCKER = "/usr/bin/docker"
SOCKET = "/var/run/docker.sock"
REVIEWED_DOCKER_VERSION = "28.0.4"
# Official linux/amd64 manifest and config bytes independently verified against
# Docker Hub and docker-library/repo-info ac916a0682807597ecd7a991ebf852e366b2571c.
APPROVED_IMAGE = "docker.io/library/python@sha256:edd0b3ec946cc68bd20e39480bd03929016d0fb6254cbf870cd3bc55ea25116d"
APPROVED_IMAGE_ID = "sha256:61d53b56a648da09aa966c5cc46a7e751aea2b38d01f33b04456a9f289685be9"
APPROVED_IMAGE_ENV = [
    "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG=C.UTF-8", "GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305",
    "PYTHON_VERSION=3.12.15",
    "PYTHON_SHA256=c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a",
]
PROFILE_FILE = Path("/sys/kernel/security/apparmor/profiles")
PROFILE_HELPER = Path(__file__).absolute().with_name("check_artwork_apparmor_profile.py")
PROFILE_HELPER_SHA256 = "743b448efb35c21f6e6d98cda56bac9e7ff8b3f3a8bcbb5e226261133798fff3"
PROFILE_HELPER_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
PROFILE_REPORT_LIMIT = 4096
NAMESPACES = ("mnt", "net", "pid", "ipc", "uts", "cgroup")
LABEL = "org.onnellab.artwork-isolation-trial"
MARKER = "ARTWORK_DOCKER_TRIAL_OK\n"
CHILD_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
SAFE_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
MAX_OUTPUT = 1024 * 1024
CLEAN_GIT_CONFIG = "[core]\n\thooksPath = /dev/null\n\tfsmonitor = false\n"
VERSION_FORMAT = ('{"Client":{"Version":{{json .Client.Version}},"Os":{{json .Client.Os}},'
                  '"Arch":{{json .Client.Arch}}},"Server":{"Version":{{json .Server.Version}},'
                  '"Os":{{json .Server.Os}},"Arch":{{json .Server.Arch}}}}')
INFO_FORMAT = ('{"SecurityOptions":{{json .SecurityOptions}},"OSType":{{json .OSType}},'
               '"Architecture":{{json .Architecture}},'
               '"DefaultStorage":{{eq .DockerRootDir "/var/lib/docker"}}}')

# This is public engine-owned test code. It reads no application code and emits
# one fixed success marker. Its stderr is never published, even on assertion.
PROBE = r'''import ctypes, errno, json, os, pathlib, socket, subprocess, sys
assert sys.version_info[:3] == (3, 12, 15)
assert sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
expected_env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
assert dict(os.environ) == expected_env
uid, gid = map(int, sys.argv[1:3])
assert uid != 0 and os.getuid() == os.geteuid() == uid
# Moby 28.0.4 includes the primary GID in AdditionalGids; no other group is allowed.
assert os.getgid() == os.getegid() == gid and os.getgroups() == [gid]
parent = json.loads(sys.argv[3])
for name, identity in parent.items():
    assert os.readlink('/proc/self/ns/' + name) != identity
status = dict(line.split(':', 1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'):
    assert int(status[key].strip(), 16) == 0
assert status['NoNewPrivs'].strip() == '1' and status['Seccomp'].strip() == '2'
assert pathlib.Path('/proc/self/attr/current').read_text().strip() == 'docker-default (enforce)'
assert [name for _, name in socket.if_nameindex()] == ['lo']
with socket.socket() as connection:
    connection.settimeout(0.2)
    try:
        connection.connect(('198.51.100.1', 9))
    except OSError as error:
        assert error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EPERM, errno.EACCES)
    else:
        raise AssertionError('network isolation')
mounts = {}
for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
    fields = line.split()
    mounts[fields[4]] = set(fields[5].split(','))
for target in ('/', '/app', '/gate', '/probe.py', '/app/.git/config', '/site/.git'):
    assert 'ro' in mounts[target]
assert 'rw' in mounts['/site']
for target in ('/app/canary', '/gate/canary'):
    assert pathlib.Path(target).read_text() == 'public synthetic input\n'
    try:
        pathlib.Path(target).write_text('forbidden')
    except OSError as error:
        assert error.errno == errno.EROFS
    else:
        raise AssertionError('read-only bind')
assert pathlib.Path('/app/.git/config').read_text() == '[core]\n\thooksPath = /dev/null\n\tfsmonitor = false\n'
assert not list(pathlib.Path('/site/.git').iterdir())
for target in ('/app/.git/config', '/site/.git/forbidden'):
    try:
        pathlib.Path(target).write_text('forbidden')
    except OSError as error:
        assert error.errno == errno.EROFS
    else:
        raise AssertionError('git credential mask writable')
for target in ('/etc/hosts', '/etc/hostname', '/etc/resolv.conf'):
    try:
        with open(target, 'a') as stream:
            stream.write('forbidden')
    except OSError as error:
        assert error.errno in (errno.EROFS, errno.EACCES, errno.EPERM)
    else:
        raise AssertionError('runtime metadata writable')
for target in ('/var/run/docker.sock', '/run/docker.sock', '/workspace', '/host', sys.argv[4]):
    assert not pathlib.Path(target).exists()
assert not pathlib.Path('/root').is_mount()
libc = ctypes.CDLL(None, use_errno=True)
assert libc.unshare(0x10000000) == -1 and ctypes.get_errno() in (errno.EPERM, errno.ENOSYS)
git = subprocess.run(['/usr/bin/git', '--version'], capture_output=True, check=True, timeout=5)
assert git.stdout.startswith(b'git version ')
pathlib.Path('/tmp/ephemeral').write_text('public temporary input\n')
pathlib.Path('/site/result').write_text('public synthetic output\n')
print('ARTWORK_DOCKER_TRIAL_OK')
'''


class TrialBlocked(RuntimeError):
    """Only fixed, engine-owned categories may reach the public report."""


def _blocked(category: str) -> None:
    raise TrialBlocked(category)


def _unique_profile_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _validate_profile_report(raw: bytes) -> None:
    """Accept only the unchanged helper's internally consistent success report."""
    try:
        if not raw or len(raw) > PROFILE_REPORT_LIMIT:
            raise ValueError()
        report = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique_profile_object)
        keys = {"status", "scope", "reason", "elevation_attempted", "precheck", "elevated",
                "apparmor_enabled", "docker_default_enforcing_unique", "docker_continuation"}
        if not isinstance(report, dict) or set(report) != keys:
            raise ValueError()
        if (report["status"] != "passed" or report["scope"] != "existing_apparmor_profile_read_only"
                or report["reason"] != "existing_enforcing_profile_verified"
                or report["apparmor_enabled"] is not True
                or report["docker_default_enforcing_unique"] is not True
                or report["docker_continuation"] is not False
                or type(report["elevation_attempted"]) is not bool):
            raise ValueError()

        def record(value, identity):
            if not isinstance(value, dict) or set(value) != {
                    "protocol", "identity", "enabled_read", "profiles_read",
                    "apparmor_enabled", "docker_default_enforcing_unique"}:
                raise ValueError()
            if type(value["protocol"]) is not int or value["protocol"] != 1 or value["identity"] != identity:
                raise ValueError()
            for status_key, bool_key in (("enabled_read", "apparmor_enabled"),
                                          ("profiles_read", "docker_default_enforcing_unique")):
                status, flag = value[status_key], value[bool_key]
                if status not in {"ok", "EACCES", "EPERM"}:
                    raise ValueError()
                if (status == "ok" and flag is not True) or (status != "ok" and flag is not None):
                    raise ValueError()
            return {value["enabled_read"], value["profiles_read"]}

        statuses = record(report["precheck"], "nonroot")
        if report["elevation_attempted"]:
            if not statuses.intersection({"EACCES", "EPERM"}) or record(report["elevated"], "root") != {"ok"}:
                raise ValueError()
        elif statuses != {"ok"} or report["elevated"] is not None:
            raise ValueError()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _blocked("readonly_profile_report_unverified")


def _trusted_profile_helper() -> str:
    """Return only the bounded, hash-reviewed bytes of the fixed public sibling."""
    path = PROFILE_HELPER
    if not path.is_absolute() or ".." in path.parts or path.name != "check_artwork_apparmor_profile.py":
        _blocked("readonly_profile_helper_untrusted")
    try:
        for component in (*reversed(path.parents), path):
            if stat.S_ISLNK(component.lstat().st_mode):
                _blocked("readonly_profile_helper_untrusted")
        if not stat.S_ISREG(path.lstat().st_mode):
            _blocked("readonly_profile_helper_untrusted")
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                _blocked("readonly_profile_helper_untrusted")
            payload = stream.read(65537)
        if len(payload) > 65536 or hashlib.sha256(payload).hexdigest() != PROFILE_HELPER_SHA256:
            _blocked("readonly_profile_helper_untrusted")
        program = payload.decode("utf-8", "strict")
    except OSError:
        _blocked("readonly_profile_helper_unavailable")
    except UnicodeError:
        _blocked("readonly_profile_helper_untrusted")
    return program


def _inspect_profile_readonly() -> None:
    # Execute the exact verified bytes, not a pathname that can change after the
    # hash check. This public helper has no __file__ dependency or caller input.
    # It remains unprivileged; only its unchanged constant reader can use sudo.
    program = _trusted_profile_helper()
    try:
        result = subprocess.run(
            ["/usr/bin/python3", "-I", "-S", "-B", "-c", program],
            env=dict(PROFILE_HELPER_ENV), cwd="/", stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=35,
            check=False, close_fds=True, shell=False,
        )
    except subprocess.TimeoutExpired:
        _blocked("readonly_profile_inspection_timeout")
    except OSError:
        _blocked("readonly_profile_inspection_unavailable")
    if result.returncode != 0:
        _blocked("readonly_profile_inspection_blocked")
    _validate_profile_report(result.stdout)


def _profile_loaded(*, inspect_profile_readonly: bool = False) -> None:
    if inspect_profile_readonly:
        _inspect_profile_readonly()
        return
    try:
        with PROFILE_FILE.open() as stream:
            profiles = stream.read(MAX_OUTPUT + 1)
        enabled = Path("/sys/module/apparmor/parameters/enabled").read_text().strip()
    except OSError:
        _blocked("existing_apparmor_policy_unreadable")
    if len(profiles) > MAX_OUTPUT or enabled != "Y":
        _blocked("existing_apparmor_policy_unavailable")
    matches = [line for line in profiles.splitlines() if line.startswith("docker-default ")]
    if matches != ["docker-default (enforce)"]:
        _blocked("existing_enforcing_docker_profile_required")


def _host_facts(*, inspect_profile_readonly: bool = False) -> dict:
    if sys.platform != "linux":
        _blocked("linux_required")
    if os.getuid() == 0 or os.getgid() == 0:
        _blocked("nonroot_runner_required")
    try:
        if not Path(DOCKER).is_file() or not os.access(DOCKER, os.X_OK):
            _blocked("existing_docker_client_required")
        if not stat.S_ISSOCK(Path(SOCKET).stat().st_mode):
            _blocked("existing_local_docker_socket_required")
        namespaces = {name: os.readlink("/proc/self/ns/" + name) for name in NAMESPACES}
    except OSError:
        _blocked("existing_local_runtime_unavailable")
    _profile_loaded(inspect_profile_readonly=inspect_profile_readonly)
    return {"uid": os.getuid(), "gid": os.getgid(), "namespaces": namespaces}


class Client:
    def __init__(self, config: Path):
        self.prefix = [DOCKER, "--host", "unix://" + SOCKET, "--config", str(config)]
        self.env = dict(SAFE_ENV, HOME=str(config))

    def call(self, args: list[str], category: str, *, timeout: int = 20, check: bool = True):
        try:
            result = subprocess.run(self.prefix + args, env=self.env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    timeout=timeout, check=False, cwd="/")
        except subprocess.TimeoutExpired:
            _blocked(category + "_timeout")
        except OSError:
            _blocked(category + "_unavailable")
        if len(result.stdout) > MAX_OUTPUT or len(result.stderr) > MAX_OUTPUT:
            _blocked(category + "_output_invalid")
        if check and result.returncode:
            _blocked(category)
        return result

    def read_json(self, args: list[str], category: str):
        result = self.call(args, category)
        try:
            return json.loads(result.stdout)
        except (ValueError, TypeError):
            _blocked(category + "_invalid")


def _readiness(client: Client, *, inspect_profile_readonly: bool = False) -> dict:
    facts = _host_facts(inspect_profile_readonly=inspect_profile_readonly)
    version = client.read_json(["version", "--format", VERSION_FORMAT], "docker_version_unavailable")
    info = client.read_json(["info", "--format", INFO_FORMAT], "docker_info_unavailable")
    if not isinstance(version, dict) or not isinstance(info, dict):
        _blocked("runtime_metadata_invalid")
    for part in ("Client", "Server"):
        record = version.get(part, {})
        if not isinstance(record, dict) or record.get("Version") != REVIEWED_DOCKER_VERSION:
            _blocked("docker_version_not_reviewed")
        if record.get("Os") != "linux" or record.get("Arch") != "amd64":
            _blocked("docker_platform_not_reviewed")
    security = info.get("SecurityOptions", [])
    if not isinstance(security, list) or not {"name=apparmor", "name=seccomp,profile=builtin", "name=cgroupns"}.issubset(security):
        _blocked("existing_default_confinement_required")
    if "name=rootless" in security or "name=userns" in security:
        _blocked("docker_namespace_configuration_not_reviewed")
    if info.get("OSType") != "linux" or info.get("Architecture") not in {"x86_64", "amd64"}:
        _blocked("docker_platform_not_reviewed")
    if info.get("DefaultStorage") is not True:
        _blocked("docker_storage_location_not_reviewed")
    try:
        if min(shutil.disk_usage("/var/lib/docker").free, shutil.disk_usage("/tmp").free) < 2 * 1024 ** 3:
            _blocked("insufficient_trial_disk_space")
    except OSError:
        _blocked("trial_disk_space_unverifiable")
    running = client.call(["container", "ls", "--no-trunc", "--format", "{{.ID}}"], "existing_workloads_unreadable")
    identities = running.stdout.splitlines()
    if len(identities) > 10000 or any(not re.fullmatch(r"[0-9a-f]{64}", identity) for identity in identities):
        _blocked("existing_workloads_metadata_invalid")
    facts["existing_running_count"] = len(identities)
    return facts


def _validate_image(image: object) -> str:
    if not isinstance(image, list) or len(image) != 1 or not isinstance(image[0], dict):
        _blocked("image_metadata_invalid")
    record = image[0]
    config = record.get("Config")
    if not isinstance(config, dict) or record.get("Os") != "linux" or record.get("Architecture") != "amd64":
        _blocked("image_platform_not_reviewed")
    digest = APPROVED_IMAGE.split("@", 1)[1]
    official_names = {repository + "@" + digest for repository in
                      ("docker.io/library/python", "library/python", "python")}
    if not official_names.intersection(record.get("RepoDigests", [])):
        _blocked("image_digest_mismatch")
    if any(config.get(key) for key in ("Volumes", "Healthcheck", "OnBuild", "Entrypoint", "User", "ExposedPorts")):
        _blocked("image_automatic_behavior_forbidden")
    if config.get("Env") != APPROVED_IMAGE_ENV or config.get("Cmd") != ["python3"]:
        _blocked("image_configuration_not_reviewed")
    identity = record.get("Id", "")
    if identity != APPROVED_IMAGE_ID:
        _blocked("image_identity_invalid")
    return identity


def _mount_specs(root: Path) -> list[tuple[Path, str, bool]]:
    return [(root / "app", "/app", True), (root / "gate", "/gate", True),
            (root / "probe.py", "/probe.py", True), (root / "site", "/site", False),
            (root / "clean-git-config", "/app/.git/config", True),
            (root / "empty-site-git", "/site/.git", True)]


def _create_args(name: str, token: str, root: Path, facts: dict) -> list[str]:
    args = ["container", "create", "--pull=never", "--name", name, "--label", LABEL + "=" + token,
            "--network=none", "--read-only", "--user", f"{facts['uid']}:{facts['gid']}",
            "--cap-drop=ALL", "--security-opt=no-new-privileges=true",
            "--security-opt=apparmor=docker-default", "--ipc=private", "--cgroupns=private",
            "--hostname=artwork-trial", "--no-healthcheck", "--pids-limit=64", "--memory=256m",
            "--cpus=1", "--log-driver=none", "--workdir=/app", "--entrypoint=/usr/bin/env",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
            "--tmpfs", "/run:rw,nosuid,nodev,noexec,size=1m,mode=755"]
    for source, target, readonly in _mount_specs(root):
        mount = f"type=bind,src={source},dst={target},bind-propagation=rprivate"
        mount += ",readonly,bind-recursive=readonly" if readonly else ",bind-recursive=disabled"
        args += ["--mount", mount]
    return args + [APPROVED_IMAGE, "-i", *[key + "=" + value for key, value in CHILD_ENV.items()],
                   "/usr/local/bin/python3", "-I", "-S", "-B", "/probe.py", str(facts["uid"]),
                   str(facts["gid"]), json.dumps(facts["namespaces"], sort_keys=True), str(root / "host-only")]


def _validate_container(records: object, identity: str, name: str, token: str,
                        root: Path, facts: dict, image_id: str) -> None:
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        _blocked("container_metadata_invalid")
    item = records[0]
    config, host = item.get("Config", {}), item.get("HostConfig", {})
    if not isinstance(config, dict) or not isinstance(host, dict):
        _blocked("container_metadata_invalid")
    if item.get("Id") != identity or item.get("Name") != "/" + name or item.get("Image") != image_id or config.get("Labels", {}).get(LABEL) != token:
        _blocked("container_identity_mismatch")
    expected = _create_args(name, token, root, facts)
    command = expected[expected.index(APPROVED_IMAGE) + 1:]
    if config.get("Entrypoint") != ["/usr/bin/env"] or config.get("Cmd") != command or config.get("User") != f"{facts['uid']}:{facts['gid']}" or config.get("WorkingDir") != "/app":
        _blocked("container_command_mismatch")
    # Validate loader-time environment too, before /usr/bin/env can clear it.
    # Docker's generated HOME/HOSTNAME occur at exec time, not in Config.Env;
    # the trusted env -i removes those before Python starts.
    if config.get("Env") != APPROVED_IMAGE_ENV:
        _blocked("container_initial_environment_mismatch")
    if config.get("Volumes") or config.get("Healthcheck", {}).get("Test") != ["NONE"]:
        _blocked("container_automatic_behavior_forbidden")
    expected_host = {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                     "CapDrop": ["ALL"], "IpcMode": "private", "CgroupnsMode": "private",
                     "PidMode": "", "UTSMode": "", "UsernsMode": "", "PidsLimit": 64,
                     "Memory": 256 * 1024 * 1024, "NanoCpus": 1000000000}
    if any(host.get(key) != value for key, value in expected_host.items()):
        _blocked("container_isolation_mismatch")
    if set(host.get("SecurityOpt", [])) != {"no-new-privileges=true", "apparmor=docker-default"}:
        _blocked("container_confinement_mismatch")
    if any(host.get(key) for key in ("CapAdd", "Devices", "DeviceRequests", "GroupAdd", "VolumesFrom", "Binds", "Links", "ExtraHosts", "PortBindings")):
        _blocked("container_extra_access_forbidden")
    if host.get("LogConfig", {}).get("Type") != "none":
        _blocked("container_log_storage_forbidden")
    if host.get("Tmpfs") != {"/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777", "/run": "rw,nosuid,nodev,noexec,size=1m,mode=755"}:
        _blocked("container_temporary_mounts_mismatch")
    configured = host.get("Mounts", [])
    if not isinstance(configured, list) or len(configured) != len(_mount_specs(root)):
        _blocked("container_recursive_mounts_mismatch")
    expected_configured = {target: (str(source), readonly) for source, target, readonly in _mount_specs(root)}
    seen_configured = set()
    for mount in configured:
        target = mount.get("Target")
        options = mount.get("BindOptions", {})
        if target not in expected_configured or target in seen_configured or (mount.get("Source"), mount.get("ReadOnly", False)) != expected_configured[target]:
            _blocked("container_recursive_mounts_mismatch")
        seen_configured.add(target)
        if mount.get("Type") != "bind" or options.get("Propagation") != "rprivate" or options.get("ReadOnlyNonRecursive", False):
            _blocked("container_recursive_mounts_mismatch")
        if mount.get("Target") == "/site":
            if options.get("NonRecursive") is not True or options.get("ReadOnlyForceRecursive", False):
                _blocked("container_recursive_mounts_mismatch")
        elif options.get("ReadOnlyForceRecursive") is not True or options.get("NonRecursive", False):
            _blocked("container_recursive_mounts_mismatch")
    mounts = item.get("Mounts", [])
    expected_mounts = {target: (str(source), not readonly) for source, target, readonly in _mount_specs(root)}
    # Engine versions may list tmpfs mounts here as well as in HostConfig.
    binds = [mount for mount in mounts if mount.get("Type") == "bind"]
    if len(binds) != len(expected_mounts) or any(mount.get("Type") not in {"bind", "tmpfs"} for mount in mounts):
        _blocked("container_mounts_mismatch")
    if any(mount.get("Destination") not in {"/tmp", "/run"} for mount in mounts if mount.get("Type") == "tmpfs"):
        _blocked("container_mounts_mismatch")
    seen = set()
    for mount in binds:
        target = mount.get("Destination")
        if target not in expected_mounts or target in seen or (mount.get("Source"), mount.get("RW")) != expected_mounts[target] or mount.get("Propagation") != "rprivate":
            _blocked("container_mounts_mismatch")
        seen.add(target)
    if item.get("State", {}).get("Running") is not False:
        _blocked("container_started_before_validation")


def _cleanup(client: Client, name: str, token: str, expected_id: str | None = None) -> None:
    """Remove only our labelled container, including an ambiguous create timeout."""
    identity = expected_id
    result = client.call(["container", "inspect", expected_id or name], "cleanup_inspect_failed", check=False)
    if result.returncode == 0:
        try:
            records = json.loads(result.stdout)
            item = records[0]
            identity = item["Id"]
            owned = (len(records) == 1 and item["Name"] == "/" + name and
                     item["Config"]["Labels"].get(LABEL) == token and
                     re.fullmatch(r"[0-9a-f]{64}", identity) and
                     (expected_id is None or identity == expected_id))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            owned = False
        if not owned:
            _blocked("cleanup_ownership_unverified")
        client.call(["container", "rm", "--force", identity], "cleanup_remove_failed", check=False)
    filters = ["name=^/" + name + "$"]
    if identity is not None:
        filters.append("id=" + identity)
    for selector in filters:
        remaining = client.call(["container", "ls", "--all", "--no-trunc", "--filter", selector,
                                 "--format", "{{.ID}}"], "cleanup_verification_failed")
        if remaining.stdout.strip():
            _blocked("cleanup_container_still_present")


def run_trial(*, inspect_profile_readonly: bool = False) -> dict:
    """Run one synthetic trial. No fallback, publication or production adoption."""
    if type(inspect_profile_readonly) is not bool:
        _blocked("profile_inspection_mode_invalid")
    if not re.fullmatch(r"docker\.io/library/python@sha256:[0-9a-f]{64}", APPROVED_IMAGE):
        _blocked("reviewed_official_image_digest_required")
    name = "onnellab-artwork-trial-" + uuid.uuid4().hex
    token = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="artwork-docker-trial-", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        config = root / "client"
        config.mkdir(mode=0o700)
        (config / "config.json").write_text("{}\n")
        (config / "config.json").chmod(0o600)
        client = Client(config)
        facts = _readiness(client, inspect_profile_readonly=inspect_profile_readonly)
        client.call(["image", "pull", "--platform=linux/amd64", APPROVED_IMAGE], "image_pull_failed", timeout=180)
        image_id = _validate_image(client.read_json(["image", "inspect", APPROVED_IMAGE], "image_inspect_failed"))
        for directory in ("app", "gate", "site"):
            (root / directory).mkdir(mode=0o755)
        for directory in ("app", "gate"):
            (root / directory / "canary").write_text("public synthetic input\n")
        (root / "host-only").write_text("public host-only canary\n")
        (root / "probe.py").write_text(PROBE)
        for directory in ("app", "site"):
            (root / directory / ".git").mkdir(mode=0o755)
            (root / directory / ".git/config").write_text("public synthetic credential canary\n")
        (root / "clean-git-config").write_text(CLEAN_GIT_CONFIG)
        (root / "empty-site-git").mkdir(mode=0o755)
        _profile_loaded(inspect_profile_readonly=inspect_profile_readonly)
        attempted_create = False
        identity = None
        try:
            attempted_create = True
            result = client.call(_create_args(name, token, root, facts), "container_create_failed")
            candidate = result.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{64}", candidate):
                _blocked("container_identity_invalid")
            identity = candidate
            records = client.read_json(["container", "inspect", identity], "container_inspect_failed")
            _validate_container(records, identity, name, token, root, facts, image_id)
            _profile_loaded(inspect_profile_readonly=inspect_profile_readonly)
            result = client.call(["container", "start", "--attach", identity], "synthetic_probe_failed", timeout=45)
            if result.stdout != MARKER or result.stderr:
                _blocked("synthetic_probe_output_invalid")
            final = client.read_json(["container", "inspect", identity], "probe_exit_unverifiable")
            if not isinstance(final, list) or len(final) != 1 or final[0].get("Id") != identity or final[0].get("State", {}).get("Running") is not False or final[0].get("State", {}).get("ExitCode") != 0 or final[0].get("State", {}).get("Status") != "exited":
                _blocked("probe_exit_unverified")
            if (root / "site/result").read_text() != "public synthetic output\n" or sorted(p.name for p in (root / "site").iterdir()) != [".git", "result"]:
                _blocked("synthetic_site_output_invalid")
            for directory in ("app", "gate"):
                if (root / directory / "canary").read_text() != "public synthetic input\n":
                    _blocked("synthetic_readonly_input_changed")
            for directory in ("app", "site"):
                if (root / directory / ".git/config").read_text() != "public synthetic credential canary\n":
                    _blocked("synthetic_host_git_canary_changed")
        finally:
            if attempted_create:
                _cleanup(client, name, token, identity)
    return {"schema_version": 1, "status": "passed", "scope": "public_synthetic_only",
            "docker_version": REVIEWED_DOCKER_VERSION, "image": APPROVED_IMAGE,
            "cleanup": "verified", "existing_running_containers": facts["existing_running_count"],
            "production_backend_changed": False}


def main(argv: list[str] | None = None) -> int:
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        try:
            arguments = sys.argv[1:] if argv is None else argv
            if arguments not in ([], ["--inspect-profile-readonly"]):
                _blocked("arguments_not_supported")
            report = run_trial(inspect_profile_readonly=bool(arguments))
        except TrialBlocked as error:
            report = {"schema_version": 1, "status": "blocked", "category": str(error),
                      "scope": "public_synthetic_only", "production_backend_changed": False}
        except (Exception, KeyboardInterrupt):
            report = {"schema_version": 1, "status": "blocked", "category": "trial_interrupted_or_internal_error",
                      "scope": "public_synthetic_only", "production_backend_changed": False}
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "passed" else 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
