#!/usr/bin/env python3
"""Create a Codex review-reply packet; this command never calls an API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_manual_publish_site import read_csv_rows
from triage_store_reviews import triage_reviews

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEWS = ROOT / "data" / "store_reviews.csv"
DEFAULT_OUTPUT = ROOT / "generated" / "review-replies" / "review_packet.json"
DEFAULT_MARKDOWN = ROOT / "generated" / "review-replies" / "review_packet.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Codex packet for personalized review replies")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    rows = [row for row in read_csv_rows(args.reviews) if not row.get("developer_reply") and row.get("status") != "replied"]
    triage = {item["review_id"]: item for item in triage_reviews(rows, (ROOT / "docs/operations/APP_FACTS.md", ROOT / "docs/operations/PRICING_FACTS.md"))["items"]}
    packet = [{"review": row, "triage": triage.get(row.get("review_id", ""), {})} for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "reviews": packet}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text("# Codex review reply packet\n\nRead `prompts/codex_review_replies.md`, then create `data/store_review_ai_drafts.json`.\n\n" + json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {args.output} and {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
