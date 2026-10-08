#!/usr/bin/env python3
"""Fail closed before canonical scheduling while the nine-locale migration runs.

Read-only: never generates, marks complete, changes a schedule, or publishes.
Historical published bilingual rows and idea/draft inventory are not rewritten.
"""
import argparse
import csv
from pathlib import Path
import sys

LANGUAGES = frozenset(("en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"))


def check_rows(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row["category"], row["slug"]), []).append(row)
    for (category, slug), group in groups.items():
        if not any(row["status"] in {"review", "scheduled"} for row in group):
            continue
        languages = [row["primary_language"] for row in group]
        if len(languages) != len(set(languages)):
            raise ValueError(f"{category}/{slug}: duplicate language rows")
        if set(languages) != LANGUAGES:
            missing = ", ".join(sorted(LANGUAGES - set(languages)))
            extra = ", ".join(sorted(set(languages) - LANGUAGES))
            raise ValueError(f"{category}/{slug}: all nine language manuscripts are required; missing={missing}; unsupported={extra}")
        statuses = {row["status"] for row in group}
        if statuses not in ({"review"}, {"scheduled"}):
            raise ValueError(f"{category}/{slug}: all nine manuscripts must be in the same review or scheduled stage")
        if statuses == {"scheduled"}:
            from datetime import datetime
            slots = [datetime.fromisoformat(row["scheduled_at"]) for row in group]
            if any(slot.tzinfo is None for slot in slots) or len(set(slots)) != 1:
                raise ValueError(f"{category}/{slug}: all nine manuscripts must share one timezone-aware publication instant")


def check_reviewed_candidates(topics_path, review_root=None):
    from schedule_ready_articles import current_review_score
    with topics_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    check_rows(rows)
    review_root = review_root or topics_path.parent.parent / "generated/reviews"
    candidates = [row for row in rows if row["status"] in {"review", "scheduled"}]
    for row in candidates:
        # Reuse the existing fail-closed persisted/current fingerprint, strict
        # >9.0 score and every-mandatory-check gate for every locale.
        if not current_review_score(row, topics_path, review_root, 9.0) > 9.0:
            raise ValueError(f"{row['category']}/{row['slug']}: locale {row['primary_language']} did not exceed 9.0")
    return len(candidates) // len(LANGUAGES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topics", type=Path, default=Path(__file__).resolve().parents[1] / "data/topics.csv")
    args = parser.parse_args()
    try:
        count = check_reviewed_candidates(args.topics)
    except (ValueError, KeyError, OSError) as error:
        print(f"nine-language publication held: {error}", file=sys.stderr)
        return 1
    print(f"Nine-language publication preflight: {count} complete currently reviewed bundle(s); existing scheduling and publication gates still apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
