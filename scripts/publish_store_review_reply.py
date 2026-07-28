#!/usr/bin/env python3
"""Publish one explicitly approved store-review reply and audit the result."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sync_store_reviews import app_store_connect_token, google_play_access_token, urlopen_with_retry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPROVALS = ROOT / "data" / "store_review_approvals.json"
DEFAULT_STORES = ROOT / "data" / "store_versions.csv"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_request(url: str, token: str, method: str, body: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "ONNELLAB-Store-Review-Publisher/1.0",
    })
    with urlopen_with_retry(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    return payload if isinstance(payload, dict) else {}


def credentials() -> tuple[str, str]:
    apple = os.environ.get("APP_STORE_CONNECT_TOKEN", "").strip()
    if not apple:
        key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "").strip()
        if not key and os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY_BASE64", "").strip():
            key = base64.b64decode(os.environ["APP_STORE_CONNECT_PRIVATE_KEY_BASE64"], validate=True).decode()
        if key:
            apple = app_store_connect_token(os.environ.get("APP_STORE_CONNECT_KEY_ID", ""), os.environ.get("APP_STORE_CONNECT_ISSUER_ID", ""), key)
    google = os.environ.get("GOOGLE_PLAY_ACCESS_TOKEN", "").strip()
    if not google and os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64", "").strip():
        service_json = base64.b64decode(os.environ["GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64"], validate=True).decode()
        google = google_play_access_token(service_json)
    return apple, google


def package_for(record: dict[str, object], stores_path: Path) -> str:
    with stores_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("app_id") == record.get("app_id") and row.get("platform") == "android":
                url = row.get("store_url", "")
                return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("id", [""])[0]
    return ""


def publish(record: dict[str, object], apple_token: str, google_token: str, stores_path: Path, requester=json_request) -> str:
    reply = str(record["reply"])
    if record.get("platform") == "android":
        if len(reply) > 350:
            raise ValueError("Google Play review replies must be at most approximately 350 characters")
        package = package_for(record, stores_path)
        if not package or not google_token:
            raise ValueError("Google Play package name and credentials are required")
        result = requester(
            "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
            f"{urllib.parse.quote(package)}/reviews/{urllib.parse.quote(str(record['review_id']))}:reply",
            google_token, "POST", {"replyText": reply},
        )
        return str(result.get("result", {}).get("lastEdited", {}).get("seconds", "google-play"))
    if record.get("platform") == "ios":
        if not apple_token:
            raise ValueError("App Store Connect credentials are required")
        result = requester("https://api.appstoreconnect.apple.com/v1/customerReviewResponses", apple_token, "POST", {
            "data": {"type": "customerReviewResponses", "attributes": {"responseBody": reply}, "relationships": {
                "review": {"data": {"type": "customerReviews", "id": str(record["review_id"])}}
            }}
        })
        return str(result.get("data", {}).get("id", "app-store"))
    raise ValueError("unsupported review platform")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish exactly one approved review reply")
    parser.add_argument("approval_id")
    parser.add_argument("--confirm-publish", action="store_true", help="Required for an external store write")
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    args = parser.parse_args()
    payload = json.loads(args.approvals.read_text(encoding="utf-8"))
    records = payload.get("approvals", [])
    record = next((item for item in records if item.get("approval_id") == args.approval_id), None)
    if not isinstance(record, dict) or record.get("status") != "queued":
        raise SystemExit("approval must exist and be queued")
    if not args.confirm_publish:
        print(f"dry run: would publish {args.approval_id}; pass --confirm-publish to write externally")
        return 0
    apple, google = credentials()
    external_id = publish(record, apple, google, args.stores)
    record["status"] = "published"
    record["publication"] = {"attempts": int(record.get("publication", {}).get("attempts", 0)) + 1, "published_at": now_iso(), "external_response_id": external_id}
    payload["updated_at"] = now_iso()
    args.approvals.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"published {args.approval_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
