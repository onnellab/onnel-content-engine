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

    def test_invalid_decimal_fails_not_silent(self):
        with self.assertRaises(ValueError):
            amount("not money")


if __name__ == "__main__":
    unittest.main()
