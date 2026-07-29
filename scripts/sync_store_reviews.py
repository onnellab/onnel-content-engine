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
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORES = ROOT / "data" / "store_versions.csv"
DEFAULT_OUTPUT = ROOT / "data" / "store_reviews.csv"
DEFAULT_OVERRIDES = ROOT / "data" / "store_review_overrides.json"
FIELDS = [
    "review_id",
    "app_id",
    "app_slug",
    "app_name",
    "platform",
    "rating",
    "review_kind",
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
GOOGLE_REPORTS_BUCKET_PREFIX = "pubsite_prod_"
TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
HTTP_MAX_ATTEMPTS = 5
HTTP_MAX_RETRY_DELAY_SECONDS = 60.0


class StoreReviewSyncError(ValueError):
    """Raised when a review sync would produce an incomplete snapshot."""


def apply_review_overrides(
    rows: list[dict[str, str]],
    overrides_path: Path = DEFAULT_OVERRIDES,
) -> list[dict[str, str]]:
    overrides: dict[str, object] = {}
    if overrides_path.exists():
        payload = json.loads(overrides_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("reviews"), dict):
            overrides = payload["reviews"]
    for row in rows:
        has_text = bool(row.get("title", "").strip() or row.get("body", "").strip())
        row["review_kind"] = "review" if has_text else "rating_only"
        override = overrides.get(row.get("review_id", ""))
        if isinstance(override, dict) and override.get("review_kind") in {"review", "rating_only"}:
            row["review_kind"] = str(override["review_kind"])
        if row["review_kind"] == "rating_only" and not row.get("developer_reply", "").strip():
            row["status"] = "rating_only"
    return rows


def retry_delay_seconds(
    error: urllib.error.HTTPError,
    attempt: int,
    now: datetime | None = None,
) -> float:
    """Return a bounded Retry-After or exponential backoff delay."""
    retry_after = str(error.headers.get("Retry-After", "") if error.headers else "").strip()
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), HTTP_MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                current = now or datetime.now(timezone.utc)
                return min(
                    max((retry_at - current).total_seconds(), 0.0),
                    HTTP_MAX_RETRY_DELAY_SECONDS,
                )
            except (TypeError, ValueError, OverflowError):
                pass
    return min(2.0 ** (attempt - 1), HTTP_MAX_RETRY_DELAY_SECONDS)


def urlopen_with_retry(
    request: urllib.request.Request,
    timeout: int,
    *,
    opener=None,
    sleeper=None,
    max_attempts: int = HTTP_MAX_ATTEMPTS,
):
    """Open an HTTP request with bounded retries for transient failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    opener = opener or urllib.request.urlopen
    sleeper = sleeper or time.sleep
    host = urllib.parse.urlsplit(request.full_url).netloc
    for attempt in range(1, max_attempts + 1):
        try:
            return opener(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code not in TRANSIENT_HTTP_STATUSES or attempt == max_attempts:
                raise
            delay = retry_delay_seconds(error, attempt)
            print(
                f"Transient HTTP {error.code} from {host}; retrying "
                f"{attempt + 1}/{max_attempts} in {delay:g}s",
                file=sys.stderr,
            )
            sleeper(delay)
        except (urllib.error.URLError, TimeoutError):
            if attempt == max_attempts:
                raise
            delay = min(2.0 ** (attempt - 1), HTTP_MAX_RETRY_DELAY_SECONDS)
            print(
                f"Transient network error from {host}; retrying "
                f"{attempt + 1}/{max_attempts} in {delay:g}s",
                file=sys.stderr,
            )
            sleeper(delay)
    raise AssertionError("unreachable")


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
    with urlopen_with_retry(request, timeout=30) as response:
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


def normalized_review_timestamp(value: str) -> str:
    """Normalize equivalent ISO-8601 timestamps for cross-source matching."""
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return value.strip()
    if parsed.tzinfo is None:
        return value.strip()
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def review_fingerprint(row: dict[str, str]) -> tuple[str, ...]:
    """Return a stable identity for a review when Google exposes different IDs.

    The Play lifetime report and the recent-reviews API do not always share an
    identifier.  The submitted content, rating, and original submission time
    are immutable review attributes and therefore safely identify that overlap.
    """
    normalize_text = lambda value: " ".join(value.split()).casefold()
    return (
        row.get("app_id", ""),
        row.get("platform", ""),
        normalize_text(row.get("rating", "")),
        normalize_text(row.get("title", "")),
        normalize_text(row.get("body", "")),
        normalized_review_timestamp(row.get("created_at", "")),
    )


def merge_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge source aliases while preferring the canonical Play API ID."""
    by_fingerprint: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        by_fingerprint.setdefault(review_fingerprint(row), []).append(row)

    merged: list[dict[str, str]] = []
    for matches in by_fingerprint.values():
        # Lifetime-report fallback IDs are useful only when Play did not supply
        # its canonical review ID. Prefer the latter for future incremental syncs.
        ranked = sorted(
            matches,
            key=lambda row: (
                row.get("review_id", "").startswith("report-"),
                not bool(row.get("developer_reply", "")),
                row.get("updated_at", ""),
            ),
        )
        combined = dict(ranked[0])
        for row in ranked[1:]:
            for field in FIELDS:
                if not combined.get(field, "") and row.get(field, ""):
                    combined[field] = row[field]
        combined["status"] = (
            "replied"
            if combined.get("developer_reply") or any(row.get("status") == "replied" for row in matches)
            else "pending"
        )
        merged.append(combined)
    return merged


