#!/usr/bin/env python3
"""Approve an idea topic."""

from __future__ import annotations

import argparse
import sys

from topic_management import TopicError, TopicStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve a topic")
    parser.add_argument("topic_id")
    args = parser.parse_args()
    try:
        row = TopicStore().approve(args.topic_id)
    except TopicError as error:
        print(f"approve topic failed: {error}", file=sys.stderr)
        return 1
    print(row["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
