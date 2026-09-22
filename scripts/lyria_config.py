"""Local non-secret configuration and gcloud ADC readiness for Lyria 3 Pro."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from short_video_credentials import CredentialError

MODEL = "lyria-3-pro-preview"
LOCATION = "global"
UNIT_PRICE_USD = 0.08
PRIVATE_ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/lyria"
CONFIG_PATH = PRIVATE_ROOT / "config.json"
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


def validate_project_id(value: str) -> str:
    if not isinstance(value, str):
        raise CredentialError("lyria_project_id_invalid")
    value = value.strip()
    if not PROJECT_RE.fullmatch(value):
        raise CredentialError("lyria_project_id_invalid")
    return value


def validate_settings(data: dict) -> dict:
    if not isinstance(data, dict):
        raise CredentialError("lyria_settings_invalid")
    if set(data) != {"project_id", "candidate_count", "max_usd_per_run", "enabled"}:
        raise CredentialError("lyria_settings_invalid")
    project_id = validate_project_id(data["project_id"])
    count = data["candidate_count"]
    cap = data["max_usd_per_run"]
    enabled = data["enabled"]
    if type(count) is not int or not 1 <= count <= 5:
        raise CredentialError("lyria_candidate_count_invalid")
    if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not 0 <= float(cap) <= 5:
        raise CredentialError("lyria_spend_cap_invalid")
    minimum = round(count * UNIT_PRICE_USD, 2)
    if enabled and float(cap) + 1e-9 < minimum:
        raise CredentialError("lyria_spend_cap_below_candidate_cost")
    return {
        "schema_version": 1,
        "project_id": project_id,
        "candidate_count": count,
        "max_usd_per_run": round(float(cap), 2),
        "enabled": enabled,
        "model": MODEL,
        "location": LOCATION,
        "estimated_unit_price_usd": UNIT_PRICE_USD,
    }


def private_directory(path: Path = PRIVATE_ROOT) -> Path:
    path = Path(path).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise CredentialError("unsafe_lyria_config_directory")
    os.chmod(path, 0o700)
    return path


def load_settings(path: Path = CONFIG_PATH) -> dict | None:
    path = Path(path).expanduser()
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise CredentialError("unsafe_lyria_config_file")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise CredentialError("lyria_settings_invalid") from None
    expected = {key: raw.get(key) for key in ("project_id", "candidate_count", "max_usd_per_run", "enabled")}
    return validate_settings(expected)


def save_settings(data: dict, path: Path = CONFIG_PATH) -> dict:
    value = validate_settings(data)
    root = private_directory(Path(path).expanduser().parent)
    path = root / Path(path).name
    fd, temp_name = tempfile.mkstemp(prefix=".lyria-config-", dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return value


def delete_settings(path: Path = CONFIG_PATH) -> None:
    path = Path(path).expanduser()
    if path.exists():
        if path.is_symlink() or path.stat().st_uid != os.getuid():
            raise CredentialError("unsafe_lyria_config_file")
        path.unlink()


def _gcloud() -> str | None:
    return shutil.which("gcloud")


def access_token(*, timeout: int = 20) -> str:
    command = _gcloud()
    if not command:
        raise CredentialError("gcloud_not_installed")
    try:
        result = subprocess.run(
            [command, "auth", "application-default", "print-access-token", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise CredentialError("google_adc_unavailable") from None
    token = result.stdout.strip()
    if result.returncode or not token or len(token) > 16384 or any(ch.isspace() for ch in token):
        raise CredentialError("google_adc_unavailable")
    return token


def connection_status(*, path: Path = CONFIG_PATH, check_auth: bool = True) -> dict:
    try:
        settings = load_settings(path)
    except CredentialError as exc:
        return {"state": "blocked", "configured": False, "auth_ready": False, "error": str(exc)}
    gcloud_ready = _gcloud() is not None
    if not settings:
        return {
            "state": "not_configured",
            "configured": False,
            "gcloud_ready": gcloud_ready,
            "auth_ready": False,
            "model": MODEL,
            "location": LOCATION,
        }
    auth_ready = False
    auth_error = None
    if check_auth:
        try:
            access_token()
            auth_ready = True
        except CredentialError as exc:
            auth_error = str(exc)
    return {
        "state": "ready" if settings["enabled"] and auth_ready else "configured",
        "configured": True,
        "gcloud_ready": gcloud_ready,
        "auth_ready": auth_ready,
        "auth_error": auth_error,
        "project_id": settings["project_id"],
        "candidate_count": settings["candidate_count"],
        "max_usd_per_run": settings["max_usd_per_run"],
        "enabled": settings["enabled"],
        "model": MODEL,
        "location": LOCATION,
        "estimated_unit_price_usd": UNIT_PRICE_USD,
        "live_generation_tested": False,
    }
