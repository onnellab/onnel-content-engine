from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_manual_publish_site as dashboard


class StorePricingDashboardTest(unittest.TestCase):
    def test_live_prices_replace_manual_registry_per_platform(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apps = root / "apps.csv"
            prices = root / "app_pricing.csv"
            snapshot = root / "store_pricing_snapshot.json"
            apps.write_text(
                "app_id,app_name,slug,pricing_model,official_site_path,app_store_url,play_store_url\n"
                "APP-0002,TagWeaver,tagweaver,freemium,/apps/tagweaver/,https://apps.apple.com/app/id1,https://play.google.com/store/apps/details?id=com.tag\n",
                encoding="utf-8",
            )
            prices.write_text(
                "app_slug,product_name,product_type,price,currency,price_note\n"
                "tagweaver,TagWeaver Pro,pro,5500,KRW,Manual price registry\n",
                encoding="utf-8",
            )
            snapshot.write_text(json.dumps({
                "schema_version": 1,
                "kind": "onnellab_store_pricing_snapshot",
                "checked_at": "2026-09-24T00:00:00+00:00",
                "territory": "KR",
                "products": [
                    {
                        "app_slug": "tagweaver", "platform": "ios",
                        "product_type": "in_app_purchase", "product_id": "tagweaver_pro",
                        "product_name": "TagWeaver Pro", "price": "5500", "currency": "KRW",
                        "price_display": "₩5,500", "source": "app_store_connect_iap_price_schedule",
                        "checked_at": "2026-09-24T00:00:00+00:00",
                    },
                    {
                        "app_slug": "tagweaver", "platform": "android",
                        "product_type": "in_app_purchase", "product_id": "tagweaver_pro",
                        "product_name": "TagWeaver Pro", "price": "5500", "currency": "KRW",
                        "price_display": "", "source": "google_play_developer_inappproducts",
                        "checked_at": "2026-09-24T00:01:00+00:00",
                    },
                ],
                "stores": [],
            }), encoding="utf-8")
            rows = dashboard.product_pricing_items(
                homepage_repo=root / "homepage",
                apps_registry_path=apps,
                app_pricing_path=prices,
                store_pricing_snapshot_path=snapshot,
                ai_provider_pricing_path=root / "missing-ai.csv",
                melivra_ai_credit_policy_path=root / "missing-policy.csv",
            )
        tag = [row for row in rows if row["app_slug"] == "tagweaver"]
        self.assertEqual({row["platform"] for row in tag}, {"ios", "android"})
        self.assertTrue(all(row["price_verification"] == "live_store" for row in tag))
        self.assertEqual({row["price"] for row in tag}, {"₩5,500", "5,500 KRW"})

    def test_missing_live_platform_keeps_manual_fallback_with_blocker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apps = root / "apps.csv"
            prices = root / "app_pricing.csv"
            snapshot = root / "store_pricing_snapshot.json"
            apps.write_text(
                "app_id,app_name,slug,status,pricing_model,official_site_path,app_store_url,play_store_url\n"
                "APP-0002,TagWeaver,tagweaver,released,freemium,/apps/tagweaver/,https://apps.apple.com/app/id1,https://play.google.com/store/apps/details?id=com.tag\n",
                encoding="utf-8",
            )
            prices.write_text(
                "app_slug,product_name,product_type,price,currency,price_note\n"
                "tagweaver,TagWeaver Pro,pro,5500,KRW,Manual price registry\n",
                encoding="utf-8",
            )
            snapshot.write_text(json.dumps({
                "schema_version": 1,
                "kind": "onnellab_store_pricing_snapshot",
                "checked_at": "2026-09-24T00:00:00+00:00",
                "territory": "KR",
                "products": [{
                    "app_slug": "tagweaver", "platform": "ios",
                    "product_type": "in_app_purchase", "product_id": "tagweaver_pro",
                    "product_name": "TagWeaver Pro", "price": "5500", "currency": "KRW",
                    "source": "app_store_connect_iap_price_schedule",
                    "checked_at": "2026-09-24T00:00:00+00:00",
                }],
                "stores": [
                    {"app_slug": "tagweaver", "platform": "ios", "state": "verified",
                     "checked_at": "2026-09-24T00:00:00+00:00", "error": ""},
                    {"app_slug": "tagweaver", "platform": "android", "state": "unavailable",
                     "checked_at": "2026-09-24T00:01:00+00:00",
                     "error": "google_public_pricing_permission_denied",
                     "errors": ["google_public_pricing_permission_denied",
                                "google_catalog_pricing_permission_denied"]},
                ],
            }), encoding="utf-8")
            rows = dashboard.product_pricing_items(
                homepage_repo=root / "homepage",
                apps_registry_path=apps,
                app_pricing_path=prices,
                store_pricing_snapshot_path=snapshot,
                ai_provider_pricing_path=root / "missing-ai.csv",
                melivra_ai_credit_policy_path=root / "missing-policy.csv",
            )
        tag = [row for row in rows if row["app_slug"] == "tagweaver"]
        self.assertEqual({row["platform"] for row in tag}, {"ios", "android"})
        ios = next(row for row in tag if row["platform"] == "ios")
        android = next(row for row in tag if row["platform"] == "android")
        self.assertEqual(ios["price_verification"], "live_store")
        self.assertEqual(android["price_verification"], "manual_only")
        self.assertEqual(android["price"], "5,500 KRW")
        self.assertEqual(android["price_error"], "google_catalog_pricing_permission_denied")
        self.assertEqual(android["checked_at"], "2026-09-24T00:01:00+00:00")

    def test_manual_price_remains_when_no_safe_live_match(self):
        explicit = {"product_name": "TagWeaver Pro", "product_type": "pro"}
        live = [
            {
                "platform": "android", "product_type": "in_app_purchase",
                "product_name": "Premium Pack", "product_id": "premium_pack",
            }
        ]
        self.assertEqual(dashboard._select_live_price_rows(explicit, live), [])


if __name__ == "__main__":
    unittest.main()
