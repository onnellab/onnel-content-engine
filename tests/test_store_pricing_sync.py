from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_store_pricing as pricing


class StorePricingSyncTest(unittest.TestCase):
    def test_parses_google_micros(self):
        self.assertEqual(
            pricing._micros_price({"priceMicros": "5500000000", "currency": "KRW"}),
            ("5500", "KRW"),
        )

    def test_reads_google_public_paid_download(self):
        store = {
            "app_id": "APP-0001",
            "app_slug": "quivra",
            "app_name": "Quivra",
            "store_url": "https://play.google.com/store/apps/details?id=com.onnellab.quivra2",
            "store_package": "com.onnellab.quivra2",
        }
        with patch.object(
            pricing,
            "_html_get",
            return_value='<html>com.onnellab.quivra2<span itemprop="price" content="₩3,300"></span></html>',
        ):
            rows = pricing.google_public_download_price(store, "2026-09-24T00:00:00+00:00")
        self.assertEqual(rows[0]["price"], "3300")
        self.assertEqual(rows[0]["currency"], "KRW")
        self.assertEqual(rows[0]["source"], "google_play_public_page")

    def test_ignores_google_public_zero_price_for_free_download(self):
        store = {
            "app_id": "APP-0002",
            "app_slug": "tagweaver",
            "app_name": "TagWeaver",
            "store_url": "https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2",
            "store_package": "com.onnellab.tagweaver2",
        }
        with patch.object(
            pricing,
            "_html_get",
            return_value='<html>com.onnellab.tagweaver2<span itemprop="price" content="0"></span></html>',
        ):
            self.assertEqual(
                pricing.google_public_download_price(store, "2026-09-24T00:00:00+00:00"),
                [],
            )

    def test_chooses_current_apple_price_from_schedule(self):
        rows = [
            {
                "type": "inAppPurchasePrices",
                "id": "old",
                "attributes": {"startDate": "2026-01-01", "endDate": "2026-08-31", "manual": True},
                "relationships": {
                    "inAppPurchasePricePoint": {"data": {"type": "inAppPurchasePricePoints", "id": "p1"}},
                    "territory": {"data": {"type": "territories", "id": "KOR"}},
                },
            },
            {
                "type": "inAppPurchasePrices",
                "id": "current",
                "attributes": {"startDate": "2026-09-01", "endDate": None, "manual": True},
                "relationships": {
                    "inAppPurchasePricePoint": {"data": {"type": "inAppPurchasePricePoints", "id": "p2"}},
                    "territory": {"data": {"type": "territories", "id": "KOR"}},
                },
            },
        ]
        included = [
            {
                "type": "inAppPurchasePricePoints",
                "id": "p1",
                "attributes": {"customerPrice": "4400"},
                "relationships": {"territory": {"data": {"type": "territories", "id": "KOR"}}},
            },
            {
                "type": "inAppPurchasePricePoints",
                "id": "p2",
                "attributes": {"customerPrice": "5500"},
                "relationships": {"territory": {"data": {"type": "territories", "id": "KOR"}}},
            },
            {"type": "territories", "id": "KOR", "attributes": {"currency": "KRW"}},
        ]
        with patch.object(pricing, "date") as mocked_date:
            mocked_date.today.return_value.isoformat.return_value = "2026-09-24"
            self.assertEqual(
                pricing._current_price_from_apple_rows(
                    rows,
                    included,
                    price_point_type="inAppPurchasePricePoints",
                    price_point_relation="inAppPurchasePricePoint",
                ),
                ("5500", "KRW"),
            )

    def test_google_catalog_403_has_specific_safe_error(self):
        error = __import__("urllib.error").error.HTTPError(
            "https://example.test", 403, "Forbidden", {}, None
        )
        self.assertEqual(
            pricing._source_error("android", "catalog_pricing", error),
            "google_catalog_pricing_permission_denied",
        )

    def test_reads_google_iap_and_subscription_prices(self):
        store = {
            "app_id": "APP-0002",
            "app_slug": "tagweaver",
            "app_name": "TagWeaver",
            "store_package": "com.onnellab.tagweaver2",
        }
        products = [{
            "sku": "tagweaver_pro",
            "status": "active",
            "purchaseType": "managedUser",
            "prices": {"KR": {"priceMicros": "5500000000", "currency": "KRW"}},
            "listings": {"ko-KR": {"title": "TagWeaver Pro"}},
        }]
        subscriptions = [{
            "productId": "tagweaver_plus",
            "listings": [{"languageCode": "ko-KR", "title": "TagWeaver Plus"}],
            "basePlans": [{
                "basePlanId": "monthly",
                "state": "ACTIVE",
                "regionalConfigs": [{
                    "regionCode": "KR",
                    "price": {"priceMicros": "1200000000", "currency": "KRW"},
                }],
            }],
        }]
        with patch.object(pricing, "_google_paged", side_effect=[products, subscriptions]):
            rows = pricing.google_iap_prices(store, "token", "2026-09-24T00:00:00+00:00")
        self.assertEqual([(r["product_type"], r["price"]) for r in rows], [
            ("in_app_purchase", "5500"),
            ("subscription", "1200"),
        ])

    def test_sync_retains_partial_state_without_catalog_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            stores = Path(temp) / "stores.csv"
            app_prices = Path(temp) / "app_pricing.csv"
            output = Path(temp) / "snapshot.json"
            stores.write_text(
                "app_id,app_slug,app_name,platform,store_url,store_app_id,store_package,version,last_updated,release_notes,checked_at,status,notes\n"
                "APP-0002,tagweaver,TagWeaver,ios,https://apps.apple.com/app/id123,123,,1.0,,,2026-09-24,unchanged,\n",
                encoding="utf-8",
            )
            app_prices.write_text(
                "app_slug,product_name,product_type,price,currency,price_note\n"
                "tagweaver,TagWeaver Pro,pro,5500,KRW,Manual price registry\n",
                encoding="utf-8",
            )
            with patch.object(pricing, "apple_public_download_price", return_value=[]):
                payload = pricing.sync_store_pricing(
                    stores, output, pricing_path=app_prices
                )
            self.assertEqual(payload["stores"][0]["state"], "partial")
            self.assertEqual(
                payload["stores"][0]["error"],
                "apple_catalog_pricing_credentials_missing",
            )
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text())["schema_version"], 1)

    def test_catalog_success_after_public_failure_is_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            stores = Path(temp) / "stores.csv"
            app_prices = Path(temp) / "app_pricing.csv"
            output = Path(temp) / "snapshot.json"
            stores.write_text(
                "app_id,app_slug,app_name,platform,store_url,store_app_id,store_package,version,last_updated,release_notes,checked_at,status,notes\n"
                "APP-0002,tagweaver,TagWeaver,android,https://play.google.com/store/apps/details?id=com.tag,,com.tag,1.0,,,2026-09-24,unchanged,\n",
                encoding="utf-8",
            )
            app_prices.write_text(
                "app_slug,product_name,product_type,price,currency,price_note\n"
                "tagweaver,TagWeaver Pro,pro,5500,KRW,Manual price registry\n",
                encoding="utf-8",
            )
            live_product = {
                "app_slug": "tagweaver",
                "platform": "android",
                "product_type": "in_app_purchase",
                "product_id": "tagweaver_pro",
                "base_plan_id": "",
                "price": "5500",
            }
            with patch.object(
                pricing,
                "google_public_download_price",
                side_effect=pricing.StorePricingError("google_public_price_page_mismatch"),
            ), patch.object(pricing, "google_iap_prices", return_value=[live_product]):
                payload = pricing.sync_store_pricing(
                    stores,
                    output,
                    pricing_path=app_prices,
                    google_token="token",
                )
            self.assertEqual(payload["stores"][0]["state"], "partial")
            self.assertEqual(payload["stores"][0]["error"], "google_public_price_page_mismatch")
            self.assertEqual(payload["products"], [live_product])

    def test_paid_download_only_does_not_require_catalog_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            stores = Path(temp) / "stores.csv"
            app_prices = Path(temp) / "app_pricing.csv"
            output = Path(temp) / "snapshot.json"
            stores.write_text(
                "app_id,app_slug,app_name,platform,store_url,store_app_id,store_package,version,last_updated,release_notes,checked_at,status,notes\n"
                "APP-0001,quivra,Quivra,android,https://play.google.com/store/apps/details?id=com.quivra,,com.quivra,1.0,,,2026-09-24,unchanged,\n",
                encoding="utf-8",
            )
            app_prices.write_text(
                "app_slug,product_name,product_type,price,currency,price_note\n"
                "quivra,Paid download,paid_download,3300,KRW,Manual price registry\n",
                encoding="utf-8",
            )
            with patch.object(pricing, "google_public_download_price", return_value=[]):
                payload = pricing.sync_store_pricing(
                    stores, output, pricing_path=app_prices
                )
            self.assertEqual(payload["stores"][0]["state"], "verified")
            self.assertEqual(payload["stores"][0]["error"], "")


if __name__ == "__main__":
    unittest.main()
