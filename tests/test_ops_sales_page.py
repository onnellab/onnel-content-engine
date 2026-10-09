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
        self.assertIn("r.date<=today", result)
        self.assertIn('id="sales-export"', result)

    def test_no_html_injection_in_sales_data(self):
        result = sales_page_body({"rows": [{
            "date":"2026-10-01", "app_name": "</script><script>alert(1)</script>"
        }]})
        self.assertNotIn("</script><script>alert(1)", result)
        self.assertIn(r"\u003c/script>", result)

    def test_uncollected_does_not_claim_no_sales(self):
        html = sales_page_body(None)
        self.assertIn("아직 수집 중일 수도 있어요", html)
        self.assertIn("수집 전", html)


if __name__ == "__main__":
    unittest.main()
