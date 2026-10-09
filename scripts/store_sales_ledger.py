#!/usr/bin/env python3
"""Private, evidence-based store sales ledger. Never commit its JSON output."""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sync_store_funnel import (
    gcs_download, gcs_list_objects, google_token_from_env,
    normalize_google_reports_bucket, read_daily,
)
from sync_store_reviews import app_store_connect_read_token_from_env, app_store_connect_token, read_csv_rows
from store_settlement import fetch_finance, merge_monthly, add_app_sku_aliases

ROOT = Path(__file__).resolve().parents[1]
STORES = ROOT / "data" / "store_versions.csv"
FIRST_DAY = date(2026, 1, 1)
APPLE_FIRST_DAY = date(2026, 3, 1)
APPLE_REFRESH_DAYS = 14
APPLE_MAPPING_VERSION = 2  # Reconcile IAP/SKU identifiers against Store Connect app metadata.
MONEY = Decimal("0.01")


class LedgerError(ValueError):
    pass


def amount(value: object) -> Decimal:
    raw = str(value or "").replace(",", "").replace("(", "-").replace(")", "").strip()
    if not raw:
        return Decimal(0)
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise LedgerError("invalid decimal money field") from exc


def iso_day(value: object) -> str:
    raw = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%d %b %Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def lookup(row: dict[str, str], *keys: str) -> str:
    fields = {re.sub(r"[^a-z0-9]", "", k.casefold()): v for k, v in row.items()}
    for key in keys:
        field = fields.get(re.sub(r"[^a-z0-9]", "", key.casefold()))
        if field is not None:
            return str(field).strip()
    return ""


def read_table(source: bytes, delimiter: str = ",") -> list[dict[str, str]]:
    if source.startswith(b"\x1f\x8b"):
        source = gzip.decompress(source)
    encoding = "utf-16" if source.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    result = source.decode(encoding)
    if result.startswith("#"):
        result = "\n".join(line for line in result.splitlines() if not line.startswith("#"))
    return list(csv.DictReader(io.StringIO(result), delimiter=delimiter))


def require_report_headers(rows: list[dict], name: str, *required: tuple[str, ...]) -> None:
    """Fail closed when a vendor changes a financial CSV schema.

    A valid header-only report contains no transactions; an unfamiliar report
    containing rows must never be interpreted as 0 won or 0 fees.
    """
    if not rows:
        return
    actual = {re.sub(r"[^a-z0-9]", "", str(key).casefold())
              for key in rows[0].keys() if key is not None}
    for alternatives in required:
        if not any(re.sub(r"[^a-z0-9]", "", x.casefold()) in actual
                   for x in alternatives):
            raise LedgerError("Unsupported " + name + " report fields")


def csv_from_zip(raw: bytes):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in sorted(archive.namelist()):
            if name.lower().endswith(".csv") and not name.endswith("/"):
                yield name, read_table(archive.read(name))


def make_event(day: str, platform: str, app: dict[str, str], country: str, currency: str,
               source: str, *, units: int = 0, gross=0, refund=0, fee=0,
               proceeds=0, proceeds_currency: str = "") -> dict:
    return {
        "date": day, "platform": platform, "app_slug": app["app_slug"],
        "app_name": app["app_name"], "country": (country or "ZZ").upper(),
        "currency": currency.upper(), "source": source, "units": units,
        "gross": str(gross), "refund": str(refund), "fee": str(fee),
        "proceeds": str(proceeds), "proceeds_currency": proceeds_currency.upper(),
    }


