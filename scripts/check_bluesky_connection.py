#!/usr/bin/env python3
"""Check Bluesky credentials by creating a session without posting."""

from __future__ import annotations

import argparse
import json
import os
import sys

from post_social_drafts import bluesky_service_url, json_post
from publishing_adapters import AdapterError, require_adapter_ready


class BlueskyConnectionError(ValueError):
    """Raised when Bluesky preflight fails."""


def check_bluesky_connection() -> dict[str, object]:
    try:
        require_adapter_ready("bluesky", "social")
    except AdapterError as error:
        raise BlueskyConnectionError(str(error)) from error
    handle = os.environ["BLUESKY_HANDLE"]
    password = os.environ["BLUESKY_APP_PASSWORD"]
    service = bluesky_service_url()
    session = json_post(
        f"{service}/xrpc/com.atproto.server.createSession",
        {"identifier": handle, "password": password},
    )
    did = session.get("did")
    access_jwt = session.get("accessJwt")
    if not isinstance(access_jwt, str) or not access_jwt:
        raise BlueskyConnectionError("Bluesky session response did not include accessJwt")
    return {
        "service": service,
        "handle": handle,
        "did": did if isinstance(did, str) else "",
        "authenticated": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Bluesky connection without posting")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = check_bluesky_connection()
    except (BlueskyConnectionError, OSError, json.JSONDecodeError) as error:
        print(f"bluesky connection failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"bluesky connection ok: {result['handle']} {result['did']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
