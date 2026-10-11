#!/usr/bin/env python3
"""Reject conflicted or duplicate-payload dashboard HTML before commit/deploy."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


class DashboardArtifactError(ValueError):
    pass


class _DashboardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.payloads: dict[str, str] = {}
        self.current = ''

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get('id') or ''
        if identifier:
            self.ids.append(identifier)
        if tag == 'script' and values.get('type') == 'application/json':
            self.current = identifier
            self.payloads[identifier] = ''

    def handle_data(self, data: str) -> None:
        if self.current:
            self.payloads[self.current] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script':
            self.current = ''


def validate_dashboard(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if re.search(r'^\s*(?:<{7}|>{7}|={7}(?:\s|$))', text, re.M):
        raise DashboardArtifactError('Dashboard contains unresolved merge-conflict markers')
    parser = _DashboardParser()
    parser.feed(text)
    parser.close()
    duplicates = [identifier for identifier, count in Counter(parser.ids).items() if count > 1]
    if duplicates:
        raise DashboardArtifactError('Dashboard contains duplicate element IDs: ' + ', '.join(sorted(duplicates)))
    required = {'manual-data', 'manual-state-data', 'store-review-data', 'store-review-sync-data', 'verification-report-data'}
    missing = required - parser.payloads.keys()
    if missing:
        raise DashboardArtifactError('Dashboard is missing payloads: ' + ', '.join(sorted(missing)))
    for identifier, value in parser.payloads.items():
        try:
            json.loads(value)
        except json.JSONDecodeError as error:
            raise DashboardArtifactError(f'Dashboard payload {identifier} is invalid JSON') from error


def validate_sealed_dashboard(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "ops-sealed-data" not in text or "PBKDF2" not in text:
        raise DashboardArtifactError("Sealed dashboard is missing its encrypted login shell")
    if ('rel="icon" href="/favicon.svg?v=20261008-open-monogram-v1"' not in text
            or "20260712-ol-transparent-v2" in text):
        raise DashboardArtifactError("Sealed dashboard branding is stale or missing")
    if path.parent.name == "ops":
        # The root's PWA icons must survive every destructive encrypted republish.
        signature = bytes.fromhex("89504e470d0a1a0a")
        for size in (180, 192, 512):
            icon = path.parent / f"icon-{size}.png"
            try:
                blob = icon.read_bytes()
            except OSError as error:
                raise DashboardArtifactError(f"Sealed dashboard icon missing: {icon.name}") from error
            if (len(blob) < 33 or blob[:8] != signature
                    or int.from_bytes(blob[16:20], "big") != size
                    or int.from_bytes(blob[20:24], "big") != size):
                raise DashboardArtifactError(f"Sealed dashboard icon invalid: {icon.name}")
    if any(secret_marker in text for secret_marker in (
        'id="manual-data"', 'id="store-review-data"', 'id="sales-ledger"',
        '<nav class="ops-nav"', 'data-ops-view="home"'
    )):
        raise DashboardArtifactError("Plain dashboard payload leaked into sealed deployment")
    match = re.search(r'<script type="application/json" id="ops-sealed-data">(.*?)</script>', text, re.S)
    if not match:
        raise DashboardArtifactError("Sealed dashboard is missing the ciphertext payload")
    try:
        record = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise DashboardArtifactError("Invalid ciphertext wrapper JSON") from error
    if (record.get("v") != 1 or record.get("it", 0) < 300000
            or not all(record.get(key) for key in ("salt", "iv", "tag", "data", "path"))):
        raise DashboardArtifactError("Incomplete or weak encrypted payload")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--sealed', action='store_true')
    args = parser.parse_args()
    try:
        (validate_sealed_dashboard if args.sealed else validate_dashboard)(args.path)
    except (OSError, UnicodeError, DashboardArtifactError) as error:
        print(f'Dashboard validation failed: {error}', file=sys.stderr)
        return 1
    print('Dashboard artifact is complete, unambiguous and free of conflict markers.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
