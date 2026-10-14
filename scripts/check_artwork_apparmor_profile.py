#!/usr/bin/env python3
"""Fixed, read-only AppArmor diagnostic; never starts or repairs Docker.

Run only as a non-root Linux user. A fixed unprivileged reader runs first; the
same fixed read is attempted with noninteractive sudo only for EACCES/EPERM.
The privileged interpreter neither imports repository code nor accepts input.
Only sanitized status enums and booleans are returned, never kernel contents.
"""
from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
import time

SAFE_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
MAX_OUTPUT = 4096
TIMEOUT = 10
READ_STATUSES = frozenset({"ok", "EACCES", "EPERM", "ENOENT", "other"})

# Public, constant source passed as a single -c argument. Explicit data reads
# are limited to these two fixed kernel targets. Descriptor-relative traversal
# refuses symlinks in every component, including the final file. Standard
# interpreter/sudo runtime loading and sudo auditing are outside these reads.
READER_PROGRAM = r'''import errno, json, os, signal, stat, sys

def read_fixed(parts, limit):
    directory = None
    target = None
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        directory = os.open("/", flags | os.O_DIRECTORY)
        for part in parts[:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
        target = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=directory)
        metadata = os.fstat(target)
        # sysfs reports a nominal page size even for tiny attributes; only
        # actual bounded reads establish the content length of these files.
        if not stat.S_ISREG(metadata.st_mode):
            return "other", None
        chunks = []
        size = 0
        while size <= limit:
            chunk = os.read(target, min(65536, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > limit:
            return "other", None
        return "ok", b"".join(chunks)
    except OSError as error:
        return {errno.EACCES: "EACCES", errno.EPERM: "EPERM",
                errno.ENOENT: "ENOENT"}.get(error.errno, "other"), None
    finally:
        for descriptor in (target, directory):
            if descriptor is not None:
                os.close(descriptor)

def empty_result():
    return {"protocol": 1, "identity": "invalid", "enabled_read": "other",
            "profiles_read": "other", "apparmor_enabled": None,
            "docker_default_enforcing_unique": None}

def inspect(expected_root):
    result = empty_result()
    if (sys.platform != "linux" or sys.argv != ["-c"]
            or not sys.flags.isolated or not sys.flags.no_site
            or not sys.flags.dont_write_bytecode
            or dict(os.environ) != {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}):
        return result
    uid, effective_uid = os.getuid(), os.geteuid()
    if uid != effective_uid or (uid == 0) != expected_root:
        return result
    result["identity"] = "root" if expected_root else "nonroot"
    enabled_status, enabled = read_fixed(
        ("sys", "module", "apparmor", "parameters", "enabled"), 16)
    profiles_status, profiles = read_fixed(
        ("sys", "kernel", "security", "apparmor", "profiles"), 1024 * 1024)
    if enabled_status == "ok":
        if enabled in (b"Y", b"Y\n", b"N", b"N\n"):
            result["apparmor_enabled"] = enabled in (b"Y", b"Y\n")
        else:
            enabled_status = "other"
    if profiles_status == "ok":
        try:
            text = profiles.decode("utf-8", "strict")
            if (text and not text.endswith("\n")) or any(
                    ord(char) < 32 and char != "\n" or ord(char) == 127 for char in text):
                raise ValueError()
            matches = []
            for line in text.split("\n")[:-1]:
                name, separator, mode = line.rpartition(" (")
                if not name or not separator or mode not in (
                        "enforce)", "complain)", "kill)", "unconfined)"):
                    raise ValueError()
                if name == "docker-default":
                    matches.append(line)
            result["docker_default_enforcing_unique"] = matches == ["docker-default (enforce)"]
        except (UnicodeError, ValueError):
            profiles_status = "other"
    result["enabled_read"] = enabled_status
    result["profiles_read"] = profiles_status
    return result

signal.signal(signal.SIGALRM, signal.SIG_DFL)
signal.alarm(5)
'''

# Both entry points are constants, not templates populated with caller data.
# The inner alarm bounds the fixed privileged reader independently of its parent.
UNPRIVILEGED_PROGRAM = READER_PROGRAM + '''try:
    result = inspect(False)
except Exception:
    result = empty_result()
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")
'''
PUBLIC_PROGRAM = READER_PROGRAM + '''try:
    result = inspect(True)
except Exception:
    result = empty_result()
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")
'''
UNPRIVILEGED_COMMAND = (
    "/usr/bin/python3", "-I", "-S", "-B", "-c", UNPRIVILEGED_PROGRAM,
)
ELEVATED_COMMAND = (
    "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i",
    "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "/usr/bin/python3",
    "-I", "-S", "-B", "-c", PUBLIC_PROGRAM,
)


