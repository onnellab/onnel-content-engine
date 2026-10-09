"""Apple Finance monthly consolidated parser and incremental refresh tests."""
from __future__ import annotations
import gzip, io, sys, unittest, json
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from store_settlement import parse_finance, fetch_finance, merge_monthly, report_months

APPS={"6759609875":{"app_slug":"tagweaver","app_name":"TagWeaver"}}
HEAD=("Apple Identifier\tCountry of Sale\tQuantity\tExtended Partner Share\t"
      "Partner Share Currency\tCustomer Price\tCustomer Currency\tSale or Return\n")

class Response:
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return self.data

class FinanceTest(unittest.TestCase):
    def test_settled_sales_and_refunds_do_not_infer_apple_fee(self):
        rows=(HEAD+
              "6759609875\tJP\t2\t700.00\tJPY\t500\tJPY\tS\n"+
              "6759609875\tJP\t1\t350.00\tJPY\t500\tJPY\tR\n")
        result=parse_finance(gzip.compress(rows.encode()),"2026-09",APPS)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["units"],1)
        self.assertEqual(result[0]["proceeds"],"350.00")
        self.assertEqual(result[0]["gross"],"1000.00")
        self.assertEqual(result[0]["refund"],"-500.00")
        self.assertIsNone(result[0]["fee"])

    def test_currency_separation(self):
        data=(HEAD+"6759609875\tKR\t1\t3200.00\tKRW\t5500\tKRW\tS\n"
              "6759609875\tJP\t1\t4.00\tUSD\t600\tJPY\tS\n")
        result=parse_finance(data.encode(),"2026-09",APPS)
        self.assertEqual(len(result),2)
        self.assertEqual({r["proceeds_currency"] for r in result},{"USD","KRW"})

    def test_unknown_finance_app_reports_unmatched_rows_without_data_leaks(self):
        sample = (HEAD + "987654321\tJP\t1\t400\tJPY\t550\tJPY\tS\n").encode()
        stats = {}
        self.assertEqual(parse_finance(sample, "2026-09", APPS, stats), [])
        self.assertEqual(stats["rows_with_quantity"], 1)
        self.assertEqual(stats["unmatched_app_rows"], 1)

    def test_sku_alias_resolves_vendor_product(self):
        from store_settlement import add_app_sku_aliases
        payload = {"data":[{"id":"6759609875","attributes":{"sku":"ONNELLAB-TAG-WEAVER"}}],
                   "links":{"next":None}}
        def fake(request,timeout=30):
            return Response(json.dumps(payload).encode())
        aliases, result = add_app_sku_aliases("mock",APPS,opener=fake)
        self.assertEqual(result["sku_aliases"],1)
        self.assertEqual(aliases["ONNELLAB-TAG-WEAVER"]["app_slug"],"tagweaver")
        report=(HEAD.rstrip("\n")+"\tVendor Identifier\n"+
                "unknown\tJP\t1\t400\tJPY\t550\tJPY\tS\tONNELLAB-TAG-WEAVER\n")
        self.assertEqual(len(parse_finance(report.encode(),"2026-09",aliases)),1)

    def test_invalid_financial_headers_fail(self):
        with self.assertRaises(ValueError):
            parse_finance(b"unknown\tfoo\n1\t2\n","2026-09",APPS)

    def test_fiscal_months_exclude_unfinished_current_month(self):
        self.assertEqual(report_months(date(2026,8,1),date(2026,10,9)),
                         ["2026-08","2026-09"])

    def test_404_does_not_mean_zero_and_is_checkpointed(self):
        requests=[]
        def open_url(req,timeout=50):
            requests.append(req.full_url)
            raise HTTPError(req.full_url,404,"Missing",{},None)
        first,state=fetch_finance("test","vendor",APPS,date(2026,3,1),
                                  date(2026,10,9),opener=open_url)
        self.assertEqual(first,[])
        self.assertEqual(state["status"],"no_reports")
        self.assertEqual(len(requests),7)
        second,newstate=fetch_finance("test","vendor",APPS,date(2026,3,1),
                                     date(2026,10,9),previous=state,opener=open_url)
        self.assertEqual(len(requests),9)
        self.assertEqual(newstate["reports_missing"],7)

    def test_merge_replaces_refreshed_month_only(self):
        old=[{"fiscal_month":"2026-08","app_slug":"tagweaver","country":"KR","customer_currency":"KRW","proceeds_currency":"KRW","proceeds":"10"},
             {"fiscal_month":"2026-09","app_slug":"tagweaver","country":"KR","customer_currency":"KRW","proceeds_currency":"KRW","proceeds":"20"}]
        revised=[{**old[1],"proceeds":"30"}]
        result=merge_monthly(old,revised,["2026-09"])
        self.assertEqual([r["proceeds"] for r in result],["30","10"])

if __name__=="__main__":
    unittest.main()
