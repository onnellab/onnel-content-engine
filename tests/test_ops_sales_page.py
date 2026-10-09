import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ops_sales_page import sales_page_body


class SalesPageTests(unittest.TestCase):
    def test_monthly_filters_country_and_fee_label(self):
        result = sales_page_body({
            "checked_at": "2026-10-09T00:00:00+00:00",
            "source_status": {"google": {"status": "ok"}, "apple": {"status": "vendor_number_required"}},
            "rows": [{
                "date": "2026-10-07", "platform": "android", "app_slug": "tagweaver",
                "app_name": "TagWeaver", "country": "KR", "currency": "KRW",
                "units": 1, "gross": "5500.00", "refund": "0.00", "fee": "825.00",
                "fee_confirmed": True,
            }],
        })
        self.assertIn('id="sales-month"', result)
        self.assertIn('id="sales-country"', result)
        self.assertIn("2026-10-07", result)
        self.assertIn("5500.00", result)
        self.assertIn("Vendor Number", result)
        self.assertIn("day>=range.start && day<=range.end", result)
        self.assertIn('id="sales-export"', result)
        self.assertIn('value="all"', result)
        self.assertIn('id="sales-period-mode"', result)
        self.assertIn('value="year"', result)
        self.assertIn('value="custom"', result)
        self.assertIn('id="sales-start"', result)
        self.assertIn('id="sales-total-net"', result)
        self.assertIn('id="sales-fx-data"', result)

    def test_supports_apple_monthly_settlements_without_inventing_fees(self):
        result = sales_page_body({"settlements": [{
            "fiscal_month": "2026-09", "app_slug": "tagweaver",
            "app_name": "TagWeaver", "country": "JP", "customer_currency": "JPY",
            "proceeds_currency": "JPY", "gross": "1000.00", "proceeds": "700.00",
            "fee": None, "fee_status": "commission_invoice_required",
        }], "source_status": {"apple_finance": {"status": "ok"}}})
        self.assertIn("2026-09", result)
        self.assertIn('id="settlement-body"', result)
        self.assertIn("별도 증빙 필요", result)
        self.assertIn('id="sales-settlements"', result)

    def test_grant_export_only_includes_verified_foreign_google_fees(self):
        from ops_sales_page import confirmed_foreign_fees
        base = {"date":"2026-09-17", "app_name":"TagWeaver", "app_slug":"tagweaver",
                "platform":"android", "fee_confirmed":True, "fee":"125.00",
                "currency":"KRW", "country":"JP", "sources":["google_earnings_actual"]}
        rows = [base, {**base,"country":"KR"},
                {**base,"country":"ZZ"}, {**base,"fee_confirmed":False},
                {**base,"platform":"ios"}]
        fees = confirmed_foreign_fees(rows)
        self.assertEqual(len(fees), 1)
        self.assertEqual(fees[0]["fee"],"125.00")
        self.assertIn('id="grant-fees-export"', sales_page_body({"rows":[base]}))

    def test_krw_conversions_and_selected_periods_are_in_sealed_payload(self):
        report = {
            "fx_status": {"status":"ok","source":"European Central Bank"},
            "rows": [{
                "date":"2026-09-10","platform":"android","app_slug":"tagweaver",
                "app_name":"TagWeaver","country":"US","currency":"USD",
                "units":1,"gross":"2.00","refund":"0.00","net_sales":"2.00",
                "gross_krw":"3000","refund_krw":"0","net_sales_krw":"3000",
                "fx_sales_rate":"1500","fx_sales_date":"2026-09-10",
                "fee_confirmed":False,
            }]
        }
        html = sales_page_body(report)
        for mode in ('month','year','custom','all'):
            self.assertIn(f'value="{mode}"', html)
        for id_name in ("sales-total-net","sales-total-gross","sales-total-fee",
                        "sales-start","sales-end","sales-currency-body","sales-fx-data"):
            self.assertIn(f'id="{id_name}"', html)
        self.assertIn('"net_sales_krw":"3000"', html)
        self.assertIn('"fx_sales_date":"2026-09-10"', html)
        self.assertIn('European Central Bank', html)

    def test_user_report_placeholder_stays_in_json_not_executed(self):
        html = sales_page_body({"rows":[{
            "date":"2026-10-01", "app_name":"__SALES_JS__ __STATE__"
        }]})
        self.assertIn('"app_name":"__SALES_JS__ __STATE__"', html)
        self.assertEqual(html.count("function selectedRange()"), 1)

    def test_no_html_injection_in_sales_data(self):
        result = sales_page_body({"rows": [{
            "date":"2026-10-01", "app_name": "</script><script>alert(1)</script>"
        }]})
        self.assertNotIn("</script><script>alert(1)", result)
        self.assertIn(r"\u003c/script>", result)

    def test_uncollected_does_not_claim_no_sales(self):
        html = sales_page_body(None)
        self.assertIn("보고서 미제공은 판매 0건을 뜻하지 않아요", html)
        self.assertIn("수집 전", html)


if __name__ == "__main__":
    unittest.main()