class ProbeBlocked(RuntimeError):
    """Only fixed categories, never original errors or process output."""


def _stop_owned_process(process) -> None:
    """Bound cleanup of this invocation only; never inspect or kill other jobs."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            raise ProbeBlocked("probe_cleanup_unverified") from None
    except OSError:
        if process.poll() is None:
            raise ProbeBlocked("probe_cleanup_unverified") from None


def _capture(command: tuple[str, ...]) -> bytes:
    """Bound bytes while reading, rather than after unbounded communicate()."""
    try:
        process = subprocess.Popen(
            command, env=dict(SAFE_ENV), cwd="/", stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
            close_fds=True, shell=False,
        )
    except OSError:
        raise ProbeBlocked("probe_unavailable") from None
    output = bytearray()
    deadline = time.monotonic() + TIMEOUT
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeBlocked("probe_timeout")
                if not selector.select(remaining):
                    continue
                chunk = os.read(process.stdout.fileno(), min(1024, MAX_OUTPUT + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > MAX_OUTPUT:
                    raise ProbeBlocked("probe_output_invalid")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeBlocked("probe_timeout")
        if process.wait(timeout=remaining) != 0:
            raise ProbeBlocked("probe_failed")
        return bytes(output)
    except subprocess.TimeoutExpired:
        raise ProbeBlocked("probe_timeout") from None
    except OSError:
        raise ProbeBlocked("probe_io_unavailable") from None
    finally:
        try:
            _stop_owned_process(process)
        finally:
            process.stdout.close()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _parse(raw: bytes, *, elevated: bool) -> dict:
    try:
        if not raw or len(raw) > MAX_OUTPUT:
            raise ValueError()
        result = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique_object)
        expected_keys = {"protocol", "identity", "enabled_read", "profiles_read",
                         "apparmor_enabled", "docker_default_enforcing_unique"}
        if not isinstance(result, dict) or set(result) != expected_keys:
            raise ValueError()
        if type(result["protocol"]) is not int or result["protocol"] != 1:
            raise ValueError()
        if result["identity"] != ("root" if elevated else "nonroot"):
            raise ValueError()
        for status_key, value_key in (("enabled_read", "apparmor_enabled"),
                                      ("profiles_read", "docker_default_enforcing_unique")):
            status, value = result[status_key], result[value_key]
            if type(status) is not str or status not in READ_STATUSES:
                raise ValueError()
            if status == "ok" and type(value) is not bool:
                raise ValueError()
            if status != "ok" and value is not None:
                raise ValueError()
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProbeBlocked("probe_output_invalid") from None


def run_probe() -> dict:
    report = {"status": "blocked", "scope": "existing_apparmor_profile_read_only",
              "reason": "existing_enforcing_profile_unverified", "elevation_attempted": False,
              "precheck": None, "elevated": None, "apparmor_enabled": None,
              "docker_default_enforcing_unique": None, "docker_continuation": False}
    try:
        if sys.platform != "linux":
            raise ProbeBlocked("linux_required")
        if (os.getuid() == 0 or os.geteuid() == 0 or os.getuid() != os.geteuid()
                or os.getgid() == 0 or os.getegid() == 0 or os.getgid() != os.getegid()):
            raise ProbeBlocked("nonroot_runner_required")
        record = _parse(_capture(UNPRIVILEGED_COMMAND), elevated=False)
        report["precheck"] = record
        statuses = {record["enabled_read"], record["profiles_read"]}
        # Known disabled/missing/malformed states never justify elevation.
        if (statuses <= {"ok", "EACCES", "EPERM"}
                and statuses & {"EACCES", "EPERM"}
                and record["apparmor_enabled"] is not False
                and record["docker_default_enforcing_unique"] is not False):
            report["elevation_attempted"] = True
            record = _parse(_capture(ELEVATED_COMMAND), elevated=True)
            report["elevated"] = record
        report["apparmor_enabled"] = record["apparmor_enabled"]
        report["docker_default_enforcing_unique"] = record["docker_default_enforcing_unique"]
        if (record["apparmor_enabled"] is True
                and record["docker_default_enforcing_unique"] is True):
            report["status"] = "passed"
            report["reason"] = "existing_enforcing_profile_verified"
    except ProbeBlocked as error:
        report["reason"] = str(error)
    return report


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps({"status": "blocked", "reason": "arguments_not_supported",
                          "docker_continuation": False}, sort_keys=True))
        return 1
    report = run_probe()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
