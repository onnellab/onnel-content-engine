#!/usr/bin/env python3
"""Synchronize App Store Connect and Google Play acquisition funnel metrics."""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sync_store_reviews import (
    app_store_connect_token,
    fetch_bytes,
    fetch_json,
    google_play_access_token,
    normalize_google_reports_bucket,
    read_csv_rows,
    urlopen_with_retry,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPS = ROOT / "data" / "apps_registry.csv"
DEFAULT_STORES = ROOT / "data" / "store_versions.csv"
DEFAULT_DAILY = ROOT / "data" / "store_funnel_daily.csv"
DEFAULT_SUMMARY = ROOT / "data" / "store_funnel.json"
DEFAULT_STATUS = ROOT / "data" / "store_funnel_sync_status.json"
DEFAULT_STATE = ROOT / "data" / "store_funnel_state.json"

DAILY_FIELDS = [
    "date", "app_id", "app_slug", "app_name", "platform", "metric",
    "value", "source", "checked_at",
]
WINDOWS = (7, 30, 90)
APPLE_REPORTS = {
    "discovery": "App Store Discovery and Engagement Standard",
    "downloads": "App Store Downloads Standard",
    "purchases": "App Store Purchases Standard",
}


class FunnelSyncError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_int(value: object) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError as error:
        raise FunnelSyncError(f"invalid integer metric: {value!r}") from error


def read_daily(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_daily(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DAILY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in DAILY_FIELDS})


def read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "apple_processed_instances": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FunnelSyncError("store funnel state must be a JSON object")
    payload.setdefault("schema_version", 1)
    payload.setdefault("apple_processed_instances", [])
    return payload


def json_request(
    url: str,
    token: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
) -> dict[str, object]:
    raw_body = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ONNELLAB-Store-Funnel-Sync/1.0",
    }
    if raw_body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=raw_body, headers=headers, method=method)
    with urlopen_with_retry(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise FunnelSyncError(f"JSON response is not an object: {url}")
    return payload


def public_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ONNELLAB-Store-Funnel-Sync/1.0"})
    with urlopen_with_retry(request, timeout=90) as response:
        return response.read()


def decode_table(raw: bytes, delimiter: str = "\t") -> list[dict[str, str]]:
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    text = raw.decode(encoding)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [{str(key): str(value or "").strip() for key, value in row.items() if key is not None} for row in reader]


def app_identity(apps: list[dict[str, str]], slug: str) -> dict[str, str]:
    return next((app for app in apps if app.get("slug") == slug), {})


def metric_row(
    app: dict[str, str],
    platform: str,
    metric_date: str,
    metric: str,
    value: int,
    source: str,
    checked_at: str,
) -> dict[str, object]:
    return {
        "date": metric_date,
        "app_id": app.get("app_id", ""),
        "app_slug": app.get("slug", ""),
        "app_name": app.get("app_name", ""),
        "platform": platform,
        "metric": metric,
        "value": value,
        "source": source,
        "checked_at": checked_at,
    }


def aggregate_apple_rows(
    report_kind: str,
    rows: list[dict[str, str]],
    app: dict[str, str],
    checked_at: str,
) -> list[dict[str, object]]:
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        metric_date = row.get("Date", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", metric_date):
            continue
        if report_kind == "discovery":
            event = row.get("Event", "").casefold()
            page = row.get("Page Type", "").casefold()
            count = safe_int(row.get("Counts", row.get("Count", "0")))
            if event == "impression":
                totals[(metric_date, "impressions")] += count
            elif event == "page view" and page == "product page":
                totals[(metric_date, "store_visitors")] += count
        elif report_kind == "downloads":
            download_type = row.get("Download Type", "").casefold()
            if download_type == "first-time download":
                totals[(metric_date, "installs")] += safe_int(row.get("Counts", "0"))
        elif report_kind == "purchases":
            totals[(metric_date, "purchases")] += safe_int(row.get("Purchases", "0"))
    return [
        metric_row(app, "ios", metric_date, metric, value, f"apple_{report_kind}", checked_at)
        for (metric_date, metric), value in totals.items()
    ]


def apple_request_body(app_id: str) -> dict[str, object]:
    return {
        "data": {
            "type": "analyticsReportRequests",
            "attributes": {"accessType": "ONGOING"},
            "relationships": {"app": {"data": {"type": "apps", "id": app_id}}},
        }
    }


def apple_ongoing_request(app_id: str, token: str) -> tuple[str, str]:
    url = (
        f"https://api.appstoreconnect.apple.com/v1/apps/{urllib.parse.quote(app_id)}/analyticsReportRequests"
        "?filter%5BaccessType%5D=ONGOING&limit=200"
    )
    payload = json_request(url, token)
    requests = payload.get("data", [])
    if isinstance(requests, list):
        active = [
            item for item in requests
            if isinstance(item, dict)
            and not bool((item.get("attributes") or {}).get("stoppedDueToInactivity"))
        ]
        if active:
            return str(active[0].get("id", "")), "active"
    try:
        created = json_request(
            "https://api.appstoreconnect.apple.com/v1/analyticsReportRequests",
            token,
            method="POST",
            body=apple_request_body(app_id),
        )
    except urllib.error.HTTPError as error:
        if error.code in {403, 409}:
            return "", f"setup_http_{error.code}"
        raise
    data = created.get("data", {})
    request_id = str(data.get("id", "") if isinstance(data, dict) else "")
    return request_id, "created" if request_id else "setup_required"


def apple_reports(request_id: str, token: str) -> dict[str, str]:
    url = (
        f"https://api.appstoreconnect.apple.com/v1/analyticsReportRequests/"
        f"{urllib.parse.quote(request_id)}/reports?limit=200"
    )
    payload = json_request(url, token)
    reports = payload.get("data", [])
    result: dict[str, str] = {}
    if not isinstance(reports, list):
        return result
    for item in reports:
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            continue
        name = str(attributes.get("name", ""))
        report_id = str(item.get("id", ""))
        for kind, expected in APPLE_REPORTS.items():
            if name == expected or (
                expected.removesuffix(" Standard").casefold() in name.casefold()
                and "detailed" not in name.casefold()
            ):
                result[kind] = report_id
    return result


def apple_daily_instances(report_id: str, token: str) -> list[dict[str, object]]:
    url = (
        f"https://api.appstoreconnect.apple.com/v1/analyticsReports/"
        f"{urllib.parse.quote(report_id)}/instances?"
        "filter%5Bgranularity%5D=DAILY&limit=200"
    )
    payload = json_request(url, token)
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    valid = [item for item in data if isinstance(item, dict) and item.get("id")]
    return sorted(
        valid,
        key=lambda item: str((item.get("attributes") or {}).get("processingDate", "")),
    )


def apple_instance_rows(instance_id: str, token: str) -> list[dict[str, str]]:
    url = (
        f"https://api.appstoreconnect.apple.com/v1/analyticsReportInstances/"
        f"{urllib.parse.quote(instance_id)}/segments?limit=200"
    )
    payload = json_request(url, token)
    segments = payload.get("data", [])
    if not isinstance(segments, list):
        return []
    rows: list[dict[str, str]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        attributes = segment.get("attributes", {})
        if not isinstance(attributes, dict):
            continue
        download_url = str(attributes.get("url", "") or "")
        if not download_url:
            continue
        raw = public_bytes(download_url)
        checksum = str(attributes.get("checksum", "") or "").lower()
        if checksum and hashlib.md5(raw).hexdigest().lower() != checksum:
            raise FunnelSyncError(f"Apple segment checksum mismatch: {segment.get('id', '')}")
        rows.extend(decode_table(raw, delimiter="\t"))
    return rows


def sync_apple(
    apps: list[dict[str, str]],
    stores: list[dict[str, str]],
    token: str,
    state: dict[str, object],
    checked_at: str,
    *,
    initial_backfill_instances: int = 45,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    processed = {
        str(value) for value in state.get("apple_processed_instances", [])
        if str(value)
    }
    additions: list[dict[str, object]] = []
    app_status: dict[str, object] = {}
    processed_now: set[str] = set()

    for store in stores:
        if store.get("platform") != "ios" or not store.get("store_app_id"):
            continue
        slug = store.get("app_slug", "")
        app = app_identity(apps, slug)
        if not app:
            continue
        app_id = store["store_app_id"]
        try:
            request_id, request_status = apple_ongoing_request(app_id, token)
        except (urllib.error.HTTPError, FunnelSyncError, ValueError) as error:
            app_status[slug] = {"status": "error", "message": str(error)}
            continue
        if not request_id:
            app_status[slug] = {
                "status": request_status,
                "message": "Apple ongoing analytics report request is not ready.",
            }
            continue

        try:
            reports = apple_reports(request_id, token)
        except (urllib.error.HTTPError, FunnelSyncError) as error:
            app_status[slug] = {"status": "error", "message": str(error)}
            continue
        if not reports:
            app_status[slug] = {
                "status": "waiting_for_first_report",
                "request_id": request_id,
                "message": "Apple reports can take 24-48 hours after the initial request.",
            }
            continue

        collected_kinds: list[str] = []
        errors: list[str] = []
        for kind, report_id in reports.items():
            try:
                instances = apple_daily_instances(report_id, token)
                if not instances:
                    continue
                unseen = [item for item in instances if str(item.get("id")) not in processed]
                if not processed and len(unseen) > initial_backfill_instances:
                    unseen = unseen[-initial_backfill_instances:]
                for instance in unseen:
                    instance_id = str(instance.get("id"))
                    source_rows = apple_instance_rows(instance_id, token)
                    additions.extend(aggregate_apple_rows(kind, source_rows, app, checked_at))
                    processed_now.add(instance_id)
                collected_kinds.append(kind)
            except (urllib.error.HTTPError, FunnelSyncError, ValueError) as error:
                errors.append(f"{kind}: {error}")
        app_status[slug] = {
            "status": "partial" if errors else "ok",
            "request_id": request_id,
            "reports": sorted(collected_kinds),
            "errors": errors,
        }

    state["apple_processed_instances"] = sorted(processed | processed_now)[-10000:]
    return additions, app_status


def gcs_list_objects(bucket: str, prefix: str, token: str) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    page_token = ""
    seen: set[str] = set()
    while True:
        params = {"prefix": prefix, "maxResults": "1000"}
        if page_token:
            params["pageToken"] = page_token
        query = urllib.parse.urlencode(params)
        url = (
            f"https://storage.googleapis.com/storage/v1/b/"
            f"{urllib.parse.quote(bucket, safe='')}/o?{query}"
        )
        payload = fetch_json(url, token)
        items = payload.get("items", [])
        if isinstance(items, list):
            objects.extend(item for item in items if isinstance(item, dict))
        next_token = str(payload.get("nextPageToken", "") or "")
        if not next_token:
            break
        if next_token in seen:
            raise FunnelSyncError("Google Cloud Storage pagination repeated a page token")
        seen.add(next_token)
        page_token = next_token
    return objects


def gcs_download(bucket: str, object_name: str, token: str) -> bytes:
    url = (
        f"https://storage.googleapis.com/download/storage/v1/b/"
        f"{urllib.parse.quote(bucket, safe='')}/o/"
        f"{urllib.parse.quote(object_name, safe='')}?alt=media"
    )
    return fetch_bytes(url, token)


def recent_months(month_count: int = 4, today: date | None = None) -> set[str]:
    current = (today or datetime.now(timezone.utc).date()).replace(day=1)
    result: set[str] = set()
    for _ in range(month_count):
        result.add(current.strftime("%Y%m"))
        current = (current - timedelta(days=1)).replace(day=1)
    return result


def parse_google_store_performance(
    raw: bytes,
    app: dict[str, str],
    package: str,
    checked_at: str,
) -> list[dict[str, object]]:
    rows = decode_table(raw, delimiter=",")
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        row_package = row.get("Package name", row.get("Package Name", ""))
        if row_package and row_package != package:
            raise FunnelSyncError(f"Google store performance package mismatch: {row_package}")
        metric_date = row.get("Date", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", metric_date):
            continue
        visitors = safe_int(row.get("Store listing visitors", row.get("Store Listing Visitors", "0")))
        acquisitions = safe_int(
            row.get("Store listing acquisitions", row.get("Store Listing Acquisitions", "0"))
        )
        totals[(metric_date, "store_visitors")] += visitors
        totals[(metric_date, "installs")] += acquisitions
    return [
        metric_row(app, "android", metric_date, metric, value, "google_store_performance", checked_at)
        for (metric_date, metric), value in totals.items()
    ]


def parse_google_sales_zip(
    raw: bytes,
    apps_by_package: dict[str, dict[str, str]],
    checked_at: str,
) -> list[dict[str, object]]:
    totals: dict[tuple[str, str], int] = defaultdict(int)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():
            if name.endswith("/") or not name.lower().endswith(".csv"):
                continue
            source = archive.read(name)
            rows = decode_table(source, delimiter=",")
            for row in rows:
                package = row.get("Package ID", row.get("Package Id", ""))
                if package not in apps_by_package:
                    continue
                metric_date = row.get("Order charged date", row.get("Order Charged Date", ""))
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", metric_date):
                    continue
                status = row.get("Financial status", row.get("Financial Status", "")).strip().casefold()
                delta = 1 if status == "charged" else -1 if status == "refund" else 0
                if delta:
                    totals[(package, metric_date)] += delta
    return [
        metric_row(
            apps_by_package[package], "android", metric_date, "purchases",
            value, "google_estimated_sales", checked_at,
        )
        for (package, metric_date), value in totals.items()
    ]


def sync_google(
    apps: list[dict[str, str]],
    stores: list[dict[str, str]],
    bucket: str,
    token: str,
    checked_at: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    bucket = normalize_google_reports_bucket(bucket)
    if not bucket:
        return [], {"status": "not_configured"}
    months = recent_months(4)
    stores_by_package = {
        store.get("store_package", ""): store
        for store in stores
        if store.get("platform") == "android" and store.get("store_package")
    }
    apps_by_package = {
        package: app_identity(apps, store.get("app_slug", ""))
        for package, store in stores_by_package.items()
    }
    apps_by_package = {package: app for package, app in apps_by_package.items() if app}
    additions: list[dict[str, object]] = []

    performance_objects = gcs_list_objects(bucket, "stats/store_performance/", token)
    selected_performance = []
    pattern = re.compile(r"store_performance_(.+?)_(\d{6})_country\.csv$")
    for item in performance_objects:
        name = str(item.get("name", ""))
        match = pattern.search(name)
        if not match:
            continue
        package, month = match.groups()
        if package in apps_by_package and month in months:
            selected_performance.append((name, package))
    for object_name, package in selected_performance:
        raw = gcs_download(bucket, object_name, token)
        additions.extend(
            parse_google_store_performance(raw, apps_by_package[package], package, checked_at)
        )

    financial_status: dict[str, object]
    try:
        sales_objects = gcs_list_objects(bucket, "sales/", token)
        sales_pattern = re.compile(r"salesreport_(\d{6})\.zip$")
        selected_sales = [
            str(item.get("name", ""))
            for item in sales_objects
            if sales_pattern.search(str(item.get("name", "")))
            and sales_pattern.search(str(item.get("name", ""))).group(1) in months
        ]
        for object_name in selected_sales:
            additions.extend(
                parse_google_sales_zip(
                    gcs_download(bucket, object_name, token),
                    apps_by_package,
                    checked_at,
                )
            )
        financial_status = {"status": "ok", "objects": len(selected_sales)}
    except urllib.error.HTTPError as error:
        if error.code == 403:
            financial_status = {
                "status": "permission_required",
                "message": "Google Play financial reports require global View financial data permission.",
            }
        else:
            raise

    return additions, {
        "status": "ok",
        "store_performance_objects": len(selected_performance),
        "financial": financial_status,
    }


def daily_key(row: dict[str, object] | dict[str, str]) -> tuple[str, str, str, str]:
    return (
        str(row.get("date", "")),
        str(row.get("app_slug", "")),
        str(row.get("platform", "")),
        str(row.get("metric", "")),
    )


def merge_daily_metrics(
    existing: list[dict[str, str]],
    apple_additions: list[dict[str, object]],
    google_additions: list[dict[str, object]],
    google_status: dict[str, object],
    checked_at: str,
) -> list[dict[str, object]]:
    merged: dict[tuple[str, str, str, str], dict[str, object]] = {
        daily_key(row): dict(row) for row in existing
    }

    # Apple analytics instances are "new portions" of report content. Process each
    # instance once and add its counts, so late-arriving data and negative
    # correction rows remain meaningful without double-processing an instance.
    for row in apple_additions:
        key = daily_key(row)
        if key in merged:
            row = dict(row)
            row["value"] = safe_int(merged[key].get("value")) + safe_int(row.get("value"))
        merged[key] = dict(row)

    google_months = recent_months(4)
    performance_ok = (
        google_status.get("status") == "ok"
        and safe_int(google_status.get("store_performance_objects")) > 0
    )
    if performance_ok:
        for key in list(merged):
            metric_date, _, platform, metric = key
            if (
                platform == "android"
                and metric_date.replace("-", "")[:6] in google_months
                and metric in {"store_visitors", "installs"}
            ):
                del merged[key]

    financial = google_status.get("financial", {})
    financial_ok = isinstance(financial, dict) and financial.get("status") == "ok"
    if financial_ok:
        for key in list(merged):
            metric_date, _, platform, metric = key
            if (
                platform == "android"
                and metric_date.replace("-", "")[:6] in google_months
                and metric == "purchases"
            ):
                del merged[key]

    for row in google_additions:
        merged[daily_key(row)] = dict(row)

    retention_cutoff = (datetime.now(timezone.utc).date() - timedelta(days=400)).isoformat()
    result = [
        row for row in merged.values()
        if str(row.get("date", "")) >= retention_cutoff
    ]
    return sorted(result, key=lambda row: daily_key(row))


def build_summary(
    apps: list[dict[str, str]],
    daily_rows: list[dict[str, object]],
    checked_at: str,
    source_status: dict[str, object],
    *,
    today: date | None = None,
) -> dict[str, object]:
    today = today or datetime.now(timezone.utc).date()
    by_app_platform: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in daily_rows:
        by_app_platform[(str(row.get("app_slug", "")), str(row.get("platform", "")))].append(row)

    result_apps: dict[str, object] = {}
    for app in apps:
        slug = app.get("slug", "")
        if not slug:
            continue
        platforms_payload: dict[str, object] = {}
        for platform in ("ios", "android"):
            rows = by_app_platform.get((slug, platform), [])
            if not rows:
                platforms_payload[platform] = {"latest_date": "", "windows": {}}
                continue
            latest_date = max(str(row.get("date", "")) for row in rows)
            windows_payload: dict[str, object] = {}
            for window in WINDOWS:
                cutoff = (today - timedelta(days=window - 1)).isoformat()
                totals: dict[str, int] = defaultdict(int)
                dates: set[str] = set()
                for row in rows:
                    metric_date = str(row.get("date", ""))
                    if cutoff <= metric_date <= today.isoformat():
                        totals[str(row.get("metric", ""))] += safe_int(row.get("value"))
                        dates.add(metric_date)
                windows_payload[str(window)] = {
                    "impressions": totals.get("impressions") if platform == "ios" else None,
                    "store_visitors": totals.get("store_visitors"),
                    "installs": totals.get("installs"),
                    "purchases": totals.get("purchases"),
                    "days_with_data": len(dates),
                }
            platforms_payload[platform] = {
                "latest_date": latest_date,
                "windows": windows_payload,
            }

        combined: dict[str, object] = {}
        for window in WINDOWS:
            ios = platforms_payload["ios"]["windows"].get(str(window), {})
            android = platforms_payload["android"]["windows"].get(str(window), {})
            combined[str(window)] = {
                # Store visitor definitions differ by store, so don't produce a
                # misleading summed visitor/impression figure.
                "store_visitors": None,
                "impressions": None,
                "installs": safe_int(ios.get("installs")) + safe_int(android.get("installs")),
                "purchases": safe_int(ios.get("purchases")) + safe_int(android.get("purchases")),
            }
        result_apps[slug] = {
            "app_id": app.get("app_id", ""),
            "app_name": app.get("app_name", ""),
            "platforms": platforms_payload,
            "combined": combined,
        }

    return {
        "schema_version": 1,
        "checked_at": checked_at,
        "windows": list(WINDOWS),
        "metric_semantics": {
            "ios_impressions": "App Store Discovery and Engagement: Impression",
            "ios_store_visitors": "App Store Discovery and Engagement: Product page / Page view",
            "ios_installs": "App Store Downloads: First-time Download",
            "ios_purchases": "App Store Purchases: Purchases (refunds may be negative)",
            "android_store_visitors": "Google Play Store listing visitors (legacy Cloud Storage export)",
            "android_installs": "Google Play Store listing acquisitions (legacy Cloud Storage export)",
            "android_purchases": "Google Play estimated sales charged orders, net of full refund rows",
            "combined_visitors": None,
        },
        "source_status": source_status,
        "apps": result_apps,
    }


def apple_token_from_env() -> str:
    token = os.environ.get("APP_STORE_CONNECT_TOKEN", "").strip()
    if token:
        return token
    key_id = os.environ.get("APP_STORE_CONNECT_KEY_ID", "").strip()
    issuer_id = os.environ.get("APP_STORE_CONNECT_ISSUER_ID", "").strip()
    private_key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "").strip()
    encoded = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY_BASE64", "").strip()
    if not private_key and encoded:
        private_key = base64.b64decode(encoded, validate=True).decode("utf-8")
    if not any((key_id, issuer_id, private_key)):
        return ""
    return app_store_connect_token(key_id, issuer_id, private_key)


def google_token_from_env() -> tuple[str, str]:
    token = os.environ.get("GOOGLE_PLAY_ACCESS_TOKEN", "").strip()
    if token:
        return token, ""
    encoded = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
    if not encoded:
        return "", ""
    service_account_json = base64.b64decode(encoded, validate=True).decode("utf-8")
    payload = json.loads(service_account_json)
    principal = str(payload.get("client_email", "") if isinstance(payload, dict) else "")
    return google_play_access_token(service_account_json), principal


def atomic_write_outputs(
    daily_path: Path,
    summary_path: Path,
    status_path: Path,
    state_path: Path,
    daily_rows: list[dict[str, object]],
    summary: dict[str, object],
    status: dict[str, object],
    state: dict[str, object],
) -> None:
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=daily_path.parent) as temp_dir:
        temp = Path(temp_dir)
        write_daily(temp / "daily.csv", daily_rows)
        (temp / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temp / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temp / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for source, target in (
            (temp / "daily.csv", daily_path),
            (temp / "summary.json", summary_path),
            (temp / "status.json", status_path),
            (temp / "state.json", state_path),
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)


def sync_funnel(
    *,
    apps_path: Path = DEFAULT_APPS,
    stores_path: Path = DEFAULT_STORES,
    daily_path: Path = DEFAULT_DAILY,
    summary_path: Path = DEFAULT_SUMMARY,
    status_path: Path = DEFAULT_STATUS,
    state_path: Path = DEFAULT_STATE,
) -> dict[str, object]:
    checked_at = now_iso()
    apps = read_csv_rows(apps_path)
    stores = read_csv_rows(stores_path)
    existing = read_daily(daily_path)
    state = read_state(state_path)

    source_status: dict[str, object] = {}
    apple_additions: list[dict[str, object]] = []
    google_additions: list[dict[str, object]] = []

    try:
        apple_token = apple_token_from_env()
    except (ValueError, subprocess.CalledProcessError) as error:  # type: ignore[name-defined]
        apple_token = ""
        source_status["apple"] = {"status": "credential_error", "message": str(error)}
    if apple_token:
        apple_additions, apple_status = sync_apple(apps, stores, apple_token, state, checked_at)
        source_status["apple"] = {"status": "ok", "apps": apple_status}
    else:
        source_status.setdefault("apple", {"status": "not_configured"})

    google_status: dict[str, object] = {"status": "not_configured"}
    try:
        google_token, google_principal = google_token_from_env()
        bucket = os.environ.get("GOOGLE_PLAY_REPORTS_BUCKET", "").strip()
        if google_token and bucket:
            google_additions, google_status = sync_google(
                apps, stores, bucket, google_token, checked_at
            )
            if google_principal:
                google_status["principal"] = google_principal
    except (ValueError, FunnelSyncError, urllib.error.HTTPError) as error:
        google_status = {"status": "error", "message": str(error)}
    source_status["google"] = google_status

    daily_rows = merge_daily_metrics(
        existing, apple_additions, google_additions, google_status, checked_at
    )
    summary = build_summary(apps, daily_rows, checked_at, source_status)
    overall = (
        "ok"
        if any(
            isinstance(value, dict) and value.get("status") == "ok"
            for value in source_status.values()
        )
        else "waiting"
    )
    status = {
        "schema_version": 1,
        "checked_at": checked_at,
        "status": overall,
        "sources": source_status,
        "daily_rows": len(daily_rows),
        "apple_additions": len(apple_additions),
        "google_additions": len(google_additions),
    }
    atomic_write_outputs(
        daily_path, summary_path, status_path, state_path,
        daily_rows, summary, status, state,
    )
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS)
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    parser.add_argument("--daily", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    try:
        status = sync_funnel(
            apps_path=args.apps,
            stores_path=args.stores,
            daily_path=args.daily,
            summary_path=args.summary,
            status_path=args.status,
            state_path=args.state,
        )
    except (FunnelSyncError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as error:
        print(f"store funnel sync failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
