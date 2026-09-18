#!/usr/bin/env python3
"""Run deterministic unit tests; reject accidental network access in this process."""
from __future__ import annotations

import argparse
import importlib.util
import socket
import sys
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class UnexpectedNetworkAccess(AssertionError):
    """An unmocked transport was reached by a unit test."""


@contextmanager
def offline_network():
    """Track attempts too: catching a broad exception must not hide a live call."""
    attempts: list[str] = []

    def reject(*_args, **_kwargs):
        message = 'Unit tests must inject a fixed transport; network access is disabled.'
        attempts.append(message)
        raise UnexpectedNetworkAccess(message)

    with ExitStack() as stack:
        for owner, name in (
            (socket, 'getaddrinfo'), (socket, 'create_connection'),
            (socket.socket, 'connect'), (socket.socket, 'connect_ex'),
            (socket.socket, 'sendto'),
        ):
            stack.enter_context(patch.object(owner, name, side_effect=reject))
        yield attempts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pattern', default='test_*.py')
    parser.add_argument('--verbosity', type=int, choices=(0, 1, 2), default=1)
    args = parser.parse_args()
    if importlib.util.find_spec('yaml') is None:
        print('Install test dependencies first: python -m pip install -r requirements-test.txt', file=sys.stderr)
        return 2
    with offline_network() as attempts:
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=args.pattern)
        if suite.countTestCases() == 0:
            print(f'No tests matched {args.pattern!r}; refusing an empty pass.', file=sys.stderr)
            return 2
        result = unittest.TextTestRunner(verbosity=args.verbosity).run(suite)
    if attempts:
        print(f'FAILED: {len(attempts)} unexpected network attempt(s), even if caught by tested code.', file=sys.stderr)
    return 0 if result.wasSuccessful() and not attempts else 1


if __name__ == '__main__':
    raise SystemExit(main())
