#!/usr/bin/env python3
"""Archive a topic when the specification permits it."""

from __future__ import annotations

import argparse
import sys

from topic_management import TopicError, TopicStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive a topic")
    parser.add_argument("topic_id")
    args = parser.parse_args()
    try:
        row = TopicStore().archive(args.topic_id)
    except TopicError as error:
        print(f"archive topic failed: {error}", file=sys.stderr)
        return 1
    print(row["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
