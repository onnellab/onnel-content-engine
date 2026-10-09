"""Historical ECB exchange-rate integration with private store finance snapshots."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
from store_fx_rates import parse_ecb_xml, quote, won, enrich_ledger, fetch_nbp_quotes, nbp_cross_quote

XML = b"""<Envelope><Cube><Cube time="2026-10-08">
<Cube currency="USD" rate="1.2"/><Cube currency="KRW" rate="1800"/>
<Cube currency="JPY" rate="180"/></Cube>
<Cube time="2026-10-09"><Cube currency="USD" rate="1.25"/>
<Cube currency="KRW" rate="1750"/></Cube></Cube></Envelope>"""


class FxReferenceTests(unittest.TestCase):
    def test_ecb_cross_conversion_and_weekend_uses_prior_date(self):
        history = parse_ecb_xml(XML)
        result = quote("2026-10-10","USD",history)
        self.assertEqual(result["rate"],"1400")
        self.assertEqual(result["as_of"],"2026-10-09")
        self.assertEqual(won("2.99",result["rate"]),"4186")

    def test_older_rate_not_silently_used_for_uncovered_date(self):
        history=parse_ecb_xml(XML)
        self.assertIsNone(quote("2026-10-20","USD",history))
        self.assertIsNone(quote("2026-10-08","GBP",history))

    def test_nbu_cross_reference_covers_sar_and_uah_without_guessing(self):
        calls=[]
        def nbu(day):
            calls.append(day)
            return {
                "UAH":Decimal("1"),"KRW":Decimal("0.033488"),
                "SAR":Decimal("11.9499"),
            },day
        original=[
            {"date":"2026-10-08","currency":"SAR","gross":"10",
             "refund":"0","net_sales":"10","fee_confirmed":False},
            {"date":"2026-10-08","currency":"UAH","gross":"100",
             "refund":"0","net_sales":"100","fee_confirmed":False},
        ]
        result=enrich_ledger({"rows":original,"settlements":[]},
                             history=parse_ecb_xml(XML),nbu_loader=nbu)
        self.assertEqual(calls,["2026-10-08"])
        self.assertEqual(result["fx_status"]["missing_sales_rows"],0)
        self.assertEqual(result["fx_status"]["nbu_fallback_date_count"],1)
        self.assertEqual(result["rows"][0]["fx_sales_source"],"NBU")
        self.assertEqual(result["rows"][1]["fx_sales_source"],"NBU")
        self.assertEqual(result["rows"][0]["net_sales_krw"],
                         won("10",Decimal("11.9499")/Decimal("0.033488")))
        self.assertEqual(result["rows"][1]["net_sales_krw"],
                         won("100",Decimal("1")/Decimal("0.033488")))

    def test_clp_nbp_fallback_restores_net_apple_proceeds(self):
        calls = []
        def nbu(day):
            return {"KRW":Decimal("0.033"), "UAH":Decimal("1")}, day
        def nbp(day):
            calls.append(day)
            return {"CLP":Decimal("0.00395"), "KRW":Decimal("0.00285")}, day
        rows = [
            {"date":"2026-09-23","currency":"CLP","gross":"2990",
             "refund":"0","net_sales":"2990","units":1,
             "proceeds":"1759","proceeds_currency":"CLP"},
            {"date":"2026-09-23","currency":"CLP","gross":"0",
             "refund":"-2990","net_sales":"-2990","units":-1,
             "proceeds":"-1759","proceeds_currency":"CLP"},
        ]
        ledger={"rows":rows,"settlements":[]}
        result=enrich_ledger(ledger,history=parse_ecb_xml(XML),
                             nbu_loader=nbu,nbp_loader=nbp)
        self.assertEqual(calls,["2026-09-23"])
        self.assertEqual(result["fx_status"]["missing_sales_rows"],0)
        self.assertEqual(result["fx_status"]["nbp_fallback_date_count"],1)
        self.assertEqual(result["rows"][0]["fx_sales_source"],"NBP")
        self.assertEqual(result["rows"][0]["net_sales_krw"],
                         str(int(result["rows"][0]["gross_krw"])))
        self.assertEqual(Decimal(result["rows"][0]["net_sales_krw"]) +
                         Decimal(result["rows"][1]["net_sales_krw"]),Decimal(0))

    def test_nbp_rates_use_one_published_date_for_both_currencies(self):
        import json
        from unittest.mock import patch
        from io import BytesIO
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,*args):
                return json.dumps([{"effectiveDate":"2026-09-23",
                    "rates":[{"code":"CLP","mid":0.00395},
                             {"code":"KRW","mid":0.00285}]}]).encode()
        with patch("store_fx_rates.urllib.request.urlopen",return_value=Response()):
            rates,as_of=fetch_nbp_quotes("2026-09-24")
        q=nbp_cross_quote("2026-09-24","CLP",rates,as_of)
        self.assertEqual(q["as_of"],"2026-09-23")
        self.assertEqual(q["source"],"NBP")
        self.assertEqual(Decimal(q["rate"]),Decimal("0.00395")/Decimal("0.00285"))

    def test_sales_refunds_confirmed_fees_apple_proceeds_are_independent(self):
        src={
            "date":"2026-10-08","currency":"USD",
            "gross":"2.99","refund":"-0.99","net_sales":"2.00",
            "fee":"0.45","fee_confirmed":True,
            "proceeds":"1.3","proceeds_currency":"EUR"
        }
        settlement={
            "fiscal_month":"2026-09","currency":"",
            "proceeds_currency":"KRW","proceeds":"4000",
            "customer_currency":"USD","gross":"4.99",
        }
        ledger={"rows":[src],"settlements":[settlement]}
        enriched=enrich_ledger(deepcopy(ledger),history=parse_ecb_xml(XML),
                               nbu_loader=lambda day: ({"KRW":Decimal("1")}, day))
        row=enriched["rows"][0]
        self.assertEqual(row["gross_krw"],"4485")
        self.assertEqual(row["refund_krw"],"-1485")
        self.assertEqual(row["net_sales_krw"],"3000")
        self.assertEqual(row["fee_krw"],"675")
        self.assertEqual(row["proceeds_krw"],"2340")
        self.assertEqual(enriched["fx_status"]["missing_sales_rows"],0)
        self.assertEqual(enriched["settlements"][0]["proceeds_krw"],"4000")

    def test_missing_rate_marked_missing_not_fabricated_zero(self):
        row={"date":"2026-10-08","currency":"XYZ","gross":"10.00",
             "refund":"0","net_sales":"10.00","fee_confirmed":False}
        ledger={"rows":[row],"settlements":[]}
        result=enrich_ledger(ledger,history=parse_ecb_xml(XML),
                             nbu_loader=lambda day: ({"KRW":Decimal("1")}, day))
        self.assertNotIn("net_sales_krw",result["rows"][0])
        self.assertEqual(result["fx_status"]["missing_sales_rows"],1)
        self.assertEqual(result["fx_status"]["missing_currency_counts"],{"XYZ":1})

    def test_cached_previous_reference_rate_when_ecb_down(self):
        record={"rows":[{"date":"2026-10-08","currency":"USD","gross":"1",
                         "refund":"0","net_sales":"1"}],"settlements":[]}
        prior={"fx_rates":{"2026-10-08|USD":{"rate":"1500","as_of":"2026-10-08"}}}
        def down():
            raise OSError("network not available")
        result=enrich_ledger(record, previous=prior, fetcher=down)
        self.assertEqual(result["rows"][0]["net_sales_krw"],"1500")
        self.assertEqual(result["fx_status"]["status"],"unavailable")
        self.assertEqual(result["fx_status"]["missing_sales_rows"],0)

    def test_unconfirmed_fee_never_convert_as_confirmed(self):
        record={"rows":[{"date":"2026-10-09","currency":"KRW","gross":"5500",
                         "refund":"0","net_sales":"5500","fee":"999",
                         "fee_confirmed":False}],"settlements":[]}
        result=enrich_ledger(record,history={})
        self.assertNotIn("fee_krw",result["rows"][0])
        self.assertEqual(result["rows"][0]["net_sales_krw"],"5500")


if __name__=="__main__":
    unittest.main()