def parse_google_sales_zip(raw: bytes, apps: dict[str, dict[str, str]]) -> list[dict]:
    events = []
    for _, rows in csv_from_zip(raw):
        require_report_headers(rows, "Google Sales",
                               ("Package ID",), ("Financial status",),
                               ("Currency of Sale",), ("Charged Amount",),
                               ("Order charged date",), ("Country of Buyer",))
        for row in rows:
            package = lookup(row, "Package ID", "Package Id")
            if package not in apps:
                continue
            state = lookup(row, "Financial status").casefold()
            if state not in {"charged", "refund", "partial refund"}:
                continue
            day = iso_day(lookup(row, "Order refunded date" if state in {"refund", "partial refund"} else "Order charged date"))
            if not day:
                day = iso_day(lookup(row, "Order charged date"))
            if not day:
                continue
            currency = lookup(row, "Currency of Sale")
            if not currency:
                # Never mix buyer-currency and merchant-currency monetary fields.
                continue
            charged = lookup(row, "Charged Amount")
            if not charged:
                raise LedgerError("Google Sales charged amount missing")
            value = abs(amount(charged))
            country = lookup(row, "Country of Buyer")
            events.append(make_event(day, "android", apps[package], country, currency,
                                     "google_sales_estimate", units=1 if state == "charged" else -1 if state == "refund" else 0,
                                     gross=value if state == "charged" else 0,
                                     refund=-value if state in {"refund", "partial refund"} else 0))
    return events


def parse_google_earnings_zip(raw: bytes, apps: dict[str, dict[str, str]]) -> list[dict]:
    events = []
    for _, rows in csv_from_zip(raw):
        require_report_headers(rows, "Google Earnings",
                               ("Package ID",), ("Transaction Type",),
                               ("Transaction Date",),
                               ("Amount (Merchant Currency)", "Amount Due (Sale Currency)"))
        for row in rows:
            package = lookup(row, "Package ID")
            if package not in apps:
                continue
            kind = lookup(row, "Transaction Type").casefold()
            if kind not in {"google fee", "google fee refund", "google fee partial refund", "google fee rebill"}:
                continue
            day = iso_day(lookup(row, "Transaction Date"))
            # Earnings CSV has two published layouts; one gives buyer-country and
            # merchant-currency amount, another gives sale-country and sale-currency due.
            merchant_value = lookup(row, "Amount (Merchant Currency)")
            sale_value = lookup(row, "Amount Due (Sale Currency)")
            if merchant_value:
                currency = lookup(row, "Merchant Currency")
                value = amount(merchant_value)
            else:
                currency = lookup(row, "Sale Currency")
                value = amount(sale_value)
            if not day or not currency or not (merchant_value or sale_value):
                raise LedgerError("Google Earnings fee row has missing date or money")
            # Fees are expenses; fee-refund rows reverse that expense.
            signed_fee = -abs(value) if "refund" in kind else abs(value)
            country = lookup(row, "Buyer Country", "Sale Country", "Country")
            events.append(make_event(day, "android", apps[package], country, currency,
                                     "google_earnings_actual", fee=signed_fee))
    return events


def parse_apple_sales(raw: bytes, apps: dict[str, dict[str, str]], day: str,
                      stats: dict | None = None) -> list[dict]:
    events = []
    report_rows = read_table(raw, delimiter="\t")
    require_report_headers(report_rows, "Apple Sales",
                           ("Apple Identifier",), ("Units",),
                           ("Country Code",), ("Customer Price",),
                           ("Customer Currency",), ("Developer Proceeds",),
                           ("Currency of Proceeds",))
    for row in report_rows:
        if stats is not None:
            stats["report_rows"] = stats.get("report_rows", 0) + 1
        appid = lookup(row, "Apple Identifier")
        parent = lookup(row, "Parent Identifier")
        sku = lookup(row, "SKU")
        # IAP Apple Identifiers are PRODUCT IDs, not App Store application IDs.
        # The SKU and Parent Identifier may refer to the parent app instead.
        app = apps.get(appid) or apps.get(parent) or apps.get(sku)
        if not app:
            if stats is not None:
                stats["unmatched_rows"] = stats.get("unmatched_rows", 0) + 1
            continue
        if stats is not None:
            stats["matched_rows"] = stats.get("matched_rows", 0) + 1
        count = amount(lookup(row, "Units"))
        price = amount(lookup(row, "Customer Price"))
        if count == 0 or price == 0:
            if stats is not None:
                stats["zero_price_or_units_rows"] = stats.get("zero_price_or_units_rows", 0) + 1
            continue
        if count != count.to_integral_value():
            raise LedgerError("Invalid Apple units quantity")
        units = int(count)
        customer_currency = lookup(row, "Customer Currency")
        proceeds_currency = lookup(row, "Currency of Proceeds")
        if not customer_currency or not proceeds_currency:
            if stats is not None:
                stats["missing_currency_rows"] = stats.get("missing_currency_rows", 0) + 1
            raise LedgerError("Apple paid sale missing currency")
        if stats is not None:
            stats["paid_rows"] = stats.get("paid_rows", 0) + 1
            stats["paid_units"] = stats.get("paid_units", 0) + units
        refund = units < 0 or price < 0
        total = abs(count * price)
        partner_price = amount(lookup(row, "Developer Proceeds"))
        proceeds = (Decimal(-1) if refund else Decimal(1)) * abs(partner_price * count)
        country = lookup(row, "Country Code")
        events.append(make_event(day, "ios", app, country, customer_currency,
                                 "apple_sales_estimate", units=-abs(units) if refund else abs(units),
                                 gross=0 if refund else total,
                                 refund=-total if refund else 0,
                                 proceeds=proceeds, proceeds_currency=proceeds_currency))
    return events


