#!/usr/bin/env python3
"""Synchronize App Store and Google Play reviews into the local dashboard CSV."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
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


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def der_signature_to_raw(signature: bytes, component_size: int = 32) -> bytes:
    """Convert an ASN.1 DER ECDSA signature into the JWT r||s representation."""

    def read_length(offset: int) -> tuple[int, int]:
        if offset >= len(signature):
            raise ValueError("truncated DER signature")
        first = signature[offset]
        offset += 1
        if first < 0x80:
            return first, offset
        count = first & 0x7F
        if count == 0 or count > 2 or offset + count > len(signature):
            raise ValueError("invalid DER signature length")
        return int.from_bytes(signature[offset : offset + count], "big"), offset + count

    if not signature or signature[0] != 0x30:
        raise ValueError("ECDSA signature is not a DER sequence")
    sequence_length, offset = read_length(1)
    if offset + sequence_length != len(signature):
        raise ValueError("invalid DER sequence length")
    components: list[bytes] = []
    for _ in range(2):
        if offset >= len(signature) or signature[offset] != 0x02:
            raise ValueError("ECDSA signature component is not an integer")
        length, offset = read_length(offset + 1)
        value = signature[offset : offset + length]
        offset += length
        value = value.lstrip(b"\x00")
        if not value or len(value) > component_size:
            raise ValueError("invalid ECDSA signature component size")
        components.append(value.rjust(component_size, b"\x00"))
    if offset != len(signature):
        raise ValueError("unexpected trailing DER signature bytes")
    return b"".join(components)


def sign_es256(signing_input: bytes, private_key: str) -> bytes:
    normalized_key = private_key.strip().replace("\\n", "\n") + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as key_file:
        os.chmod(key_file.name, 0o600)
        key_file.write(normalized_key)
        key_file.flush()
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_file.name],
            input=signing_input,
            capture_output=True,
            check=True,
        )
    return result.stdout


def app_store_connect_token(
    key_id: str,
    issuer_id: str,
    private_key: str,
    issued_at: int | None = None,
    signer=sign_es256,
) -> str:
    if not key_id.strip() or not issuer_id.strip() or not private_key.strip():
        raise ValueError("App Store Connect Key ID, Issuer ID, and private key are required")
    now = int(time.time()) if issued_at is None else issued_at
    header = {"alg": "ES256", "kid": key_id.strip(), "typ": "JWT"}
    payload = {
        "iss": issuer_id.strip(),
        "iat": now,
        "exp": now + 19 * 60,
        "aud": "appstoreconnect-v1",
    }
    encoded_header = base64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = der_signature_to_raw(signer(signing_input, private_key))
    return f"{signing_input.decode('ascii')}.{base64url(signature)}"


def google_service_account_assertion(
    service_account: dict[str, object],
    issued_at: int | None = None,
    signer=sign_es256,
) -> str:
    client_email = str(service_account.get("client_email", "")).strip()
    private_key = str(service_account.get("private_key", "")).strip()
    if not client_email or not private_key:
        raise ValueError("Google Play service account JSON requires client_email and private_key")
    now = int(time.time()) if issued_at is None else issued_at
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": client_email,
            "scope": (
                "https://www.googleapis.com/auth/androidpublisher "
                "https://www.googleapis.com/auth/devstorage.read_only"
            ),
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 60 * 60,
    }
    encoded_header = base64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = signer(signing_input, private_key)
    return f"{signing_input.decode('ascii')}.{base64url(signature)}"


def google_play_access_token(service_account_json: str) -> str:
    service_account = json.loads(service_account_json)
    if not isinstance(service_account, dict):
        raise ValueError("Google Play service account JSON must be an object")
    assertion = google_service_account_assertion(service_account)
    body = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ONNELLAB-Store-Review-Sync/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    access_token = str(payload.get("access_token", "") if isinstance(payload, dict) else "").strip()
    if not access_token:
        raise ValueError("Google OAuth response did not include an access token")
    return access_token


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


def fetch_bytes(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/csv,application/octet-stream",
            "User-Agent": "ONNELLAB-Store-Review-Sync/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_apple_review_pages(
    url: str,
    token: str,
    fetcher=fetch_json,
    max_pages: int = 100,
) -> dict[str, object]:
    combined: dict[str, object] = {"data": [], "included": []}
    next_url = url
    seen: set[str] = set()
    for _ in range(max_pages):
        if not next_url or next_url in seen:
            break
        seen.add(next_url)
        payload = fetcher(next_url, token)
        for field in ("data", "included"):
            values = payload.get(field, [])
            if isinstance(values, list):
                combined[field].extend(values)  # type: ignore[union-attr]
        links = payload.get("links", {})
        next_url = str(links.get("next", "") if isinstance(links, dict) else "").strip()
    return combined


def fetch_google_review_pages(
    url: str,
    token: str,
    fetcher=fetch_json,
    max_pages: int = 100,
) -> dict[str, object]:
    combined: dict[str, object] = {"reviews": []}
    next_url = url
    seen_tokens: set[str] = set()
    for _ in range(max_pages):
        payload = fetcher(next_url, token)
        reviews = payload.get("reviews", [])
        if isinstance(reviews, list):
            combined["reviews"].extend(reviews)  # type: ignore[union-attr]
        pagination = payload.get("tokenPagination", {})
        next_token = str(
            pagination.get("nextPageToken", "") if isinstance(pagination, dict) else ""
        ).strip()
        if not next_token or next_token in seen_tokens:
            break
        seen_tokens.add(next_token)
        parsed = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query["token"] = next_token
        next_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
        )
    return combined


def google_report_review_rows(
    bucket: str,
    store: dict[str, str],
    token: str,
    synced_at: str,
    json_fetcher=fetch_json,
    bytes_fetcher=fetch_bytes,
) -> list[dict[str, str]]:
    bucket = bucket.removeprefix("gs://").strip().strip("/")
    package = store.get("store_package", "")
    if not bucket or not package:
        return []
    prefix = f"reviews/reviews_{package}_"
    query = urllib.parse.urlencode({"prefix": prefix, "maxResults": "1000"})
    list_url = f"https://storage.googleapis.com/storage/v1/b/{urllib.parse.quote(bucket, safe='')}/o?{query}"
    object_names: list[str] = []
    while list_url:
        payload = json_fetcher(list_url, token)
        items = payload.get("items", [])
        if isinstance(items, list):
            object_names.extend(
                str(item.get("name", ""))
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).endswith(".csv")
            )
        page_token = str(payload.get("nextPageToken", "") or "").strip()
        if not page_token:
            break
        query = urllib.parse.urlencode({"prefix": prefix, "maxResults": "1000", "pageToken": page_token})
        list_url = f"https://storage.googleapis.com/storage/v1/b/{urllib.parse.quote(bucket, safe='')}/o?{query}"

    rows: list[dict[str, str]] = []
    for object_name in sorted(set(object_names)):
        download_url = (
            f"https://storage.googleapis.com/download/storage/v1/b/{urllib.parse.quote(bucket, safe='')}"
            f"/o/{urllib.parse.quote(object_name, safe='')}?alt=media"
        )
        raw = bytes_fetcher(download_url, token)
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        for source in csv.DictReader(io.StringIO(raw.decode(encoding))):
            review_text = str(source.get("Review Text", "") or "").strip()
            review_title = str(source.get("Review Title", "") or "").strip()
            if not review_text and not review_title:
                continue
            review_link = str(source.get("Review Link", "") or "")
            review_id = ""
            marker = "ReviewPlace:id="
            if marker in review_link:
                review_id = urllib.parse.unquote(review_link.split(marker, 1)[1].split("&", 1)[0])
            if not review_id:
                identity = "|".join(
                    [
                        package,
                        str(source.get("Review Submit Millis Since Epoch", "") or ""),
                        review_title,
                        review_text,
                    ]
                )
                review_id = "report-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            developer_reply = str(source.get("Developer Reply Text", "") or "").strip()
            rows.append(
                {
                    "review_id": review_id,
                    "app_id": store.get("app_id", ""),
                    "app_slug": store.get("app_slug", ""),
                    "app_name": store.get("app_name", ""),
                    "platform": "android",
                    "rating": str(source.get("Star Rating", "") or ""),
                    "title": review_title,
                    "body": review_text,
                    "reviewer_language": str(source.get("Reviewer Language", "") or ""),
                    "territory": "",
                    "app_version": str(source.get("App Version Name", "") or ""),
                    "created_at": str(source.get("Review Submit Date and Time", "") or ""),
                    "updated_at": str(source.get("Review Last Update Date and Time", "") or ""),
                    "developer_reply": developer_reply,
                    "reply_updated_at": str(source.get("Developer Reply Date and Time", "") or ""),
                    "status": "replied" if developer_reply else "pending",
                    "synced_at": synced_at,
                }
            )
    return rows


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
    google_reports_bucket: str = "",
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
                payload = fetch_apple_review_pages(
                    f"https://api.appstoreconnect.apple.com/v1/apps/{urllib.parse.quote(app_id)}/customerReviews?{query}",
                    apple_token,
                )
            if payload is None:
                counts["skipped"] += 1
                continue
            rows = apple_review_rows(payload, store, synced_at)
        elif platform == "android":
            package = store.get("store_package", "")
            rows = []
            if google_reports_bucket and google_token and package:
                rows.extend(
                    google_report_review_rows(
                        google_reports_bucket,
                        store,
                        google_token,
                        synced_at,
                    )
                )
            if payload is None and google_token and package:
                payload = fetch_google_review_pages(
                    "https://androidpublisher.googleapis.com/androidpublisher/v3/"
                    f"applications/{urllib.parse.quote(package)}/reviews?maxResults=200",
                    google_token,
                )
            if payload is None:
                if not rows:
                    counts["skipped"] += 1
                    continue
            else:
                rows.extend(google_review_rows(payload, store, synced_at))
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
    apple_token = os.environ.get("APP_STORE_CONNECT_TOKEN", "").strip()
    if not apple_token:
        key_id = os.environ.get("APP_STORE_CONNECT_KEY_ID", "").strip()
        issuer_id = os.environ.get("APP_STORE_CONNECT_ISSUER_ID", "").strip()
        private_key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "").strip()
        encoded_private_key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY_BASE64", "").strip()
        if not private_key and encoded_private_key:
            private_key = base64.b64decode(encoded_private_key, validate=True).decode("utf-8")
        if key_id or issuer_id or private_key:
            apple_token = app_store_connect_token(key_id, issuer_id, private_key)
    google_token = os.environ.get("GOOGLE_PLAY_ACCESS_TOKEN", "").strip()
    if not google_token:
        encoded_service_account = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
        if encoded_service_account:
            service_account_json = base64.b64decode(encoded_service_account, validate=True).decode("utf-8")
            google_token = google_play_access_token(service_account_json)
    counts = sync_reviews(
        stores_path=args.stores,
        output_path=args.output,
        apple_token=apple_token,
        google_token=google_token,
        google_reports_bucket=os.environ.get("GOOGLE_PLAY_REPORTS_BUCKET", "").strip(),
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
