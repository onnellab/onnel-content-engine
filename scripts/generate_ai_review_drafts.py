#!/usr/bin/env python3
"""Generate one fact-grounded, review-specific reply draft per pending review.

Requires OPENAI_API_KEY. The generated drafts are never published and remain
subject to the existing human approval and policy checks.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from build_manual_publish_site import read_csv_rows
from store_review_responses import generate_reply
from triage_store_reviews import triage_reviews

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEWS = ROOT / "data" / "store_reviews.csv"
DEFAULT_OUTPUT = ROOT / "data" / "store_review_ai_drafts.json"
MODEL = "gpt-5-mini"
FORBIDDEN = ("next update", "will be fixed", "refund approved", "guaranteed", "다음 업데이트", "고쳐드리", "환불해드리")


def request_reply(api_key: str, review: dict[str, str], facts: list[dict[str, str]]) -> str:
    language = "Korean" if review.get("reviewer_language", "").lower().startswith("ko") else "the review's language, or English"
    prompt = {
        "role": "user",
        "content": "Write one concise, warm public app-store reply in " + language + ". "
        "Address the specific review without repeating it verbatim. Use only these approved facts: "
        + json.dumps(facts, ensure_ascii=False) + ". Never claim a cause, fix, release date, refund, or future feature. "
        "Never request personal data. Return only the reply text. Review: "
        + json.dumps({k: review.get(k, "") for k in ("app_name", "rating", "title", "body", "app_version")}, ensure_ascii=False),
    }
    body = json.dumps({"model": MODEL, "input": [prompt], "max_output_tokens": 220, "store": False}).encode()
    request = urllib.request.Request("https://api.openai.com/v1/responses", data=body, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    text = str(payload.get("output_text", "")).strip()
    if not text or len(text) > 1000 or any(word in text.casefold() for word in FORBIDDEN):
        raise ValueError("AI response failed local reply safety validation")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Create custom AI reply drafts; never publishes")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required; no drafts were generated")
    rows = read_csv_rows(args.reviews)
    triage = {item["review_id"]: item for item in triage_reviews(rows, (ROOT / "docs/operations/APP_FACTS.md", ROOT / "docs/operations/PRICING_FACTS.md"))["items"]}
    drafts = []
    for review in rows:
        if review.get("developer_reply") or review.get("status") == "replied":
            continue
        details = triage.get(review.get("review_id", ""), {})
        try:
            reply = request_reply(api_key, review, details.get("facts", []))
            source = "ai"
        except (ValueError, OSError, json.JSONDecodeError):
            reply = generate_reply(review)["suggested_reply"]
            source = "safe_template_fallback"
        drafts.append({"review_id": review.get("review_id", ""), "reply": reply, "source": source, "facts": details.get("facts", [])})
    args.output.write_text(json.dumps({"schema_version": 1, "model": MODEL, "drafts": drafts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
