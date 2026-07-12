#!/usr/bin/env python3
"""Check environment variables required by publishing adapters."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from publishing_adapters import ADAPTERS, AdapterError, adapter_spec, missing_credentials


FOREM_API_ACCEPT = "application/vnd.forem.api-v1+json"
ONNELLAB_USER_AGENT = "ONNELLAB content engine"


class CredentialPreflightError(ValueError):
    """Raised when a live credential preflight fails."""


def json_request(
    url: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise CredentialPreflightError(f"HTTP {error.code} from {url}: {detail}") from error


def form_request(url: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict[str, object]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise CredentialPreflightError(f"HTTP {error.code} from {url}: {detail}") from error


def bluesky_service_url() -> str:
    return os.environ.get("BLUESKY_SERVICE", "https://bsky.social").rstrip("/")


def x_basic_auth_header() -> str:
    credentials = f"{os.environ['X_CLIENT_ID']}:{os.environ['X_CLIENT_SECRET']}".encode("utf-8")
    return f"Basic {base64.b64encode(credentials).decode('ascii')}"


def x_refresh_token() -> str:
    token_file = os.environ.get("X_REFRESH_TOKEN_FILE", "").strip()
    if token_file:
        path = Path(token_file)
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
    return os.environ["X_REFRESH_TOKEN"]


def persist_x_refresh_token(refresh_token: str, previous_refresh_token: str) -> None:
    if refresh_token == previous_refresh_token:
        return
    token_file = os.environ.get("X_REFRESH_TOKEN_FILE", "").strip()
    if token_file:
        path = Path(token_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{refresh_token}\n", encoding="utf-8")
        return
    print("X OAuth returned a rotated refresh token. Update X_REFRESH_TOKEN in your secret store.", file=sys.stderr)


def refresh_x_access_token() -> str:
    current_refresh_token = x_refresh_token()
    response = form_request(
        "https://api.x.com/2/oauth2/token",
        {
            "grant_type": "refresh_token",
            "refresh_token": current_refresh_token,
            "client_id": os.environ["X_CLIENT_ID"],
        },
        {"Authorization": x_basic_auth_header()},
    )
    access_token = response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise CredentialPreflightError("X OAuth refresh response did not include access_token")
    refresh_token = response.get("refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        persist_x_refresh_token(refresh_token, current_refresh_token)
    return access_token


def live_preflight(adapter: str) -> dict[str, object]:
    if adapter == "bluesky":
        response = json_request(
            f"{bluesky_service_url()}/xrpc/com.atproto.server.createSession",
            "POST",
            {"identifier": os.environ["BLUESKY_HANDLE"], "password": os.environ["BLUESKY_APP_PASSWORD"]},
        )
        access_jwt = response.get("accessJwt")
        if not isinstance(access_jwt, str) or not access_jwt:
            raise CredentialPreflightError("Bluesky session response did not include accessJwt")
        return {"authenticated": True, "identity": response.get("did", "")}
    if adapter == "devto":
        response = json_request(
            "https://dev.to/api/users/me",
            headers={
                "api-key": os.environ["DEVTO_API_KEY"],
                "Accept": FOREM_API_ACCEPT,
                "User-Agent": ONNELLAB_USER_AGENT,
            },
        )
        username = response.get("username") or response.get("name") or response.get("id", "")
        return {"authenticated": True, "identity": username}
    if adapter == "hashnode":
        response = json_request(
            "https://gql.hashnode.com",
            "POST",
            {"query": "query Viewer { me { id username } }"},
            {"Authorization": os.environ["HASHNODE_TOKEN"]},
        )
        errors = response.get("errors")
        if errors:
            raise CredentialPreflightError(f"Hashnode GraphQL errors: {errors}")
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("me"), dict):
            raise CredentialPreflightError("Hashnode response did not include viewer")
        me = data["me"]
        return {"authenticated": True, "identity": me.get("username") or me.get("id", "")}
    if adapter == "x":
        access_token = refresh_x_access_token()
        response = json_request(
            "https://api.x.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = response.get("data")
        if not isinstance(data, dict):
            raise CredentialPreflightError("X response did not include data")
        return {"authenticated": True, "identity": data.get("username") or data.get("id", "")}
    raise CredentialPreflightError(f"live preflight is not supported for {adapter}")


def credential_status(adapter: str, live: bool = False) -> dict[str, object]:
    spec = adapter_spec(adapter)
    missing = missing_credentials(adapter)
    ready = not missing and spec.implemented
    result: dict[str, object] = {
        "adapter": adapter,
        "ready": ready,
        "implemented": spec.implemented,
        "required": list(spec.required_env),
        "missing": missing,
        "note": spec.note,
        "live_checked": False,
        "live_ok": False,
        "identity": "",
        "error": "",
    }
    if live and ready and adapter in {"bluesky", "devto", "x"}:
        result["live_checked"] = True
        try:
            preflight = live_preflight(adapter)
            result["live_ok"] = bool(preflight.get("authenticated"))
            result["identity"] = str(preflight.get("identity") or "")
        except Exception as error:
            result["live_ok"] = False
            result["error"] = str(error)
    return result


def credential_report(adapter: str | None = None, live: bool = False) -> str:
    names = [adapter] if adapter else sorted(name for name in ADAPTERS if name != "mock")
    lines: list[str] = []
    for name in names:
        status_item = credential_status(name, live)
        status = "ready" if status_item["ready"] else "not ready"
        if not status_item["implemented"] and not status_item["required"]:
            status = "adapter not implemented"
        elif not status_item["implemented"] and not status_item["missing"]:
            status = "credentials present, adapter not implemented"
        lines.append(f"{name}: {status}")
        if status_item["required"]:
            lines.append(f"  required: {', '.join(status_item['required'])}")
        if status_item["missing"]:
            lines.append(f"  missing: {', '.join(status_item['missing'])}")
        if status_item["live_checked"]:
            live_status = "ok" if status_item["live_ok"] else "failed"
            identity = f" ({status_item['identity']})" if status_item["identity"] else ""
            lines.append(f"  live: {live_status}{identity}")
            if status_item["error"]:
                lines.append(f"  live_error: {status_item['error']}")
        elif live and status_item["ready"]:
            lines.append("  live: skipped")
        lines.append(f"  note: {status_item['note']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check publishing adapter credentials")
    parser.add_argument("--adapter")
    parser.add_argument("--live", action="store_true", help="Call safe authentication endpoints without posting")
    args = parser.parse_args()
    try:
        print(credential_report(args.adapter, args.live))
    except (AdapterError, CredentialPreflightError, OSError, json.JSONDecodeError) as error:
        print(f"credential check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