def aggregate(events: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for event in events:
        key = tuple(event[k] for k in ("date", "platform", "app_slug", "country", "currency"))
        item = grouped.setdefault(key, {
            "date": event["date"], "platform": event["platform"], "app_slug": event["app_slug"],
            "app_name": event["app_name"], "country": event["country"], "currency": event["currency"],
            "units": 0, "gross": Decimal(0), "refund": Decimal(0), "fee": Decimal(0),
            "proceeds": Decimal(0), "proceeds_currency": "", "fee_confirmed": False,
            "sources": set(),
        })
        item["units"] += event["units"]
        for field in ("gross", "refund", "fee"):
            item[field] += amount(event[field])
        if event["source"] == "google_earnings_actual":
            item["fee_confirmed"] = True
        if event["proceeds_currency"]:
            if not item["proceeds_currency"] or item["proceeds_currency"] == event["proceeds_currency"]:
                item["proceeds_currency"] = event["proceeds_currency"]
                item["proceeds"] += amount(event["proceeds"])
            else:
                raise LedgerError("multiple proceeds currencies in one group")
        item["sources"].add(event["source"])
    result = []
    for item in sorted(grouped.values(), key=lambda x: (x["date"], x["platform"], x["app_slug"], x["country"], x["currency"]), reverse=True):
        for name in ("gross", "refund", "fee", "proceeds"):
            item[name] = str(item[name].quantize(MONEY))
        item["net_sales"] = str((amount(item["gross"]) + amount(item["refund"])).quantize(MONEY))
        item["sources"] = sorted(item["sources"])
        result.append(item)
    return result


def google_ledger(stores: list[dict], as_of: date, earliest: date = FIRST_DAY) -> tuple[list[dict], dict]:
    bucket = normalize_google_reports_bucket(os.getenv("GOOGLE_PLAY_REPORTS_BUCKET", ""))
    token, _ = google_token_from_env()
    if not bucket or not token:
        return [], {"status": "not_configured"}
    apps = {s["store_package"]: s for s in stores if s.get("platform") == "android" and s.get("store_package")}
    events: list[dict] = []
    statuses: dict[str, object] = {
        "status": "ok", "sales_files": 0, "earnings_files": 0,
        "sales_months": [], "earnings_months": [],
    }
    statuses["earnings_objects_listed"] = 0
    statuses["earnings_unrecognized_files"] = 0
    for prefix, matcher, fn, label in (
        ("sales/", r"salesreport_(\d{6})\.zip$", parse_google_sales_zip, "sales_files"),
        ("earnings/", r"^earnings/earnings_(\d{6})(?:_[A-Za-z0-9_-]+)?\.zip$", parse_google_earnings_zip, "earnings_files"),
    ):
        objects = gcs_list_objects(bucket, prefix, token)
        if prefix == "earnings/":
            statuses["earnings_objects_listed"] = len(objects)
        for obj in objects:
            filename = str(obj.get("name", ""))
            match = re.search(matcher, filename)
            if not match:
                if prefix == "earnings/" and filename.lower().endswith(".zip"):
                    statuses["earnings_unrecognized_files"] += 1
                continue
            yyyy_mm = match.group(1)
            month = date(int(yyyy_mm[:4]), int(yyyy_mm[4:]), 1)
            if not (earliest.replace(day=1) <= month <= as_of.replace(day=1)):
                continue
            events.extend(fn(gcs_download(bucket, filename, token), apps))
            statuses[label] += 1
            month_key = "sales_months" if label == "sales_files" else "earnings_months"
            statuses[month_key].append(yyyy_mm[:4] + "-" + yyyy_mm[4:])
    statuses["sales_months"] = sorted(set(statuses["sales_months"]))
    statuses["earnings_months"] = sorted(set(statuses["earnings_months"]))
    previous_month = (as_of.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    statuses["missing_earnings_months"] = [
        month for month in statuses["sales_months"]
        if month <= previous_month and month not in statuses["earnings_months"]
    ]
    statuses["fee_source_status"] = (
        "available" if statuses["earnings_files"] else "awaiting_earnings_report"
    )
    if not statuses["sales_files"] and not statuses["earnings_files"]:
        statuses["status"] = "no_reports"
    elif not statuses["sales_files"] or not statuses["earnings_files"] or (
        statuses["earnings_unrecognized_files"]
    ):
        statuses["status"] = "partial"
    return events, statuses


def apple_sales_token() -> str:
    # Finance API keys are intentionally separate from store release and review
    # keys. Never overwrite a working upload/review credential to enable finance.
    dedicated = {
        "key_id": os.getenv("APP_STORE_FINANCE_KEY_ID", "").strip(),
        "issuer_id": os.getenv("APP_STORE_FINANCE_ISSUER_ID", "").strip(),
        "encoded": os.getenv("APP_STORE_FINANCE_PRIVATE_KEY_BASE64", "").strip(),
    }
    if any(dedicated.values()):
        if not all(dedicated.values()):
            raise LedgerError("incomplete dedicated Apple Finance API credentials")
        private_key = base64.b64decode(
            dedicated["encoded"], validate=True
        ).decode("utf-8")
        return app_store_connect_token(
            dedicated["key_id"], dedicated["issuer_id"], private_key,
            key_type="team",
        )

    # Backward-compatible fallback for teams with a valid existing Team key.
    team_key = os.getenv("APP_STORE_CONNECT_KEY_ID", "").strip()
    issuer_id = os.getenv("APP_STORE_CONNECT_ISSUER_ID", "").strip()
    encoded = os.getenv("APP_STORE_CONNECT_PRIVATE_KEY_BASE64", "").strip()
    if team_key and issuer_id and encoded:
        private_key = base64.b64decode(encoded, validate=True).decode("utf-8")
        return app_store_connect_token(team_key, issuer_id, private_key, key_type="team")
    if os.getenv("APP_STORE_CONNECT_READ_KEY_TYPE", "").lower().strip() == "individual":
        raise LedgerError("finance reports require a team API key")
    return app_store_connect_read_token_from_env()


def apple_ledger(stores: list[dict], as_of: date, earliest: date = FIRST_DAY, *,
                 previous_status: dict | None = None, app_aliases: dict | None = None,
                 sku_status: dict | None = None) -> tuple[list[dict], dict]:
    vendor = os.getenv("APP_STORE_VENDOR_NUMBER", "").strip()
    if not vendor:
        return [], {"status": "vendor_number_required"}
    try:
        token = apple_sales_token()
    except Exception:
        return [], {"status": "credentials_unavailable"}
    apps = {s["store_app_id"]: s for s in stores if s.get("platform") == "ios" and s.get("store_app_id")}
    # Include verified App Store Connect parent-app SKUs. An in-app product's
    # Apple Identifier can be unrelated to the app's public App Store ID.
    for alias, store in (app_aliases or {}).items():
        if store.get("store_app_id") in apps:
            if alias in apps and apps[alias]["app_slug"] != store["app_slug"]:
                raise LedgerError("Apple app alias collision")
            apps[alias] = store
    # Apple daily sales data becomes available the next day; never infer today's sales as zero.
    cursor = max(earliest, APPLE_FIRST_DAY, as_of - timedelta(days=364))
    prior = previous_status if isinstance(previous_status, dict) else {}
    sku_status = sku_status or {"status":"ok"}
    mapping_verified = sku_status.get("status") == "ok"
    # Backfilled historical "success" must not survive a parser/ID mapping
    # upgrade: those reports may contain IAP transactions silently discarded.
    remap_history = prior.get("app_mapping_version") != APPLE_MAPPING_VERSION
    checked_days = set(prior.get("completed_days", []))
    missing_days = set(prior.get("missing_days", []))
    checked_days = {value for value in checked_days if cursor.isoformat() <= value < as_of.isoformat()}
    missing_days = {value for value in missing_days if cursor.isoformat() <= value < as_of.isoformat()}
    events: list[dict] = []
    new_checked = 0
    refreshed_days: list[str] = []
    errors: list[str] = []
    parser_stats: dict[str, int] = {}
    while cursor < as_of:
        day = cursor.isoformat()
        recent = cursor >= as_of - timedelta(days=APPLE_REFRESH_DAYS)
        if not recent and not remap_history and (day in checked_days or day in missing_days):
            cursor += timedelta(days=1)
            continue
        params = urllib.parse.urlencode({
            "filter[frequency]": "DAILY",
            "filter[reportDate]": day,
            "filter[reportType]": "SALES",
            "filter[reportSubType]": "SUMMARY",
            "filter[vendorNumber]": vendor,
        })
        req = urllib.request.Request(
            "https://api.appstoreconnect.apple.com/v1/salesReports?" + params,
            headers={"Authorization": "Bearer " + token, "Accept": "application/a-gzip"},
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                events.extend(parse_apple_sales(response.read(), apps, day, parser_stats))
            checked_days.add(day)
            missing_days.discard(day)
            refreshed_days.append(day)
            new_checked += 1
        except urllib.error.HTTPError as error:
            if error.code == 404:
                missing_days.add(day)
                checked_days.discard(day)
            else:
                errors.append(f"{day}: HTTP {error.code}")
                if error.code in {401, 403, 429}:
                    break
        cursor += timedelta(days=1)
    unresolved = (not mapping_verified or parser_stats.get("unmatched_rows", 0) > 0)
    status = (
        "partial" if errors or (checked_days and unresolved)
        else "no_reports" if not checked_days
        else "ok"
    )
    return events, {
        "status": status, "days_checked": len(checked_days),
        "days_missing": len(missing_days), "new_reports": new_checked,
        "completed_days": sorted(checked_days), "missing_days": sorted(missing_days),
        "refreshed_days": refreshed_days, "errors": errors[:8],
        "app_mapping_version": APPLE_MAPPING_VERSION if mapping_verified and not errors else 0,
        "sku_mapping": sku_status.get("status", "unknown"),
        "sku_aliases": len(apps) - len({
            s["store_app_id"] for s in stores if s.get("platform") == "ios" and s.get("store_app_id")
        }),
        "rechecked_history": remap_history, "parser_rows": parser_stats,
    }



def build_ledger(as_of: date, *, earliest: date = FIRST_DAY, apple: bool = True,
                 google: bool = True, previous: dict | None = None) -> dict:
    if earliest > as_of:
        raise LedgerError("start date exceeds as-of date")
    stores = read_csv_rows(STORES)
    events: list[dict] = []
    status = {}
    if google:
        rows, state = google_ledger(stores, as_of, earliest)
        events += rows
        status["google"] = state
    settlements: list[dict] = []
    if apple:
        vendor = os.getenv("APP_STORE_VENDOR_NUMBER", "").strip()
        finance_apps = {
            store["store_app_id"]: store for store in stores
            if store.get("platform") == "ios" and store.get("store_app_id")
        }
        token = ""
        sku_status = {"status": "unavailable"}
        if vendor:
            try:
                token = apple_sales_token()
                finance_apps, sku_status = add_app_sku_aliases(token, finance_apps)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                # Do not mark old Apple days reconciled after incomplete metadata.
                sku_status = {"status": "unavailable", "error_type": type(exc).__name__}
        old_status = (previous or {}).get("source_status", {}).get("apple", {})
        rows, state = apple_ledger(
            stores, as_of, earliest, previous_status=old_status,
            app_aliases=finance_apps, sku_status=sku_status,
        )
        events += rows
        status["apple"] = state
        if vendor and state["status"] != "credentials_unavailable" and token:
            prior_finance = (previous or {}).get("source_status", {}).get("apple_finance", {})
            fresh, finance_state = fetch_finance(
                token, vendor, finance_apps, max(earliest, APPLE_FIRST_DAY), as_of,
                previous=prior_finance,
                sku_reconciled=sku_status.get('status') == 'ok',
            )
            finance_state["app_sku_status"] = sku_status
            status["apple_finance"] = finance_state
            settlements = merge_monthly(
                (previous or {}).get("settlements", []), fresh,
                finance_state.get("refreshed_months", []),
            )
        else:
            status["apple_finance"] = {
                "status":"vendor_number_required" if not vendor else "credentials_unavailable",
                "errors":[],
            }
    return {
        "schema_version": 1,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "earliest": earliest.isoformat(),
        "as_of": as_of.isoformat(),
        "source_status": status,
        "rows": aggregate(events),
        "settlements": settlements,
        "notices": [
            "Apple daily sales and Google salesreport data are estimates, not final settlement.",
            "Google fee is actual only where earnings report contains Google fee transactions.",
            "Apple customer price includes tax; it is not valid to treat customer price less proceeds as platform fee.",
            "Keep amounts in original currencies; never add figures across currencies.",
            "No transactions in an unavailable report is NOT evidence of zero sales.",
        ],
    }


def merge_sales_history(latest: dict, previous: dict, as_of: date) -> list[dict]:
    """Replace complete Google snapshots; refresh Apple only on fetched days.

    Google ZIPs are collected afresh every run. Keeping a stale Google row when
    it disappeared from a corrected monthly Earnings report would overstate
    confirmed fees. Conversely, an incomplete source must not erase evidence.
    """
    old_rows = [row for row in previous.get("rows", []) if isinstance(row, dict)]
    new_rows = [row for row in latest.get("rows", []) if isinstance(row, dict)]
    statuses = latest.get("source_status", {})
    current_google = statuses.get("google", {})
    old_google = (previous.get("source_status") or {}).get("google") or {}

    current_months = {
        name: set(current_google.get(name, []))
        for name in ("sales_months", "earnings_months")
    }
    missing_old = {
        name: sorted(set(old_google.get(name, [])) - current_months[name])
        for name in current_months
    }
    google_complete = (
        current_google.get("status") == "ok"
        and current_google.get("sales_files", 0) > 0
        and current_google.get("earnings_files", 0) > 0
        and not any(missing_old.values())
    )
    current_google["snapshot_replaced"] = google_complete
    if not google_complete and any(row.get("platform") == "android" for row in old_rows):
        current_google["underlying_status"] = current_google.get("status", "not_collected")
        current_google["status"] = "partial"
        current_google["previous_snapshot_retained"] = True
        current_google["missing_previous_report_months"] = {
            name: len(months) for name, months in missing_old.items()
        }

    refreshed_apple = set(
        statuses.get("apple", {}).get("refreshed_days", [])
    )
    limit = as_of.isoformat()
    def identity(row):
        return tuple(str(row.get(field, "")) for field in
                     ("date", "platform", "app_slug", "country", "currency"))
    combined = {}
    had_previous_google = any(row.get("platform") == "android" for row in old_rows)
    for row in old_rows:
        if row.get("date", "") > limit:
            continue
        if row.get("platform") == "ios" and row.get("date") in refreshed_apple:
            continue
        if row.get("platform") == "android" and google_complete:
            continue
        combined[identity(row)] = row
    for row in new_rows:
        if row.get("date", "") > limit:
            continue
        if row.get("platform") == "android" and not google_complete and had_previous_google:
            continue
        combined[identity(row)] = row
    return sorted(combined.values(), key=identity, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build private store finance ledger")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--earliest", type=date.fromisoformat, default=FIRST_DAY)
    parser.add_argument("--previous", type=Path, help="Decrypted prior private ledger")
    parser.add_argument("--no-google", action="store_true")
    parser.add_argument("--no-apple", action="store_true")
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if (
        args.previous and args.previous.exists()
    ) else None
    ledger = build_ledger(args.as_of, earliest=args.earliest, google=not args.no_google,
                          apple=not args.no_apple, previous=previous)
    if previous:
        ledger["rows"] = merge_sales_history(ledger, previous, args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(args.output, 0o600)
    # Do not print customer rows, currency amounts or authentication details into CI logs.
    print("Private ledger created (not suitable for public git or logs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
