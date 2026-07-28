#!/usr/bin/env python3
"""Create one approved GitHub issue from a review triage record."""
from __future__ import annotations
import argparse, csv, json, os, urllib.request
from pathlib import Path
from triage_store_reviews import triage_reviews

ROOT = Path(__file__).resolve().parents[1]

def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle))

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_id")
    parser.add_argument("--confirm-create", action="store_true")
    args = parser.parse_args()
    review_rows = rows(ROOT / "data/store_reviews.csv")
    review = next((row for row in review_rows if row.get("review_id") == args.review_id), None)
    triage = {item["review_id"]: item for item in triage_reviews(review_rows, (ROOT / "docs/operations/APP_FACTS.md", ROOT / "docs/operations/PRICING_FACTS.md"))["items"]}
    item = triage.get(args.review_id, {})
    if not review or item.get("actions", {}).get("github_issue") != "approval_required": raise SystemExit("review is not eligible for an issue")
    if not args.confirm_create:
        print(f"dry run: would create issue for {args.review_id}"); return 0
    repo = next((row.get("repository", "") for row in rows(ROOT / "data/app_release_config.csv") if row.get("app_id") == review.get("app_id")), "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token: raise SystemExit("repository mapping and GITHUB_TOKEN are required")
    body = json.dumps({"title": f"Review report: {item['category']} ({review.get('app_version','unknown version')})", "body": item.get("issue_draft", "")}).encode()
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues", data=body, method="POST", headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as response: created = json.loads(response.read().decode())
    audit_path = ROOT / "data/review_issue_publications.json"; audit = json.loads(audit_path.read_text(encoding="utf-8")); audit["items"].append({"review_id":args.review_id,"repository":repo,"issue_number":created.get("number"),"issue_url":created.get("html_url")}); audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(created.get("html_url", "created")); return 0
if __name__ == "__main__": raise SystemExit(main())