def fetch_json(url: str, token: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "ONNELLAB-Store-Review-Sync/1.0",
        },
    )
    with urlopen_with_retry(request, timeout=30) as response:
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
    with urlopen_with_retry(request, timeout=60) as response:
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
        if not next_url:
            break
        if next_url in seen:
            raise StoreReviewSyncError(f"Apple review pagination repeated a page URL: {next_url}")
        seen.add(next_url)
        payload = fetcher(next_url, token)
        for field in ("data", "included"):
            values = payload.get(field, [])
            if isinstance(values, list):
                combined[field].extend(values)  # type: ignore[union-attr]
        links = payload.get("links", {})
        next_url = str(links.get("next", "") if isinstance(links, dict) else "").strip()
    if next_url:
        raise StoreReviewSyncError(
            f"Apple review pagination exceeded the safety limit of {max_pages} pages"
        )
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
        if not next_token:
            break
        if next_token in seen_tokens:
            raise StoreReviewSyncError(
                f"Google Play review pagination repeated a page token: {next_token}"
            )
        seen_tokens.add(next_token)
        parsed = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query["token"] = next_token
        next_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
        )
    else:
        raise StoreReviewSyncError(
            f"Google Play review pagination exceeded the safety limit of {max_pages} pages"
        )
    return combined


def normalize_google_reports_bucket(value: str) -> str:
    normalized = value.strip().removeprefix("gs://").strip("/")
    bucket = normalized.split("/", 1)[0]
    if not bucket:
        return ""
    if not bucket.startswith(GOOGLE_REPORTS_BUCKET_PREFIX):
        raise StoreReviewSyncError(
            "GOOGLE_PLAY_REPORTS_BUCKET must be the Play Console review report bucket "
            f"starting with {GOOGLE_REPORTS_BUCKET_PREFIX}"
        )
    return bucket


def apple_store_app_id(store: dict[str, str]) -> str:
    configured = store.get("store_app_id", "").strip()
    if configured:
        return configured
    if store.get("status", "").strip().lower() == "failed":
        return ""
    path = urllib.parse.urlsplit(store.get("store_url", "")).path
    for segment in reversed(path.split("/")):
        candidate = segment.removeprefix("id")
        if candidate.isdigit():
            return candidate
    return ""


def google_store_package(store: dict[str, str]) -> str:
    configured = store.get("store_package", "").strip()
    if configured:
        return configured
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(store.get("store_url", "")).query)
    return str(query.get("id", [""])[0]).strip()


def google_report_access_error(bucket: str, principal: str = "") -> StoreReviewSyncError:
    identity = principal or "the configured Google Play service account"
    return StoreReviewSyncError(
        f"Google Play report bucket {bucket} denied access to {identity}. "
        "In Play Console > Users and permissions, grant this service account "
        "the account-level 'View app information and download bulk reports "
        "(read-only)' permission (CAN_VIEW_NON_FINANCIAL_DATA_GLOBAL). "
        "Google notes that permission changes may take up to 48 hours to propagate."
    )


def apple_review_ids(payload: dict[str, object]) -> set[str]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        return set()
    return {
        str(item.get("id", "")).strip()
        for item in data
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }


def relationship_resource_id(resource: dict[str, object], relationship_name: str) -> str:
    relationships = resource.get("relationships", {})
    if not isinstance(relationships, dict):
        return ""
    relationship = relationships.get(relationship_name, {})
    if not isinstance(relationship, dict):
        return ""
    data = relationship.get("data", {})
    if not isinstance(data, dict):
        return ""
    return str(data.get("id", "") or "").strip()


