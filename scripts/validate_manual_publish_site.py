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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        validate_dashboard(args.path)
    except (OSError, UnicodeError, DashboardArtifactError) as error:
        print(f'Dashboard validation failed: {error}', file=sys.stderr)
        return 1
    print('Dashboard artifact is complete, unambiguous and free of conflict markers.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
