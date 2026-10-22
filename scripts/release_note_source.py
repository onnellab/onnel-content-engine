#!/usr/bin/env python3
"""Read the nine-language release notes authored beside each app's upload config.

Public store version discovery is used only as a publication gate. Neither the
version number nor a GitHub commit summary is a sufficient customer changelog.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from typing import Any

LOCALES = ("ko", "en", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es")
SOURCES = {
    "aligna": ("onnellab/aligna", "release/store_release_notes.json"),
    "clipnest": ("onnellab/clipnest", "release/store_release_notes.json"),
    "melivra": ("onnellab/melivra", "release/store_release_notes.json"),
    "papira": ("onnellab/papira", "release/store_release_notes.json"),
    "quivra": ("onnellab/quivra", "release/store_release_notes.json"),
    "segra": ("onnellab/segra", "release/store_release_notes.json"),
    "tagweaver": ("onnellab/tagweaver", "release/store_release_notes.json"),
    "vaultxt": ("onnellab/onnellab-text", "vaultxt/release/store_release_notes.json"),
}
SUMMARY_FORMATS = {
    "ko": "{app} {version} 버전의 변경 사항이에요.",
    "en": "Changes in {app} {version}.",
    "ja": "{app} {version}の変更点です。",
    "zh-Hans": "{app} {version} 的更新内容。",
    "zh-Hant": "{app} {version} 的更新內容。",
    "pt-BR": "Novidades do {app} {version}.",
    "de": "Neuerungen in {app} {version}.",
    "fr": "Nouveautés de {app} {version}.",
    "es": "Novedades de {app} {version}.",
}
GENERIC = (
    " is now available ", " store update detected", " public release",
    " 버전이 ", " 공개됐어요", "latest public store release",
)


def validate_note(slug: str, value: Any) -> dict[str, Any]:
    """Fail closed on missing locales, stale versions or copied English text."""
    if not isinstance(value, dict) or set(value) != {"version", "locales"}:
        raise ValueError(f"{slug}: invalid release note schema")
    if not isinstance(value["version"], str) or not re.fullmatch(
        r"\d+\.\d+(?:\.\d+)?\+\d+", value["version"]
    ):
        raise ValueError(f"{slug}: release note version must include build number")
    notes = value["locales"]
    if not isinstance(notes, dict) or set(notes) != set(LOCALES):
        raise ValueError(f"{slug}: expected nine localized release notes")
    for locale, body in notes.items():
        if (not isinstance(body, str) or not body.strip() or body != body.strip()
                or len(body) > 500 or any(not line.strip().removeprefix("- ").strip()
                                          for line in body.splitlines())):
            raise ValueError(f"{slug}: missing or invalid {locale} release-note text")
        if any(generic in body.casefold() for generic in GENERIC):
            raise ValueError(f"{slug}: generic release statement in {locale}")
    if len(set(notes.values())) != len(LOCALES):
        raise ValueError(f"{slug}: locale text is copied instead of translated")
    return value


def fetch_source_notes(token: str | None = None) -> dict[str, dict[str, Any]]:
    """Fetch only fixed, allowlisted GitHub files, not arbitrary user URLs."""
    token = token if token is not None else (
        os.environ.get("ONNELLAB_RELEASE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    )
    if not token:
        return {}
    result = {}
    for slug, (repository, path) in SOURCES.items():
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/contents/{path}?ref=main",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ONNELLAB release notes",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
        if payload.get("encoding") != "base64":
            raise ValueError(f"{slug}: unrecognized GitHub content encoding")
        raw = base64.b64decode(payload["content"])
        if len(raw) > 20000:
            raise ValueError(f"{slug}: release notes are unexpectedly large")
        result[slug] = validate_note(slug, json.loads(raw))
    return result


def localized_content(
    app_slug: str, app_name: str, version: str, sources: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    source = sources.get(app_slug)
    if not source or source["version"].split("+", 1)[0] != version:
        return None
    notes = source["locales"]
    copies = {}
    for locale in LOCALES:
        changes = [line.strip().removeprefix("- ").strip() for line in notes[locale].splitlines()]
        copies[locale] = {
            "summary": SUMMARY_FORMATS[locale].format(app=app_name, version=version),
            "changes": changes,
        }
    return {
        "summary": copies["en"]["summary"],
        "summaryKo": copies["ko"]["summary"],
        "changes": copies["en"]["changes"],
        "changesKo": copies["ko"]["changes"],
        "localizations": copies,
    }
