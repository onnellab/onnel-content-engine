#!/usr/bin/env python3
"""Create deterministic, fact-grounded triage records for store reviews.

This is intentionally a workflow stage, not a publisher.  Its JSON output is
reviewable input for the dashboard and no code in this module calls a store or
GitHub write API.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEWS = ROOT / "data" / "store_reviews.csv"
DEFAULT_OUTPUT = ROOT / "data" / "store_review_triage.json"
DEFAULT_APP_FACTS = ROOT / "docs" / "operations" / "APP_FACTS.md"
DEFAULT_PRICING_FACTS = ROOT / "docs" / "operations" / "PRICING_FACTS.md"

RISK_TERMS = {
    "billing": ("paid", "pay", "payment", "purchase", "refund", "charged", "free", "결제", "구매", "환불", "무료"),
    "privacy": ("privacy", "personal data", "tracking", "개인정보", "추적"),
    "security": ("security", "hack", "password", "보안", "해킹", "비밀번호"),
    "data_loss": ("lost", "deleted", "missing", "data loss", "사라", "삭제", "유실"),
    "bug": ("crash", "crashed", "freeze", "error", "doesn't work", "does not work", "failed", "버그", "크래시", "오류", "안 됨", "안됨"),
    "feature": ("feature", "please add", "would like", "support", "기능", "추가", "지원"),
}
PRICING_CONFUSION = ("not free", "actually a paid", "paid app", "free as stated", "무료가 아니", "유료")


def read_reviews(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def facts_for_app(app_slug: str, paths: tuple[Path, ...]) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    marker = f"- [{app_slug.lower()}]"
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lower().startswith(marker):
                facts.append({"text": line.split("]", 1)[1].strip(), "source": f"{path.relative_to(ROOT)}:{line_number}"})
    return facts


def matching_categories(text: str) -> list[str]:
    lowered = text.casefold()
    return [category for category, terms in RISK_TERMS.items() if any(term in lowered for term in terms)]


def classify(row: dict[str, str]) -> tuple[str, list[str], str]:
    text = " ".join((row.get("title", ""), row.get("body", ""))).casefold()
    flags = matching_categories(text)
    if any(term in text for term in PRICING_CONFUSION):
        return "pricing_confusion", sorted(set(flags + ["billing"])), "pricing_free_vs_pro_confusion"
    if "data_loss" in flags:
        return "data_loss", flags, "data_loss"
    if "security" in flags:
        return "security", flags, "security"
    if "privacy" in flags:
        return "privacy", flags, "privacy"
    if "billing" in flags:
        return "billing", flags, "billing"
    if "bug" in flags:
        return "bug", flags, "bug"
    if "feature" in flags:
        return "feature_request", flags, "feature_request"
    try:
        rating = int(row.get("rating", "0"))
    except ValueError:
        rating = 0
    return ("praise" if rating >= 4 else "general_feedback"), flags, ("praise" if rating >= 4 else "general_feedback")


def issue_draft(row: dict[str, str], category: str, key: str) -> str:
    return "\n".join((
        "## Customer report (unverified)",
        f"- App: {row.get('app_name', row.get('app_slug', ''))}",
        f"- Platform/version: {row.get('platform', '')} {row.get('app_version', '')}".rstrip(),
        f"- Category: {category}",
        f"- Similarity key: {key}",
        "", "## Sanitized summary", "Customer reported a possible product problem. Review the original in the approval dashboard; do not copy personal data into this issue.",
        "", "## Required before implementation", "- Reproduce or identify telemetry evidence.", "- Confirm affected versions and rollback path.",
    ))


def triage_reviews(rows: list[dict[str, str]], fact_paths: tuple[Path, ...]) -> dict[str, object]:
    classified = [classify(row) for row in rows]
    counts = Counter(key for _, _, key in classified)
    items: list[dict[str, object]] = []
    for row, (category, flags, key) in zip(rows, classified):
        try:
            rating = int(row.get("rating", "0"))
        except ValueError:
            rating = 0
        facts = facts_for_app(row.get("app_slug", ""), fact_paths)
        sensitive = {"billing", "privacy", "security", "data_loss"}.intersection(flags)
        requires_issue = category in {"bug", "data_loss", "security"} or (category == "pricing_confusion" and counts[key] >= 3)
        requires_manual = rating <= 3 or bool(sensitive) or category not in {"praise", "general_feedback"}
        actions = {
            "reply": "recommended" if not row.get("developer_reply", "") else "not_needed",
            "github_issue": "approval_required" if requires_issue else "not_needed",
            "store_copy": "review_recommended" if category == "pricing_confusion" and counts[key] >= 3 else "not_needed",
            "code_change": "investigate" if category in {"bug", "data_loss", "security"} else "not_needed",
        }
        items.append({
            "review_id": row.get("review_id", ""), "category": category, "risk_flags": flags,
            "similarity_key": key, "similar_reviews": counts[key], "facts": facts,
            "requires_human_approval": requires_manual, "actions": actions,
            "issue_draft": issue_draft(row, category, key) if requires_issue else "",
        })
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "items": items}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create review triage records; never publishes externally")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--app-facts", type=Path, default=DEFAULT_APP_FACTS)
    parser.add_argument("--pricing-facts", type=Path, default=DEFAULT_PRICING_FACTS)
    args = parser.parse_args()
    payload = triage_reviews(read_reviews(args.reviews), (args.app_facts, args.pricing_facts))
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
