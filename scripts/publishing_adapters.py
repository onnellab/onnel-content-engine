#!/usr/bin/env python3
"""Publishing adapter registry and credential checks."""

from __future__ import annotations

import os
from dataclasses import dataclass


class AdapterError(ValueError):
    """Raised when a publishing adapter cannot run."""


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    kind: str
    required_env: tuple[str, ...]
    implemented: bool
    note: str


ADAPTERS: dict[str, AdapterSpec] = {
    "mock": AdapterSpec("mock", "all", (), True, "Local manifest update only."),
    "bluesky": AdapterSpec(
        "bluesky",
        "social",
        ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"),
        True,
        "Bluesky posting with clickable link facets and website card embeds.",
    ),
    "x": AdapterSpec(
        "x",
        "social",
        ("X_BEARER_TOKEN",),
        True,
        "X API v2 text post creation.",
    ),
    "devto": AdapterSpec(
        "devto",
        "syndication",
        ("DEVTO_API_KEY",),
        True,
        "Unpublished Dev.to draft posting.",
    ),
    "hashnode": AdapterSpec(
        "hashnode",
        "syndication",
        ("HASHNODE_TOKEN", "HASHNODE_PUBLICATION_ID"),
        True,
        "Hashnode GraphQL draft posting.",
    ),
    "linkedin": AdapterSpec("linkedin", "social", (), False, "Unsupported until account and permission scope are defined."),
    "medium": AdapterSpec("medium", "syndication", (), False, "Export-only. No supported real API adapter."),
}


def adapter_spec(name: str) -> AdapterSpec:
    try:
        return ADAPTERS[name]
    except KeyError as error:
        raise AdapterError(f"unknown publishing adapter: {name}") from error


def missing_credentials(name: str, environ: dict[str, str] | None = None) -> list[str]:
    env = environ if environ is not None else os.environ
    spec = adapter_spec(name)
    return [key for key in spec.required_env if not env.get(key)]


def require_adapter_ready(name: str, expected_kind: str, environ: dict[str, str] | None = None) -> AdapterSpec:
    spec = adapter_spec(name)
    if spec.kind not in {expected_kind, "all"}:
        raise AdapterError(f"adapter {name} is for {spec.kind}, not {expected_kind}")
    missing = missing_credentials(name, environ)
    if missing:
        raise AdapterError(f"adapter {name} is missing credentials: {', '.join(missing)}")
    if not spec.implemented:
        raise AdapterError(f"adapter {name} is not implemented yet: {spec.note}")
    return spec
