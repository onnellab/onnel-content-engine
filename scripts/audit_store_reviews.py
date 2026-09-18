#!/usr/bin/env python3
"""Read-only store review audit; never publish replies or mutate the dashboard."""
from __future__ import annotations
import argparse
import base64
import csv
import io
import json
import os
import urllib.error
import urllib.parse
from pathlib import Path
import sync_store_reviews as sync


def review_id_from_link(link: str) -> str:
    """Support old and current Play Console report links without guessing IDs."""
    parsed = urllib.parse.urlsplit(link)
    for part in (parsed.query, parsed.fragment):
        for key, value in urllib.parse.parse_qsl(part):
            if key.casefold() in {"reviewid", "review_id"} and value.strip():
                return value.strip()
    marker = "ReviewPlace:id="
    if marker in link:
        return urllib.parse.unquote(link.split(marker, 1)[1].split("&", 1)[0]).strip()
    return ""


def credentials() -> tuple[str, str, str]:
    apple = os.environ.get("APP_STORE_CONNECT_TOKEN", "").strip()
    if not apple:
        key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "").strip()
        if not key and os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY_BASE64"):
            key = base64.b64decode(os.environ["APP_STORE_CONNECT_PRIVATE_KEY_BASE64"], validate=True).decode()
        if key:
            apple = sync.app_store_connect_token(os.environ.get("APP_STORE_CONNECT_KEY_ID", ""), os.environ.get("APP_STORE_CONNECT_ISSUER_ID", ""), key)
    google = os.environ.get("GOOGLE_PLAY_ACCESS_TOKEN", "").strip()
    if not google and os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64"):
        google = sync.google_play_access_token(base64.b64decode(os.environ["GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64"], validate=True).decode())
    bucket = sync.normalize_google_reports_bucket(os.environ.get("GOOGLE_PLAY_REPORTS_BUCKET", ""))
    if not apple or not google or not bucket:
        raise sync.StoreReviewSyncError("Configured Apple, Google and report-bucket credentials are required")
    return apple, google, bucket


def audit() -> dict:
    apple, google, bucket = credentials()
    timestamp = sync.now_iso()
    existing = sync.read_csv_rows(sync.DEFAULT_OUTPUT)
    result = {"checked_at": timestamp, "stores": []}
    for store in sync.read_csv_rows(sync.DEFAULT_STORES):
        slug, platform = store["app_slug"], store["platform"]
        prior = [r for r in existing if r["app_id"] == store["app_id"] and r["platform"] == platform]
        item = {"app_slug": slug, "platform": platform, "saved_count": len(prior)}
        result["stores"].append(item)
        if store.get("status") == "not_released":
            item["state"] = "not_released"
            continue
        try:
            if platform == "ios":
                app_id = sync.apple_store_app_id(store)
                if not app_id:
                    item["state"] = "unavailable"
                    continue
                url = f"https://api.appstoreconnect.apple.com/v1/apps/{urllib.parse.quote(app_id, safe='')}/customerReviews?limit=200&include=response"
                rows = sync.apple_review_rows(sync.fetch_apple_review_pages(url, apple), store, timestamp)
                item.update(state="complete", current_count=len(rows), rows=rows)
                continue
            package = sync.google_store_package(store)
            raw_reports = []
            def observe(url: str, token: str) -> bytes:
                raw = sync.fetch_bytes(url, token)
                encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
                for source in csv.DictReader(io.StringIO(raw.decode(encoding))):
                    link = source.get("Review Link", "")
                    parsed = urllib.parse.urlsplit(link)
                    raw_reports.append({
                        "review_id": review_id_from_link(link),
                        "link_keys": list(urllib.parse.parse_qs(parsed.query)),
                        "link_fragment": parsed.fragment[:80],
                        "body": source.get("Review Text", ""), "title": source.get("Review Title", ""),
                        "rating": source.get("Star Rating", ""),
                        "created_at": source.get("Review Submit Date and Time", ""),
                        "updated_at": source.get("Review Last Update Date and Time", ""),
                    })
                return raw
            reports = sync.google_report_review_rows(bucket, store, google, timestamp, bytes_fetcher=observe)
            base = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{urllib.parse.quote(package, safe='')}/reviews"
            recent = sync.google_review_rows(sync.fetch_google_review_pages(base + "?maxResults=100", google), store, timestamp)
            ids = sorted({r["review_id"] for r in raw_reports + reports + prior + recent if r.get("review_id") and not r["review_id"].startswith("report-")})
            states = []
            for review_id in ids:
                record = {"review_id": review_id}
                try:
                    payload = sync.fetch_json(base + "/" + urllib.parse.quote(review_id, safe=""), google)
                    record.update(http_status=200, rows=sync.google_review_rows({"reviews":[payload]}, store, timestamp))
                except urllib.error.HTTPError as error:
                    record["http_status"] = error.code
                states.append(record)
            item.update(state="complete", reports=reports, report_records=raw_reports, recent=recent, individual_checks=states)
        except urllib.error.HTTPError as error:
            item.update(state="error", http_status=error.code)
        except (sync.StoreReviewSyncError, ValueError, OSError):
            item.update(state="error", reason="source_fetch_or_parse_failed")
        print(json.dumps({k:v for k,v in item.items() if k not in {"rows","reports","report_records","recent","individual_checks"}}, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Read-only audit complete; no replies, review snapshots or dashboard files were modified.")
    return int(any(s.get("state") == "error" for s in data["stores"]))

if __name__ == "__main__":
    raise SystemExit(main())