def google_report_review_rows(
    bucket: str,
    store: dict[str, str],
    token: str,
    synced_at: str,
    json_fetcher=fetch_json,
    bytes_fetcher=fetch_bytes,
    max_pages: int = 100,
    principal: str = "",
) -> list[dict[str, str]]:
    bucket = normalize_google_reports_bucket(bucket)
    package = google_store_package(store)
    if not bucket or not package:
        return []
    prefix = f"reviews/reviews_{package}_"
    query = urllib.parse.urlencode({"prefix": prefix, "maxResults": "1000"})
    list_url = f"https://storage.googleapis.com/storage/v1/b/{urllib.parse.quote(bucket, safe='')}/o?{query}"
    object_names: list[str] = []
    seen_page_tokens: set[str] = set()
    for _ in range(max_pages):
        try:
            payload = json_fetcher(list_url, token)
        except urllib.error.HTTPError as error:
            if error.code == 403:
                raise google_report_access_error(bucket, principal) from error
            raise
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
        if page_token in seen_page_tokens:
            raise StoreReviewSyncError(
                f"Google Play report pagination repeated a page token: {page_token}"
            )
        seen_page_tokens.add(page_token)
        query = urllib.parse.urlencode({"prefix": prefix, "maxResults": "1000", "pageToken": page_token})
        list_url = f"https://storage.googleapis.com/storage/v1/b/{urllib.parse.quote(bucket, safe='')}/o?{query}"
    else:
        raise StoreReviewSyncError(
            f"Google Play report pagination exceeded the safety limit of {max_pages} pages"
        )

    rows: list[dict[str, str]] = []
    for object_name in sorted(set(object_names)):
        download_url = (
            f"https://storage.googleapis.com/download/storage/v1/b/{urllib.parse.quote(bucket, safe='')}"
            f"/o/{urllib.parse.quote(object_name, safe='')}?alt=media"
        )
        try:
            raw = bytes_fetcher(download_url, token)
        except urllib.error.HTTPError as error:
            if error.code == 403:
                raise google_report_access_error(bucket, principal) from error
            raise
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


