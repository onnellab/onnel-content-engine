"""Unit tests: real store report field semantics and money isolation."""
from __future__ import annotations

import gzip
import io
import os
import sys
import unittest
import zipfile
from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from store_sales_ledger import (
    aggregate, parse_google_sales_zip, parse_google_earnings_zip,
    parse_apple_sales, amount,
)

APPLE = {"6759609875": {"app_slug": "tagweaver", "app_name": "TagWeaver"}}
GOOGLE = {"com.onnellab.tagweaver2": {"app_slug": "tagweaver", "app_name": "TagWeaver"}}


def archive(data: str, name="report.csv") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as target:
        target.writestr(name, data)
    return output.getvalue()


class LedgerTests(unittest.TestCase):
    def test_google_estimated_sales_actual_columns_country_currency_refunds(self):
        raw = archive(
            "Package ID,Financial status,Order charged date,Order refunded date,"
            "Currency of Sale,Charged Amount,Country of Buyer\n"
            "com.onnellab.tagweaver2,Charged,2026-09-12,,KRW,\"5,500\",KR\n"
            "com.onnellab.tagweaver2,Refund,2026-09-12,2026-09-14,KRW,5500,KR\n"
            "com.other.app,Charged,2026-09-12,,USD,1.99,US\n"
        )
        rows = aggregate(parse_google_sales_zip(raw, GOOGLE))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], "2026-09-14")
        self.assertEqual(rows[0]["refund"], "-5500.00")
        self.assertEqual(rows[1]["date"], "2026-09-12")
        self.assertEqual(rows[1]["gross"], "5500.00")
        self.assertEqual(rows[1]["currency"], "KRW")
        self.assertEqual(rows[1]["country"], "KR")

    def test_google_earnings_actual_fee_only_and_reversal(self):
        raw = archive(
            "Package ID,Transaction Type,Transaction Date,Buyer Country,Merchant Currency,"
            "Amount (Merchant Currency)\n"
            "com.onnellab.tagweaver2,Google fee,\"Sep 12, 2026\",KR,KRW,-825.00\n"
            "com.onnellab.tagweaver2,Google fee refund,\"Sep 14, 2026\",KR,KRW,825.00\n"
            "com.onnellab.tagweaver2,Tax,\"Sep 12, 2026\",KR,KRW,-500.00\n"
        )
        rows = aggregate(parse_google_earnings_zip(raw, GOOGLE))
        self.assertEqual([(x["date"], x["fee"]) for x in rows],
                         [("2026-09-14", "-825.00"), ("2026-09-12", "825.00")])
        self.assertTrue(rows[0]["fee_confirmed"])

    def test_google_earnings_sale_currency_layout_partial_refund(self):
        raw = archive(
            "Package ID,Transaction Type,Transaction Date,Sale Country,Sale Currency,"
            "Amount Due (Sale Currency)\n"
            "com.onnellab.tagweaver2,Google fee,\"Oct 07, 2026\",JP,JPY,82.50\n"
            "com.onnellab.tagweaver2,Google fee partial refund,\"Oct 08, 2026\",JP,JPY,-22.50\n"
        )
        rows = aggregate(parse_google_earnings_zip(raw, GOOGLE))
        self.assertEqual([(r["date"],r["country"],r["currency"],r["fee"]) for r in rows],
                         [("2026-10-08","JP","JPY","-22.50"),
                          ("2026-10-07","JP","JPY","82.50")])

    def test_earnings_files_accept_merchant_suffix_and_adjustments(self):
        from store_sales_ledger import google_ledger
        sample = archive(
            "Package ID,Transaction Type,Transaction Date,Buyer Country,Merchant Currency,"
            "Amount (Merchant Currency)\n"
            "com.onnellab.tagweaver2,Google fee,\"Sep 12, 2026\",US,USD,-0.75\n"
        )
        objects = {
            "sales/": [],
            "earnings/": [
                {"name": "earnings/earnings_202609_abc-123.zip"},
                {"name": "earnings/earnings_202608.zip"},
                {"name": "earnings/unrecognized_202609.zip"},
            ],
        }
        def listed(bucket, prefix, token):
            return objects[prefix]
        app = {**GOOGLE["com.onnellab.tagweaver2"],
               "platform": "android", "store_package": "com.onnellab.tagweaver2"}
        with patch("store_sales_ledger.normalize_google_reports_bucket",
                   return_value="safe-bucket"), patch(
                   "store_sales_ledger.google_token_from_env",
                   return_value=("token","")), patch(
                   "store_sales_ledger.gcs_list_objects",
                   side_effect=listed), patch(
                   "store_sales_ledger.gcs_download", return_value=sample):
            rows, status = google_ledger([app], date(2026, 10, 9))
        self.assertEqual(status["earnings_files"], 2)
        self.assertEqual(status["earnings_objects_listed"], 3)
        self.assertEqual(status["earnings_unrecognized_files"], 1)
        self.assertEqual(status["earnings_months"], ["2026-08", "2026-09"])
        self.assertEqual(len(rows), 2)

    def test_google_corrected_reports_replace_stale_fees_and_sales(self):
        from store_sales_ledger import merge_sales_history
        previous = {
            "source_status":{"google":{
                "status":"ok","sales_months":["2026-08","2026-09"],
                "earnings_months":["2026-08","2026-09"]
            }},
            "rows":[
                {"date":"2026-09-12","platform":"android","app_slug":"tagweaver",
                 "country":"US","currency":"KRW","gross":"100","fee":"30"},
                {"date":"2026-09-13","platform":"android","app_slug":"tagweaver",
                 "country":"US","currency":"KRW","gross":"100","fee":"30"},
                {"date":"2026-09-14","platform":"ios","app_slug":"tagweaver",
                 "country":"US","currency":"USD","gross":"2.99"},
            ]
        }
        latest = {
            "source_status":{
                "google":{"status":"ok","sales_files":2,"earnings_files":2,
                          "sales_months":["2026-08","2026-09"],
                          "earnings_months":["2026-08","2026-09"]},
                "apple":{"refreshed_days":[]}
            },
            "rows":[
                {"date":"2026-09-12","platform":"android","app_slug":"tagweaver",
                 "country":"US","currency":"KRW","gross":"100","fee":"10"},
            ]
        }
        merged=merge_sales_history(latest,previous,date(2026,10,9))
        self.assertEqual(len(merged),2)
        google=[row for row in merged if row["platform"]=="android"]
        self.assertEqual(len(google),1)
        self.assertEqual(google[0]["fee"],"10")
        self.assertTrue(latest["source_status"]["google"]["snapshot_replaced"])

    def test_incomplete_google_report_does_not_erase_previous_expense(self):
        from store_sales_ledger import merge_sales_history
        previous={
            "source_status":{"google":{"status":"ok",
                "sales_months":["2026-08","2026-09"],
                "earnings_months":["2026-08","2026-09"]}},
            "rows":[{"date":"2026-09-12","platform":"android",
                     "app_slug":"tagweaver","country":"US","currency":"KRW",
                     "fee":"825"}]
        }
        latest={
            "source_status":{
                "google":{"status":"ok","sales_files":2,"earnings_files":1,
                          "sales_months":["2026-08","2026-09"],
                          "earnings_months":["2026-09"]},
                "apple":{"refreshed_days":[]}
            },
            "rows":[{"date":"2026-09-12","platform":"android",
                     "app_slug":"tagweaver","country":"US","currency":"KRW",
                     "fee":"0"}]
        }
        merged=merge_sales_history(latest,previous,date(2026,10,9))
        self.assertEqual(merged[0]["fee"],"825")
        self.assertEqual(latest["source_status"]["google"]["status"],"partial")
        self.assertTrue(latest["source_status"]["google"]["previous_snapshot_retained"])

    def test_google_complete_refresh_keeps_unaffected_apple_and_replaces_refresh(self):
        from store_sales_ledger import merge_sales_history
        previous={"source_status":{"google":{"status":"ok"}},
                  "rows":[{"date":"2026-09-12","platform":"ios",
                           "app_slug":"tagweaver","country":"US","currency":"USD",
                           "gross":"2.99"}]}
        latest={
            "source_status":{
                "google":{"status":"ok","sales_files":1,"earnings_files":1,
                          "sales_months":["2026-09"],
                          "earnings_months":["2026-09"]},
                "apple":{"refreshed_days":["2026-09-12"]}
            },
            "rows":[{"date":"2026-09-12","platform":"ios",
                     "app_slug":"tagweaver","country":"US","currency":"USD",
                     "gross":"4.99"}]
        }
        self.assertEqual(merge_sales_history(latest,previous,date(2026,10,9))[0]["gross"],
                         "4.99")

    def test_apple_daily_report_no_fee_inferred(self):
        fields = [
            "Apple Identifier", "Country Code", "Customer Currency", "Currency of Proceeds",
            "Customer Price", "Developer Proceeds", "Units",
        ]
        lines = [
            "\t".join(fields),
            "\t".join(["6759609875", "JP", "JPY", "JPY", "550", "400", "1"]),
            "\t".join(["6759609875", "JP", "JPY", "JPY", "-550", "400", "-1"]),
        ]
        raw = gzip.compress(("\n".join(lines) + "\n").encode())
        rows = aggregate(parse_apple_sales(raw, APPLE, "2026-09-08"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gross"], "550.00")
        self.assertEqual(rows[0]["refund"], "-550.00")
        self.assertEqual(rows[0]["proceeds"], "0.00")
        self.assertEqual(rows[0]["fee"], "0.00")
        self.assertFalse(rows[0]["fee_confirmed"])

    def test_ios_iap_product_id_resolves_using_parent_app_sku(self):
        # Real Apple reports identify an in-app purchase by its product Apple ID,
        # distinct from the public App Store application ID.
        headers = [
            "Apple Identifier", "Parent Identifier", "SKU", "Country Code",
            "Units", "Customer Price", "Customer Currency",
            "Currency of Proceeds", "Developer Proceeds",
        ]
        data = [
            headers,
            ["6761288417", "", "com.onnellab.tagweaver", "ES",
             "3", "3.99", "EUR", "EUR", "2.80"],
            ["6759609875", "", "", "US", "1", "2.99", "USD", "USD", "2.10"],
            ["999999999", "", "com.unknown.app", "JP", "2", "550", "JPY", "JPY", "400"],
        ]
        raw = gzip.compress(
            ("\n".join("\t".join(row) for row in data) + "\n").encode()
        )
        aliases = {**APPLE, "com.onnellab.tagweaver": APPLE["6759609875"]}
        stats = {}
        events = parse_apple_sales(raw, aliases, "2026-04-22", stats)
        self.assertEqual(len(events), 2)
        self.assertEqual(sum(row["units"] for row in events), 4)
        self.assertEqual(stats["matched_rows"], 2)
        self.assertEqual(stats["unmatched_rows"], 1)
        self.assertEqual(stats["paid_rows"], 2)
        self.assertEqual(stats["paid_units"], 4)
        self.assertEqual(sum(row["units"] for row in parse_apple_sales(
            raw, APPLE, "2026-04-22"
        )), 1)  # Previously the IAP SKU was dropped.

    def test_full_ledger_maps_ios_iap_sku_to_owner_app(self):
        from store_sales_ledger import build_ledger, APPLE_MAPPING_VERSION
        app = {**APPLE["6759609875"], "platform":"ios",
               "store_app_id":"6759609875"}
        daily = (
            "Apple Identifier\tSKU\tCountry Code\tUnits\tCustomer Price\t"
            "Customer Currency\tCurrency of Proceeds\tDeveloper Proceeds\n"
            "6761288417\tcom.onnellab.tagweaver\tES\t2\t3.99\tEUR\tEUR\t2.80\n"
        )
        aliases = {
            "6759609875":app, "com.onnellab.tagweaver":app
        }
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self): return gzip.compress(daily.encode())
        with patch.dict(os.environ, {"APP_STORE_VENDOR_NUMBER":"12345678"}), (
            patch("store_sales_ledger.read_csv_rows", return_value=[app])
        ), patch("store_sales_ledger.apple_sales_token", return_value="token"), (
            patch("store_sales_ledger.add_app_sku_aliases",
                  return_value=(aliases, {"status":"ok","sku_aliases":1}))
        ), patch("store_sales_ledger.fetch_finance",
                 return_value=([],{"status":"ok","refreshed_months":[]})), (
            patch("store_sales_ledger.urllib.request.urlopen",return_value=Response())
        ):
            result = build_ledger(date(2026,4,23), earliest=date(2026,4,22),
                                  google=False)
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["app_slug"], "tagweaver")
        self.assertEqual(result["rows"][0]["units"], 2)
        self.assertEqual(result["rows"][0]["gross"], "7.98")
        self.assertEqual(result["source_status"]["apple"]["app_mapping_version"],
                         APPLE_MAPPING_VERSION)
        self.assertEqual(result["source_status"]["apple"]["parser_rows"]["paid_units"], 2)

    def test_group_by_country_currency_no_cross_currency_total(self):
        raw = archive(
            "Package ID,Financial status,Order charged date,Currency of Sale,Charged Amount,Country of Buyer\n"
            "com.onnellab.tagweaver2,Charged,2026-09-12,KRW,5500,KR\n"
            "com.onnellab.tagweaver2,Charged,2026-09-12,JPY,550,JP\n"
        )
        rows = aggregate(parse_google_sales_zip(raw, GOOGLE))
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["currency"] for row in rows}, {"KRW", "JPY"})
        self.assertEqual(sum(int(x["units"]) for x in rows), 2)

    def test_apple_all_404_reports_are_not_reported_as_success(self):
        from store_sales_ledger import apple_ledger
        unavailable = HTTPError("https://example.com", 404, "Not Found", {}, None)
        with patch.dict(os.environ, {"APP_STORE_VENDOR_NUMBER": "12345678"}), (
            patch("store_sales_ledger.apple_sales_token", return_value="mock-token")
        ), patch("store_sales_ledger.urllib.request.urlopen", side_effect=unavailable):
            rows, status = apple_ledger(
                [{"platform": "ios", "store_app_id": "123", "app_slug": "test",
                  "app_name": "Test"}],
                date(2026, 10, 9), date(2026, 10, 7),
            )
        self.assertEqual(rows, [])
        self.assertEqual(status["status"], "no_reports")
        self.assertEqual(status["days_missing"], 2)
        self.assertEqual(status["days_checked"], 0)

    def test_apple_initial_backfill_starts_at_first_launch(self):
        from store_sales_ledger import apple_ledger
        requests = []
        missing = HTTPError("https://example.com", 404, "Missing", {}, None)
        def fetch(req, timeout=40):
            requests.append(req.full_url)
            raise missing
        with patch.dict(os.environ, {"APP_STORE_VENDOR_NUMBER": "12345678"}), (
            patch("store_sales_ledger.apple_sales_token", return_value="mock-token")
        ), patch("store_sales_ledger.urllib.request.urlopen", side_effect=fetch):
            _, state = apple_ledger([], date(2026, 3, 4), date(2026, 1, 1))
        self.assertEqual(len(requests), 3)
        self.assertTrue(all("2026-03-" in url for url in requests))
        self.assertEqual(state["days_missing"], 3)

    def test_new_ios_id_mapping_rechecks_previously_completed_months(self):
        from store_sales_ledger import apple_ledger, APPLE_MAPPING_VERSION
        previous = {
            "completed_days": ["2026-03-01"],
            "missing_days": ["2026-03-02"],
            # Old parser did not recognize in-app product IDs via parent SKU.
        }
        calls = []
        missing = HTTPError("https://example.com", 404, "Missing", {}, None)
        def fetch(req, timeout=40):
            calls.append(req.full_url)
            raise missing
        apple_app = {**APPLE["6759609875"], "store_app_id":"6759609875", "platform":"ios"}
        with patch.dict(os.environ, {"APP_STORE_VENDOR_NUMBER":"12345678"}), (
            patch("store_sales_ledger.apple_sales_token", return_value="test-token")
        ), patch("store_sales_ledger.urllib.request.urlopen", side_effect=fetch):
            events, state = apple_ledger(
                [apple_app], date(2026,3,20), date(2026,3,1),
                previous_status=previous, app_aliases={
                    "com.onnellab.tagweaver":apple_app
                }, sku_status={"status":"ok"},
            )
        self.assertEqual(events, [])
        self.assertEqual(len(calls), 19)
        self.assertTrue(state["rechecked_history"])
        self.assertEqual(state["sku_aliases"], 1)
        self.assertEqual(state["app_mapping_version"], APPLE_MAPPING_VERSION)
        self.assertEqual(state["days_missing"], 19)

    def test_apple_old_dates_not_redownloaded_after_backfill(self):
        from store_sales_ledger import apple_ledger
        previous = {"completed_days": ["2026-03-01"], "missing_days": ["2026-03-02"],
                    "app_mapping_version": 2}
        missing = HTTPError("https://example.com", 404, "Missing", {}, None)
        calls = []
        def fetch(req, timeout=40):
            calls.append(req.full_url)
            raise missing
        with patch.dict(os.environ, {"APP_STORE_VENDOR_NUMBER": "12345678"}), (
            patch("store_sales_ledger.apple_sales_token", return_value="mock-token")
        ), patch("store_sales_ledger.urllib.request.urlopen", side_effect=fetch):
            _, state = apple_ledger([], date(2026, 3, 20), date(2026, 3, 1),
                                     previous_status=previous)
        self.assertTrue(all("2026-03-01" not in url for url in calls))
        self.assertTrue(all("2026-03-02" not in url for url in calls))
        self.assertIn("2026-03-01", state["completed_days"])
        self.assertIn("2026-03-02", state["missing_days"])

    def test_finance_team_key_isolated_from_release_key(self):
        from store_sales_ledger import apple_sales_token
        credentials = {
            "APP_STORE_FINANCE_KEY_ID": "finance-key",
            "APP_STORE_FINANCE_ISSUER_ID": "finance-issuer",
            "APP_STORE_FINANCE_PRIVATE_KEY_BASE64": "cHJpdmF0ZSBrZXk=",
            "APP_STORE_CONNECT_KEY_ID": "release-key",
            "APP_STORE_CONNECT_ISSUER_ID": "release-issuer",
            "APP_STORE_CONNECT_PRIVATE_KEY_BASE64": "cHJpdmF0ZSBrZXk=",
        }
        with patch.dict(os.environ, credentials, clear=True), patch(
            "store_sales_ledger.app_store_connect_token", return_value="valid-token"
        ) as create:
            self.assertEqual(apple_sales_token(), "valid-token")
        create.assert_called_once_with(
            "finance-key", "finance-issuer", "private key", key_type="team"
        )

    def test_incomplete_finance_credentials_never_fall_back_silently(self):
        from store_sales_ledger import LedgerError, apple_sales_token
        with patch.dict(os.environ, {
            "APP_STORE_FINANCE_KEY_ID": "only-key-id",
        }, clear=True):
            with self.assertRaises(LedgerError):
                apple_sales_token()

    def test_invalid_decimal_fails_not_silent(self):
        with self.assertRaises(ValueError):
            amount("not money")


if __name__ == "__main__":
    unittest.main()
