#!/usr/bin/env python3
"""Validate Codex review drafts before they enter the approval dashboard."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_manual_publish_site import read_csv_rows
from triage_store_reviews import triage_reviews

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("next update", "will be fixed", "refund approved", "guaranteed", "다음 업데이트", "고쳐드리", "환불해드리")


def validate(drafts_path: Path, reviews_path: Path) -> list[str]:
    if not drafts_path.exists():
        return []
    data = json.loads(drafts_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("drafts"), list):
        return ["draft file must contain schema_version 1 and a drafts array"]
    reviews = {row.get("review_id", ""): row for row in read_csv_rows(reviews_path)}
    triage = {item["review_id"]: item for item in triage_reviews(list(reviews.values()), (ROOT / "docs/operations/APP_FACTS.md", ROOT / "docs/operations/PRICING_FACTS.md"))["items"]}
    errors: list[str] = []; ids: set[str] = set(); replies: set[str] = set()
    for number, draft in enumerate(data["drafts"], 1):
        prefix = f"draft {number}"
        if not isinstance(draft, dict): errors.append(f"{prefix}: must be an object"); continue
        review_id, reply = str(draft.get("review_id", "")), str(draft.get("reply", "")).strip()
        review = reviews.get(review_id)
        if not review or review.get("developer_reply") or review.get("status") == "replied": errors.append(f"{prefix}: unknown or non-pending review_id")
        if not review_id or review_id in ids: errors.append(f"{prefix}: review_id must be unique")
        ids.add(review_id)
        if not reply or len(reply) > 350: errors.append(f"{prefix}: reply must be 1-350 characters")
        if any(term in reply.casefold() for term in FORBIDDEN): errors.append(f"{prefix}: contains a prohibited promise")
        normal = re.sub(r"\W+", "", reply.casefold())
        if normal and normal in replies: errors.append(f"{prefix}: duplicate reply text")
        replies.add(normal)
        allowed = {fact["source"] for fact in triage.get(review_id, {}).get("facts", [])}
        facts = draft.get("facts", [])
        if not isinstance(facts, list) or any(not isinstance(fact, dict) or fact.get("source") not in allowed for fact in facts): errors.append(f"{prefix}: facts must use approved sources")
        if review and review.get("reviewer_language", "").lower().startswith("ko") and not re.search(r"[가-힣]", reply): errors.append(f"{prefix}: Korean review requires Korean reply")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drafts", type=Path, default=ROOT / "data/store_review_ai_drafts.json")
    parser.add_argument("--reviews", type=Path, default=ROOT / "data/store_reviews.csv")
    args = parser.parse_args()
    try: errors = validate(args.drafts, args.reviews)
    except (OSError, json.JSONDecodeError) as error: errors = [str(error)]
    if errors:
        print("Review draft validation failed:", *[f"- {error}" for error in errors], sep="\n", file=sys.stderr); return 1
    print("Review drafts validated"); return 0


if __name__ == "__main__": raise SystemExit(main())
