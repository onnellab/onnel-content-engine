from __future__ import annotations
import csv
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_store_reviews as s

STORE = {"app_id":"APP-1", "app_slug":"app", "app_name":"App", "platform":"android", "store_package":"com.example.app"}
STAMP = "2026-09-18T12:00:00+00:00"

def row(rid, **kw):
    return {"review_id":rid, "app_id":"APP-1", "app_slug":"app", "app_name":"App", "platform":"android", "rating":"1", "title":"", "body":"old", "created_at":"2026-03-01T00:00:00Z", "updated_at":"2026-03-01T00:00:00Z", "developer_reply":"old reply", "status":"replied", **kw}

def payload(rid, body="current", reply="new reply", rating=5):
    comments=[{"userComment":{"text":body,"starRating":rating,"lastModified":{"seconds":"1789732800"},"reviewerLanguage":"pt"}}]
    if reply: comments.append({"developerComment":{"text":reply,"lastModified":{"seconds":"1789732900"}}})
    return {"reviewId":rid,"comments":comments}

class ReconciliationTest(unittest.TestCase):
    def check(self, prior, reports, responses, archive=None):
        def fetch(url, token):
            item = responses[url.rsplit("/",1)[1]]
            if isinstance(item,int): raise urllib.error.HTTPError(url,item,"test",{},None)
            return item
        return s.reconcile_google_current_reviews(STORE,prior,reports,[],"token",STAMP,archive or [],fetcher=fetch)

    def test_old_reviews_refreshed_even_when_recent_list_empty(self):
        current, history = self.check([row("keep"),row("gone")],[row("keep")],{"keep":payload("keep"),"gone":404})
        self.assertEqual([r["review_id"] for r in current],["keep"])
        self.assertEqual(current[0]["developer_reply"],"new reply")
        self.assertEqual(current[0]["rating"],"5")
        self.assertEqual(current[0]["verified_at"],STAMP)
        self.assertEqual(history[0]["reason"],"store_not_found")

    def test_report_aliases_do_not_duplicate_edited_review(self):
        report=row("real",_report_alias="report-current",body="updated")
        current,history=self.check([row("real"),row("report-current",body="updated"),row("report-old",body="first version")],[report],{"real":payload("real","updated")})
        self.assertEqual(len(current),1)
        self.assertEqual(current[0]["created_at"],report["created_at"])
        reasons={e["review"]["review_id"]:e["reason"] for e in history}
        self.assertEqual(reasons,{"report-current":"superseded_alias","report-old":"unverified_report_history"})

    def test_missing_from_reports_does_not_mean_deleted(self):
        current,history=self.check([row("old-real")],[],{"old-real":payload("old-real")})
        self.assertEqual(len(current),1)
        self.assertEqual(history,[])

    def test_removed_developer_reply_is_not_resurrected(self):
        current,_=self.check([row("r")],[row("r")],{"r":payload("r",reply="")})
        self.assertEqual(current[0]["developer_reply"],"")
        self.assertEqual(current[0]["status"],"pending")

    def test_unrelated_real_ids_with_same_text_remain_distinct(self):
        current,_=self.check([],[row("a"),row("b")],{"a":payload("a"),"b":payload("b")})
        self.assertEqual(len(current),2)

    def test_reappearing_archived_review_is_restored(self):
        archive=[{"review":row("r"),"reason":"store_not_found","checked_at":"old"}]
        current,_=self.check([],[],{"r":payload("r")},archive)
        self.assertEqual([r["review_id"] for r in current],["r"])

    def test_auth_errors_are_not_deletions(self):
        for code in [401,403,429,500]:
            with self.subTest(code=code),self.assertRaises(urllib.error.HTTPError):
                self.check([row("r")],[],{"r":code})

    def test_wrong_id_and_malformed_comment_fail_closed(self):
        for value in [payload("different"),{"reviewId":"r","comments":[]}]:
            with self.assertRaises(s.StoreReviewSyncError): self.check([row("r")],[],{"r":value})

    def test_modern_report_id_and_legacy_override_are_retained(self):
        keys=["Package Name","Star Rating","Review Title","Review Text","Review Submit Millis Since Epoch","Review Link"]
        source={"Package Name":"com.example.app","Star Rating":"5","Review Title":"","Review Text":"Tageditor","Review Submit Millis Since Epoch":"123","Review Link":"https://play.google.com/console/reviews?reviewId=real-id&corpus=PUBLIC_REVIEWS"}
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=keys);writer.writeheader();writer.writerow(source)
        rows=s.google_report_review_rows("pubsite_prod_123",STORE,"token",STAMP,json_fetcher=lambda *_:{"items":[{"name":"reviews/reviews_com.example.app_202601.csv"}]},bytes_fetcher=lambda *_:buf.getvalue().encode())
        self.assertEqual(rows[0]["review_id"],"real-id")
        self.assertEqual(rows[0]["_report_alias"],s.google_report_fallback_id("com.example.app",source))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"overrides.json";path.write_text(json.dumps({"reviews":{rows[0]["_report_alias"]:{"review_kind":"rating_only"}}}))
            self.assertEqual(s.apply_review_overrides(rows,path)[0]["review_kind"],"rating_only")

    def test_malformed_report_rejected(self):
        with self.assertRaises(s.StoreReviewSyncError):
            s.google_report_review_rows("pubsite_prod_123",STORE,"token",STAMP,json_fetcher=lambda *_:{"items":[{"name":"r.csv"}]},bytes_fetcher=lambda *_:b"bad,columns\n1,2\n")

    def test_partial_google_fixture_preserves_older_records(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stores=root/"stores.csv";out=root/"reviews.csv";fixtures=root/"fixtures";fixtures.mkdir()
            self.write_stores(stores);s.write_csv_rows(out,[row("old")]);(fixtures/"app.json").write_text('{"reviews":[]}')
            s.sync_reviews(stores_path=stores,output_path=out,google_json_dir=fixtures)
            self.assertEqual(s.read_csv_rows(out)[0]["review_id"],"old")
            self.assertEqual(json.loads((root/"store_review_sync_status.json").read_text())["stores"][0]["state"],"partial")

    def write_stores(self,path):
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(STORE));w.writeheader();w.writerow(STORE)

    def test_whole_snapshot_unchanged_on_error(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stores=root/"stores.csv";out=root/"reviews.csv";self.write_stores(stores);s.write_csv_rows(out,[row("r")])
            archive=root/"store_reviews_archive.json";status=root/"store_review_sync_status.json"
            archive.write_text('{"records":[]}');status.write_text('{"checked_at":"before"}')
            before=[p.read_bytes() for p in (out,archive,status)]
            with patch.object(s,"google_report_review_rows",return_value=[]),patch.object(s,"fetch_google_review_pages",return_value={"reviews":[]}),patch.object(s,"fetch_json",side_effect=urllib.error.HTTPError("https://google.test",503,"unavailable",{},None)):
                with self.assertRaises(urllib.error.HTTPError): s.sync_reviews(stores_path=stores,output_path=out,google_token="token",google_reports_bucket="pubsite_prod_123",require_google_history=True)
            self.assertEqual(before,[p.read_bytes() for p in (out,archive,status)])

    def test_full_snapshot_is_idempotent_and_auditable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stores=root/"stores.csv";out=root/"reviews.csv";self.write_stores(stores);s.write_csv_rows(out,[row("gone"),row("report-a")])
            report=row("a",_report_alias="report-a")
            def fetch(url,token):
                if url.endswith('/gone'): raise urllib.error.HTTPError(url,404,"missing",{},None)
                return payload("a")
            with patch.object(s,"now_iso",return_value=STAMP),patch.object(s,"google_report_review_rows",return_value=[report]),patch.object(s,"fetch_google_review_pages",return_value={"reviews":[]}),patch.object(s,"fetch_json",side_effect=fetch):
                for _ in range(2): s.sync_reviews(stores_path=stores,output_path=out,google_token="token",google_reports_bucket="pubsite_prod_123",require_google_history=True)
            self.assertEqual([r["review_id"] for r in s.read_csv_rows(out)],["a"])
            records=json.loads((root/"store_reviews_archive.json").read_text())["records"]
            self.assertEqual(len(records),2)
            status=json.loads((root/"store_review_sync_status.json").read_text())
            self.assertEqual(status["stores"][0]["current_reviews"],1)
            self.assertEqual(len(status["snapshot_sha256"]),64)

    def test_complete_apple_list_archives_absent_review(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stores=root/"stores.csv";out=root/"reviews.csv"
            stores.write_text('app_id,app_slug,app_name,platform,store_app_id\nAPP-1,app,App,ios,123\n')
            s.write_csv_rows(out,[row("gone",platform="ios")])
            with patch.object(s,"fetch_apple_review_pages",return_value={"data":[],"included":[]}): s.sync_reviews(stores_path=stores,output_path=out,apple_token="token")
            self.assertEqual(s.read_csv_rows(out),[])
            self.assertEqual(json.loads((root/"store_reviews_archive.json").read_text())["records"][0]["reason"],"not_in_complete_apple_list")

if __name__ == '__main__': unittest.main()
