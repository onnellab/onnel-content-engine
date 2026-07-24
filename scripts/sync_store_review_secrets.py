#!/usr/bin/env python3
"""Sync store-review API credentials into GitHub Actions secrets."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


DEFAULT_REPOSITORY = "onnellab/onnel-content-engine"
SECRET_KEYS = (
    "APP_STORE_CONNECT_KEY_ID",
    "APP_STORE_CONNECT_ISSUER_ID",
    "APP_STORE_CONNECT_PRIVATE_KEY_BASE64",
)


class SecretSyncError(ValueError):
    """Raised when required store-review credentials are unavailable."""


def sync_secret(repository: str, key: str, value: str, dry_run: bool = False) -> None:
    if dry_run:
        print(f"would sync {key} to {repository}")
        return
    subprocess.run(
        ["gh", "secret", "set", key, "--repo", repository, "--body-file", "-"],
        input=value,
        text=True,
        check=True,
    )


def sync_store_review_secrets(
    repository: str = DEFAULT_REPOSITORY,
    dry_run: bool = False,
) -> list[str]:
    missing = [key for key in SECRET_KEYS if not os.environ.get(key, "").strip()]
    if missing:
        raise SecretSyncError("missing required environment variables: " + ", ".join(missing))
    synced: list[str] = []
    for key in SECRET_KEYS:
        sync_secret(repository, key, os.environ[key], dry_run)
        synced.append(key)
    return synced


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync store-review credentials to GitHub Actions secrets")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        synced = sync_store_review_secrets(args.repository, args.dry_run)
    except (SecretSyncError, OSError, subprocess.CalledProcessError) as error:
        print(f"store-review secret sync failed: {error}", file=sys.stderr)
        return 1
    action = "would sync" if args.dry_run else "synced"
    print(f"{action} {len(synced)} store-review secret(s): {', '.join(synced)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