def apple_review_rows(
    payload: dict[str, object],
    store: dict[str, str],
    synced_at: str,
    published_response_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    response_by_id: dict[str, dict[str, object]] = {}
    response_by_review: dict[str, dict[str, object]] = {}
    included = payload.get("included", [])
    if isinstance(included, list):
        for item in included:
            if not isinstance(item, dict) or item.get("type") != "customerReviewResponses":
                continue
            response_id = str(item.get("id", "") or "").strip()
            if response_id:
                response_by_id[response_id] = item
            review_id = relationship_resource_id(item, "review")
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
        response_id = relationship_resource_id(item, "response")
        response = response_by_id.get(response_id) or response_by_review.get(review_id, {})
        response_attributes = response.get("attributes", {}) if isinstance(response, dict) else {}
        if not isinstance(response_attributes, dict):
            response_attributes = {}
        developer_reply = str(response_attributes.get("responseBody", "") or "").strip()
        has_published_response = (
            published_response_ids is not None and review_id in published_response_ids
        )
        has_response = bool(response_id or response or developer_reply or has_published_response)
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
                "status": "replied" if has_response else "pending",
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
    require_google_history: bool = False,
    google_principal: str = "",
    overrides_path: Path = DEFAULT_OVERRIDES,
) -> dict[str, int]:
    google_reports_bucket = normalize_google_reports_bucket(google_reports_bucket)
    if require_google_history and not google_reports_bucket:
        raise StoreReviewSyncError(
            "GOOGLE_PLAY_REPORTS_BUCKET is required for a complete Google Play review history; "
            "the reviews API only exposes reviews created or modified within the last week"
        )
    stores = read_csv_rows(stores_path)
    existing = {
        (row.get("app_id", ""), row.get("platform", ""), row.get("review_id", "")): row
        for row in read_csv_rows(output_path)
        if row.get("review_id")
    }
    synced_at = now_iso()
    fetched: list[dict[str, str]] = []
    counts = {
        "ios": 0,
        "android": 0,
        "apple_published": 0,
        "google_reports": 0,
        "google_recent": 0,
        "unavailable": 0,
        "skipped": 0,
    }
    for store in stores:
        platform = store.get("platform", "")
        slug = store.get("app_slug", "")
        payload = fixture_payload(apple_json_dir if platform == "ios" else google_json_dir, slug)
        if platform == "ios":
            app_id = apple_store_app_id(store)
            published_response_ids: set[str] | None = None
            if (
                payload is None
                and not app_id
                and store.get("status", "").strip().lower() == "failed"
            ):
                counts["unavailable"] += 1
                continue
            if payload is None and apple_token and app_id:
                parameters = {
                    "limit": "200",
                    "sort": "-createdDate",
                    "include": "response",
                    "fields[customerReviews]": "rating,title,body,createdDate,reviewTerritory,response",
                    "fields[customerReviewResponses]": "responseBody,lastModifiedDate,state,review",
                }
                query = urllib.parse.urlencode(parameters)
                reviews_url = (
                    "https://api.appstoreconnect.apple.com/v1/apps/"
                    f"{urllib.parse.quote(app_id)}/customerReviews"
                )
                payload = fetch_apple_review_pages(
                    f"{reviews_url}?{query}",
                    apple_token,
                )
                published_query = urllib.parse.urlencode(
                    {
                        "limit": "200",
                        "sort": "-createdDate",
                        "exists[publishedResponse]": "true",
                    }
                )
                published_payload = fetch_apple_review_pages(
                    f"{reviews_url}?{published_query}",
                    apple_token,
                )
                published_response_ids = apple_review_ids(published_payload)
                counts["apple_published"] += len(published_response_ids)
            if payload is None:
                counts["skipped"] += 1
                continue
            rows = apple_review_rows(
                payload,
                store,
                synced_at,
                published_response_ids=published_response_ids,
            )
        elif platform == "android":
            package = google_store_package(store)
            rows = []
            if require_google_history and payload is None and package and not google_token:
                raise StoreReviewSyncError(
                    "Google Play credentials are required to read the lifetime review reports"
                )
            if google_reports_bucket and google_token and package:
                report_rows = google_report_review_rows(
                    google_reports_bucket,
                    store,
                    google_token,
                    synced_at,
                    principal=google_principal,
                )
                rows.extend(report_rows)
                counts["google_reports"] += len(report_rows)
            if payload is None and google_token and package:
                payload = fetch_google_review_pages(
                    "https://androidpublisher.googleapis.com/androidpublisher/v3/"
                    f"applications/{urllib.parse.quote(package)}/reviews?maxResults=100",
                    google_token,
                )
            if payload is None:
                if not rows:
                    counts["skipped"] += 1
                    continue
            else:
                recent_rows = google_review_rows(payload, store, synced_at)
                rows.extend(recent_rows)
                counts["google_recent"] += len(recent_rows)
        else:
            continue
        unique_rows: dict[tuple[str, str, str], dict[str, str]] = {}
        for row in rows:
            key = (
                row.get("app_id", ""),
                row.get("platform", ""),
                row.get("review_id", ""),
            )
            unique_rows[key] = row
        rows = merge_review_rows(list(unique_rows.values()))
        fetched.extend(rows)
        counts[platform] += len(rows)

    for row in fetched:
        existing[(row["app_id"], row["platform"], row["review_id"])] = row
    rows = sorted(
        merge_review_rows(list(existing.values())),
        key=lambda row: (row.get("updated_at", ""), row.get("created_at", "")),
        reverse=True,
    )
    write_csv_rows(output_path, apply_review_overrides(rows, overrides_path))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize App Store and Google Play reviews")
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--apple-json-dir", type=Path)
    parser.add_argument("--google-json-dir", type=Path)
    parser.add_argument(
        "--allow-recent-only",
        action="store_true",
        help="Allow Google Play sync without the lifetime report bucket",
    )
    args = parser.parse_args()
    google_reports_bucket = os.environ.get("GOOGLE_PLAY_REPORTS_BUCKET", "").strip()
    try:
        google_reports_bucket = normalize_google_reports_bucket(google_reports_bucket)
        if not args.allow_recent_only and not google_reports_bucket:
            raise StoreReviewSyncError(
                "GOOGLE_PLAY_REPORTS_BUCKET is required for a complete Google Play review history; "
                "use --allow-recent-only only for an intentional partial sync"
            )
    except StoreReviewSyncError as error:
        print(f"store review sync failed: {error}", file=sys.stderr)
        return 1
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
    google_principal = ""
    if not google_token:
        encoded_service_account = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
        if encoded_service_account:
            service_account_json = base64.b64decode(encoded_service_account, validate=True).decode("utf-8")
            service_account = json.loads(service_account_json)
            if isinstance(service_account, dict):
                google_principal = str(service_account.get("client_email", "") or "").strip()
            google_token = google_play_access_token(service_account_json)
    try:
        counts = sync_reviews(
            stores_path=args.stores,
            output_path=args.output,
            apple_token=apple_token,
            google_token=google_token,
            google_reports_bucket=google_reports_bucket,
            apple_json_dir=args.apple_json_dir,
            google_json_dir=args.google_json_dir,
            require_google_history=not args.allow_recent_only,
            google_principal=google_principal,
        )
    except StoreReviewSyncError as error:
        print(f"store review sync failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(counts, ensure_ascii=False))
    if counts["skipped"]:
        print(
            "Some stores were skipped. Provide APP_STORE_CONNECT_TOKEN and "
            "GOOGLE_PLAY_ACCESS_TOKEN, or fixture directories."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
