#!/usr/bin/env python3
"""Edit an existing topic row."""

from __future__ import annotations

import argparse
import sys

from topic_management import EDITABLE_FIELDS, TopicError, TopicStore


CLI_FIELDS = sorted(EDITABLE_FIELDS)


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Edit a topic in data/topics.csv")
    parser.add_argument("topic_id")
    for field in CLI_FIELDS:
        parser.add_argument(f"--{field.replace('_', '-')}", dest=field)
    return parser


def main() -> int:
    args = parser().parse_args()
    fields = {field: getattr(args, field) for field in CLI_FIELDS if getattr(args, field) is not None}
    try:
        row = TopicStore().edit(args.topic_id, fields)
    except TopicError as error:
        print(f"edit topic failed: {error}", file=sys.stderr)
        return 1
    print(row["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
