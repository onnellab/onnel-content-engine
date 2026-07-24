#!/usr/bin/env python3
"""Synchronize App Store and Google Play reviews into the local dashboard CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORES = ROOT / "data" / "store_versions.csv"
DEFAULT_OUTPUT = ROOT / "data" / "store_reviews.csv"
FIELDS = [
    "review_id",
    "app_id",
    "app_slug",
    "app_name",
    "platform",
    "rating",
    "title",
    "body",
    "reviewer_language",
    "territory",
    "app_version",
    "created_at",
    "updated_at",
    "developer_reply",
    "reply_updated_at",
    "status",
    "synced_at",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def timestamp_iso(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    try:
        seconds = int(str(value.get("seconds", "0")))
    except ValueError:
        return ""
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=0).isoformat() if seconds else ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in FIELDS} for row in rows)


def fetch_json(url: str, token: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "ONNELLAB-Store-Review-Sync/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("store review response is not a JSON object")
    return payload


def apple_review_rows(payload: dict[str, object], store: dict[str, str], synced_at: str) -> list[dict[str, str]]:
    response_by_review: dict[str, dict[str, object]] = {}
    included = payload.get("included", [])
    if isinstance(included, list):
        for item in included:
            if not isinstance(item, dict) or item.get("type") != "customerReviewResponses":
                continue
            relationships = item.get("relationships", {})
            review_id = ""
            if isinstance(relationships, dict):
                review = relationships.get("review", {})
                if isinstance(review, dict):
                    data = review.get("data", {})
                    if isinstance(data, dict):
                        review_id = str(data.get("id", ""))
            if review_id:
                response_by_review[review_id] = item

    rows: list[dict[str, str]] = []
    data = payload.get("data", [])
    if not isinstance(data, list):
        return rows
    for item in data:
        if not isinstance(item, dict):
            continue
        review_id = str(item.get("id", ""))
        attributes = item.get("attributes", {})
        if not review_id or not isinstance(attributes, dict):
            continue
        response = response_by_review.get(review_id, {})
        response_attributes = response.get("attributes", {}) if isinstance(response, dict) else {}
        if not isinstance(response_attributes, dict):
            response_attributes = {}
        developer_reply = str(response_attributes.get("responseBody", "") or "")
        rows.append(
            {
                "review_id": review_id,
                "app_id": store.get("app_id", ""),
                "app_slug": store.get("app_slug", ""),
                "app_name": store.get("app_name", ""),
                "platform": "ios",
                "rating": str(attributes.get("rating", "") or ""),
                "title": str(attributes.get("title", "") or ""),
                "body": str(attributes.get("body", "") or ""),
                "reviewer_language": "",
                "territory": str(
                    attributes.get("reviewTerritory", "")
                    or attributes.get("territory", "")
                    or ""
                ),
                "app_version": "",
                "created_at": str(attributes.get("createdDate", "") or ""),
                "updated_at": str(attributes.get("createdDate", "") or ""),
                "developer_reply": developer_reply,
                "reply_updated_at": str(response_attributes.get("lastModifiedDate", "") or ""),
                "status": "replied" if developer_reply else "pending",
                "synced_at": synced_at,
            }
        )
    return rows


def google_review_rows(payload: dict[str, object], store: dict[str, str], synced_at: str) -> list[dict[str, str]]:
    reviews = payload.get("reviews", [])
    if not isinstance(reviews, list):
        return []
    rows: list[dict[str, str]] = []
    for item in reviews:
        if not isinstance(item, dict):
            continue
        review_id = str(item.get("reviewId", ""))
        if not review_id:
            continue
        user_comment: dict[str, object] = {}
        developer_comment: dict[str, object] = {}
        comments = item.get("comments", [])
        if isinstance(comments, list):
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                if isinstance(comment.get("userComment"), dict):
                    user_comment = comment["userComment"]
                if isinstance(comment.get("developerComment"), dict):
                    developer_comment = comment["developerComment"]
        text = str(user_comment.get("text", "") or "")
        title, separator, body = text.partition("\t")
        if not separator:
            title, body = "", title
        developer_reply = str(developer_comment.get("text", "") or "")
        updated_at = timestamp_iso(user_comment.get("lastModified"))
        rows.append(
            {
                "review_id": review_id,
                "app_id": store.get("app_id", ""),
                "app_slug": store.get("app_slug", ""),
                "app_name": store.get("app_name", ""),
                "platform": "android",
                "rating": str(user_comment.get("starRating", "") or ""),
                "title": title,
                "body": body,
                "reviewer_language": str(user_comment.get("reviewerLanguage", "") or ""),
                "territory": "",
                "app_version": str(user_comment.get("appVersionName", "") or ""),
                "created_at": updated_at,
                "updated_at": updated_at,
                "developer_reply": developer_reply,
                "reply_updated_at": timestamp_iso(developer_comment.get("lastModified")),
                "status": "replied" if developer_reply else "pending",
                "synced_at": synced_at,
            }
        )
    return rows


def fixture_payload(directory: Path | None, slug: str) -> dict[str, object] | None:
    if not directory:
        return None
    path = directory / f"{slug}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"fixture is not a JSON object: {path}")
    return payload


def sync_reviews(
    stores_path: Path = DEFAULT_STORES,
    output_path: Path = DEFAULT_OUTPUT,
    apple_token: str = "",
    google_token: str = "",
    apple_json_dir: Path | None = None,
    google_json_dir: Path | None = None,
) -> dict[str, int]:
    stores = read_csv_rows(stores_path)
    existing = {
        (row.get("platform", ""), row.get("review_id", "")): row
        for row in read_csv_rows(output_path)
        if row.get("review_id")
    }
    synced_at = now_iso()
    fetched: list[dict[str, str]] = []
    counts = {"ios": 0, "android": 0, "skipped": 0}
    for store in stores:
        platform = store.get("platform", "")
        slug = store.get("app_slug", "")
        payload = fixture_payload(apple_json_dir if platform == "ios" else google_json_dir, slug)
        if platform == "ios":
            app_id = store.get("store_app_id", "")
            if payload is None and apple_token and app_id:
                query = urllib.parse.urlencode(
                    {
                        "limit": "200",
                        "sort": "-createdDate",
                        "include": "response",
                        "fields[customerReviews]": "rating,title,body,createdDate,reviewTerritory,response",
                        "fields[customerReviewResponses]": "responseBody,lastModifiedDate,state,review",
                    }
                )
                payload = fetch_json(
                    f"https://api.appstoreconnect.apple.com/v1/apps/{urllib.parse.quote(app_id)}/customerReviews?{query}",
                    apple_token,
                )
            if payload is None:
                counts["skipped"] += 1
                continue
            rows = apple_review_rows(payload, store, synced_at)
        elif platform == "android":
            package = store.get("store_package", "")
            if payload is None and google_token and package:
                payload = fetch_json(
                    "https://androidpublisher.googleapis.com/androidpublisher/v3/"
                    f"applications/{urllib.parse.quote(package)}/reviews?maxResults=200",
                    google_token,
                )
            if payload is None:
                counts["skipped"] += 1
                continue
            rows = google_review_rows(payload, store, synced_at)
        else:
            continue
        fetched.extend(rows)
        counts[platform] += len(rows)

    for row in fetched:
        existing[(row["platform"], row["review_id"])] = row
    rows = sorted(
        existing.values(),
        key=lambda row: (row.get("updated_at", ""), row.get("created_at", "")),
        reverse=True,
    )
    write_csv_rows(output_path, rows)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize App Store and Google Play reviews")
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--apple-json-dir", type=Path)
    parser.add_argument("--google-json-dir", type=Path)
    args = parser.parse_args()
    counts = sync_reviews(
        stores_path=args.stores,
        output_path=args.output,
        apple_token=os.environ.get("APP_STORE_CONNECT_TOKEN", ""),
        google_token=os.environ.get("GOOGLE_PLAY_ACCESS_TOKEN", ""),
        apple_json_dir=args.apple_json_dir,
        google_json_dir=args.google_json_dir,
    )
    print(json.dumps(counts, ensure_ascii=False))
    if counts["skipped"]:
        print(
            "Some stores were skipped. Provide APP_STORE_CONNECT_TOKEN and "
            "GOOGLE_PLAY_ACCESS_TOKEN, or fixture directories."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
