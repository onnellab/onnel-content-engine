#!/usr/bin/env python3
"""Synchronize current store prices for ONNELLAB apps without exposing credentials."""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from sync_store_reviews import (
    app_store_connect_token,
    apple_store_app_id,
    fetch_json,
    google_play_access_token,
    google_store_package,
    read_csv_rows,
    urlopen_with_retry,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORES = ROOT / "data" / "store_versions.csv"
DEFAULT_OUTPUT = ROOT / "data" / "store_pricing_snapshot.json"
APPLE = "https://api.appstoreconnect.apple.com"
GOOGLE = "https://androidpublisher.googleapis.com/androidpublisher/v3"
TARGET_COUNTRY = "KR"
APPLE_TERRITORY = "KOR"
TRANSIENT_OR_AUTH = {401, 403, 429, 500, 502, 503, 504}


class StorePricingError(ValueError):
    """Raised when a live price response is malformed or unsafe to publish."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_get(url: str, *, token: str = "") -> dict[str, object]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "ONNELLAB-Store-Pricing-Sync/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urlopen_with_retry(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise StorePricingError("store_pricing_json_invalid")
    return payload


def _html_get(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "ONNELLAB-Store-Pricing-Sync/1.0",
        },
    )
    with urlopen_with_retry(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _decode_credentials() -> tuple[str, str]:
    apple = os.environ.get("APP_STORE_CONNECT_TOKEN", "").strip()
    if not apple:
        key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY", "").strip()
        encoded = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY_BASE64", "").strip()
        if not key and encoded:
            key = base64.b64decode(encoded, validate=True).decode("utf-8")
        if key:
            apple = app_store_connect_token(
                os.environ.get("APP_STORE_CONNECT_KEY_ID", ""),
                os.environ.get("APP_STORE_CONNECT_ISSUER_ID", ""),
                key,
            )
    google = os.environ.get("GOOGLE_PLAY_ACCESS_TOKEN", "").strip()
    if not google:
        encoded = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
        if encoded:
            google = google_play_access_token(
                base64.b64decode(encoded, validate=True).decode("utf-8")
            )
    return apple, google


def _decimal_text(value: object) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ""
    normalized = number.quantize(Decimal("1")) if number == number.to_integral() else number.normalize()
    return format(normalized, "f")


def _micros_price(value: object) -> tuple[str, str]:
    if not isinstance(value, dict):
        return "", ""
    micros = str(value.get("priceMicros", "") or "").strip()
    currency = str(value.get("currency", "") or "").strip()
    if not micros.isdigit() or not currency:
        return "", ""
    amount = Decimal(micros) / Decimal(1_000_000)
    return _decimal_text(amount), currency


def _product(
    store: dict[str, str],
    *,
    product_type: str,
    product_id: str,
    product_name: str,
    price: str,
    currency: str,
    state: str,
    source: str,
    checked_at: str,
    platform: str,
    price_display: str = "",
    base_plan_id: str = "",
) -> dict[str, str]:
    return {
        "app_id": store.get("app_id", ""),
        "app_slug": store.get("app_slug", ""),
        "app_name": store.get("app_name", ""),
        "platform": platform,
        "product_type": product_type,
        "product_id": product_id,
        "base_plan_id": base_plan_id,
        "product_name": product_name,
        "price": price,
        "currency": currency,
        "price_display": price_display,
        "territory": TARGET_COUNTRY,
        "state": state,
        "source": source,
        "checked_at": checked_at,
    }


def apple_public_download_price(store: dict[str, str], checked_at: str) -> list[dict[str, str]]:
    app_id = apple_store_app_id(store)
    if not app_id:
        return []
    url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"id": app_id, "country": TARGET_COUNTRY.lower()}
    )
    payload = _json_get(url)
    results = payload.get("results", [])
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise StorePricingError("apple_public_price_missing")
    row = results[0]
    price = _decimal_text(row.get("price", ""))
    currency = str(row.get("currency", "") or "")
    if not price or Decimal(price) <= 0:
        return []
    return [_product(
        store,
        product_type="paid_download",
        product_id=app_id,
        product_name=str(row.get("trackName", "") or store.get("app_name", "")),
        price=price,
        currency=currency,
        price_display=str(row.get("formattedPrice", "") or ""),
        state="available",
        source="apple_itunes_lookup",
        checked_at=checked_at,
        platform="ios",
    )]


def google_public_download_price(store: dict[str, str], checked_at: str) -> list[dict[str, str]]:
    store_url = store.get("store_url", "")
    package = google_store_package(store)
    if not store_url or not package:
        return []
    parsed = urllib.parse.urlsplit(store_url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query.update({"hl": ["ko"], "gl": [TARGET_COUNTRY]})
    url = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query, doseq=True), parsed.fragment)
    )
    html = _html_get(url)
    if package not in html:
        raise StorePricingError("google_public_price_page_mismatch")
    match = re.search(r'itemprop="price"\s+content="([^"]+)"', html, re.I)
    if not match:
        return []
    display = match.group(1).strip()
    digits = re.sub(r"[^0-9]", "", display)
    if not digits or int(digits) <= 0:
        return []
    return [_product(
        store,
        product_type="paid_download",
        product_id=package,
        product_name=store.get("app_name", ""),
        price=str(int(digits)),
        currency="KRW",
        price_display=display,
        state="available",
        source="google_play_public_page",
        checked_at=checked_at,
        platform="android",
    )]


def _paged_apple(url: str, token: str, max_pages: int = 50) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    next_url = url
    for _ in range(max_pages):
        if not next_url:
            return result
        if next_url in seen:
            raise StorePricingError("apple_pricing_pagination_repeated")
        seen.add(next_url)
        payload = fetch_json(next_url, token)
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            raise StorePricingError("apple_pricing_list_invalid")
        result.extend(row for row in rows if isinstance(row, dict))
        links = payload.get("links", {})
        next_url = str(links.get("next", "") if isinstance(links, dict) else "").strip()
    raise StorePricingError("apple_pricing_pagination_exceeded")


def _rel_id(row: dict[str, object], name: str) -> str:
    relationships = row.get("relationships", {})
    if not isinstance(relationships, dict):
        return ""
    relation = relationships.get(name, {})
    if not isinstance(relation, dict):
        return ""
    data = relation.get("data", {})
    if not isinstance(data, dict):
        return ""
    return str(data.get("id", "") or "")


def _current_price_from_apple_rows(
    rows: list[dict[str, object]],
    included: list[dict[str, object]],
    *,
    price_point_type: str,
    price_point_relation: str,
) -> tuple[str, str]:
    today = date.today().isoformat()
    included_by_key = {
        (str(item.get("type", "")), str(item.get("id", ""))): item
        for item in included
        if isinstance(item, dict)
    }
    eligible: list[tuple[str, int, str, str]] = []
    for row in rows:
        attributes = row.get("attributes", {})
        if not isinstance(attributes, dict):
            continue
        start = str(attributes.get("startDate", "") or "")
        end = str(attributes.get("endDate", "") or "")
        if start and start > today:
            continue
        if end and end < today:
            continue
        point_id = _rel_id(row, price_point_relation)
        point = included_by_key.get((price_point_type, point_id), {})
        point_attrs = point.get("attributes", {}) if isinstance(point, dict) else {}
        if not isinstance(point_attrs, dict):
            point_attrs = {}
        customer_price = _decimal_text(point_attrs.get("customerPrice", ""))
        territory_id = _rel_id(row, "territory") or _rel_id(point, "territory") if isinstance(point, dict) else ""
        territory = included_by_key.get(("territories", territory_id), {})
        territory_attrs = territory.get("attributes", {}) if isinstance(territory, dict) else {}
        currency = str(territory_attrs.get("currency", "") or "") if isinstance(territory_attrs, dict) else ""
        if customer_price and currency:
            eligible.append((start or "0000-00-00", int(bool(attributes.get("manual"))), customer_price, currency))
    if not eligible:
        return "", ""
    _, _, price, currency = max(eligible)
    return price, currency


def _apple_schedule_prices(
    schedule_id: str,
    token: str,
    *,
    kind: str,
) -> tuple[str, str]:
    if kind == "iap":
        base = f"{APPLE}/v1/inAppPurchasePriceSchedules/{urllib.parse.quote(schedule_id)}/"
        data_type = "inAppPurchasePrices"
        point_type = "inAppPurchasePricePoints"
        point_relation = "inAppPurchasePricePoint"
        fields_prices = "startDate,endDate,manual,inAppPurchasePricePoint,territory"
        fields_points = "customerPrice,territory"
        point_field_name = "inAppPurchasePricePoints"
    else:
        base = f"{APPLE}/v1/appPriceSchedules/{urllib.parse.quote(schedule_id)}/"
        data_type = "appPrices"
        point_type = "appPricePoints"
        point_relation = "appPricePoint"
        fields_prices = "startDate,endDate,manual,appPricePoint,territory"
        fields_points = "customerPrice,territory"
        point_field_name = "appPricePoints"
    rows: list[dict[str, object]] = []
    included: list[dict[str, object]] = []
    for lane in ("manualPrices", "automaticPrices"):
        params = {
            "filter[territory]": APPLE_TERRITORY,
            "include": f"{point_relation},territory",
            f"fields[{data_type}]": fields_prices,
            f"fields[{point_field_name}]": fields_points,
            "fields[territories]": "currency",
            "limit": "200",
        }
        payload = fetch_json(base + lane + "?" + urllib.parse.urlencode(params), token)
        data = payload.get("data", [])
        extras = payload.get("included", [])
        if isinstance(data, list):
            rows.extend(item for item in data if isinstance(item, dict))
        if isinstance(extras, list):
            included.extend(item for item in extras if isinstance(item, dict))
    return _current_price_from_apple_rows(
        rows,
        included,
        price_point_type=point_type,
        price_point_relation=point_relation,
    )


def apple_iap_prices(store: dict[str, str], token: str, checked_at: str) -> list[dict[str, str]]:
    app_id = apple_store_app_id(store)
    if not app_id or not token:
        return []
    url = f"{APPLE}/v1/apps/{urllib.parse.quote(app_id)}/inAppPurchasesV2?limit=50"
    purchases = _paged_apple(url, token)
    result: list[dict[str, str]] = []
    for item in purchases:
        iap_id = str(item.get("id", "") or "")
        attrs = item.get("attributes", {})
        if not iap_id or not isinstance(attrs, dict):
            continue
        schedule = fetch_json(
            f"{APPLE}/v2/inAppPurchases/{urllib.parse.quote(iap_id)}/iapPriceSchedule",
            token,
        )
        schedule_data = schedule.get("data", {})
        schedule_id = str(schedule_data.get("id", "") if isinstance(schedule_data, dict) else "")
        price, currency = _apple_schedule_prices(schedule_id, token, kind="iap") if schedule_id else ("", "")
        if not price:
            continue
        result.append(_product(
            store,
            product_type="in_app_purchase",
            product_id=str(attrs.get("productId", "") or iap_id),
            product_name=str(attrs.get("name", "") or attrs.get("productId", "") or iap_id),
            price=price,
            currency=currency,
            state=str(attrs.get("state", "") or ""),
            source="app_store_connect_iap_price_schedule",
            checked_at=checked_at,
            platform="ios",
        ))
    return result


def _google_paged(url: str, token: str, list_key: str, page_key: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    next_token = ""
    seen: set[str] = set()
    for _ in range(100):
        parsed = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        if next_token:
            params[page_key] = next_token
        page_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(params), parsed.fragment)
        )
        payload = fetch_json(page_url, token)
        rows = payload.get(list_key, [])
        if not isinstance(rows, list):
            raise StorePricingError("google_pricing_list_invalid")
        result.extend(item for item in rows if isinstance(item, dict))
        pagination = payload.get("tokenPagination", {})
        candidate = ""
        if isinstance(pagination, dict):
            candidate = str(pagination.get("nextPageToken", "") or "")
        candidate = candidate or str(payload.get("nextPageToken", "") or "")
        if not candidate:
            return result
        if candidate in seen:
            raise StorePricingError("google_pricing_pagination_repeated")
        seen.add(candidate)
        next_token = candidate
    raise StorePricingError("google_pricing_pagination_exceeded")


def _google_listing_name(product: dict[str, object], fallback: str) -> str:
    listings = product.get("listings", {})
    if isinstance(listings, dict):
        for key in ("ko-KR", "en-US", "en-GB"):
            value = listings.get(key)
            if isinstance(value, dict) and value.get("title"):
                return str(value["title"])
        for value in listings.values():
            if isinstance(value, dict) and value.get("title"):
                return str(value["title"])
    if isinstance(listings, list):
        for value in listings:
            if isinstance(value, dict) and value.get("title"):
                return str(value["title"])
    return fallback


def google_iap_prices(store: dict[str, str], token: str, checked_at: str) -> list[dict[str, str]]:
    package = google_store_package(store)
    if not package or not token:
        return []
    encoded = urllib.parse.quote(package, safe="")
    result: list[dict[str, str]] = []
    products = _google_paged(
        f"{GOOGLE}/applications/{encoded}/inappproducts",
        token,
        "inappproduct",
        "token",
    )
    for item in products:
        sku = str(item.get("sku", "") or "")
        purchase_type = str(item.get("purchaseType", "") or "")
        if not sku or purchase_type.lower() == "subscription":
            continue
        regional = item.get("prices", {})
        price_obj = regional.get(TARGET_COUNTRY, {}) if isinstance(regional, dict) else {}
        price, currency = _micros_price(price_obj)
        if not price:
            continue
        result.append(_product(
            store,
            product_type="in_app_purchase",
            product_id=sku,
            product_name=_google_listing_name(item, sku),
            price=price,
            currency=currency,
            state=str(item.get("status", "") or ""),
            source="google_play_developer_inappproducts",
            checked_at=checked_at,
            platform="android",
        ))
    subscriptions = _google_paged(
        f"{GOOGLE}/applications/{encoded}/subscriptions?pageSize=1000",
        token,
        "subscriptions",
        "pageToken",
    )
    for item in subscriptions:
        product_id = str(item.get("productId", "") or "")
        if not product_id:
            continue
        name = _google_listing_name(item, product_id)
        base_plans = item.get("basePlans", [])
        if not isinstance(base_plans, list):
            continue
        for base_plan in base_plans:
            if not isinstance(base_plan, dict):
                continue
            regional = base_plan.get("regionalConfigs", [])
            if not isinstance(regional, list):
                continue
            config = next(
                (r for r in regional if isinstance(r, dict) and r.get("regionCode") == TARGET_COUNTRY),
                None,
            )
            if not isinstance(config, dict):
                continue
            price, currency = _micros_price(config.get("price", {}))
            if not price:
                continue
            result.append(_product(
                store,
                product_type="subscription",
                product_id=product_id,
                product_name=name,
                price=price,
                currency=currency,
                state=str(base_plan.get("state", "") or ""),
                source="google_play_developer_subscriptions",
                checked_at=checked_at,
                platform="android",
                base_plan_id=str(base_plan.get("basePlanId", "") or ""),
            ))
    return result


def sync_store_pricing(
    stores_path: Path = DEFAULT_STORES,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    apple_token: str = "",
    google_token: str = "",
) -> dict[str, object]:
    checked_at = now_iso()
    stores = read_csv_rows(stores_path)
    products: list[dict[str, str]] = []
    states: list[dict[str, str]] = []
    for store in stores:
        platform = store.get("platform", "")
        status = store.get("status", "")
        state = {
            "app_id": store.get("app_id", ""),
            "app_slug": store.get("app_slug", ""),
            "platform": platform,
            "checked_at": checked_at,
            "state": "verified",
            "error": "",
        }
        if status in {"not_released", "in_review"}:
            state["state"] = status
            states.append(state)
            continue
        try:
            if platform == "ios":
                products.extend(apple_public_download_price(store, checked_at))
                if apple_token:
                    products.extend(apple_iap_prices(store, apple_token, checked_at))
                else:
                    state["state"] = "partial"
                    state["error"] = "apple_pricing_credentials_missing"
            elif platform == "android":
                products.extend(google_public_download_price(store, checked_at))
                if google_token:
                    products.extend(google_iap_prices(store, google_token, checked_at))
                else:
                    state["state"] = "partial"
                    state["error"] = "google_pricing_credentials_missing"
            else:
                state["state"] = "not_applicable"
        except urllib.error.HTTPError as error:
            state["state"] = "unavailable"
            state["error"] = f"store_pricing_http_{error.code}"
        except (StorePricingError, ValueError, OSError) as error:
            state["state"] = "unavailable"
            reason = str(error)
            state["error"] = reason if re.fullmatch(r"[a-z0-9_]{3,100}", reason) else "store_pricing_sync_failed"
        states.append(state)
    payload = {
        "schema_version": 1,
        "kind": "onnellab_store_pricing_snapshot",
        "checked_at": checked_at,
        "territory": TARGET_COUNTRY,
        "products": sorted(
            products,
            key=lambda row: (
                row["app_slug"], row["product_type"], row["product_id"],
                row["base_plan_id"], row["platform"],
            ),
        ),
        "stores": states,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    apple, google = _decode_credentials()
    payload = sync_store_pricing(
        args.stores,
        args.output,
        apple_token=apple,
        google_token=google,
    )
    incomplete = [
        s for s in payload["stores"]
        if s.get("state") in {"partial", "unavailable"}
    ]
    print(json.dumps({
        "status": "partial" if incomplete else "ok",
        "checked_at": payload["checked_at"],
        "territory": payload["territory"],
        "products": len(payload["products"]),
        "incomplete": len(incomplete),
    }, ensure_ascii=False))
    # A per-store price source can be unavailable while the durable snapshot is
    # still valid for every successfully verified product. Daily operations must
    # preserve those verified values and expose the incomplete store state rather
    # than blocking unrelated review/status/dashboard refreshes.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
