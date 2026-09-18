from __future__ import annotations
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_manual_publish_site import store_review_items, store_review_sync_status_item, html_document

class DashboardReviewStatusTest(unittest.TestCase):
    def test_snapshot_checksum_detects_mismatched_status(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"store_reviews.csv";p.write_text("review_id,body\na,review\n")
            status=p.with_name("store_review_sync_status.json")
            status.write_text(json.dumps({"snapshot_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"stores":[]}))
            self.assertTrue(store_review_sync_status_item(p)["snapshot_matches"])
            p.write_text("review_id,body\nb,new review\n")
            self.assertFalse(store_review_sync_status_item(p)["snapshot_matches"])

    def test_real_ids_are_not_merged_by_equal_content(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"store_reviews.csv"
            p.write_text("review_id,app_id,app_slug,platform,rating,body,created_at,verified_at\na,APP-1,app,android,5,great,2026-01-01,2026-09-18\nb,APP-1,app,android,5,great,2026-01-01,2026-09-18\n")
            items=store_review_items(p)
            self.assertEqual(len(items),2)
            self.assertTrue(all(x["verified_at"]=="2026-09-18" for x in items))

    def test_dashboard_embeds_and_refreshes_coverage(self):
        html=html_document([],store_review_sync_status={"snapshot_matches":True,"historical_records":2,"stores":[{"app_slug":"vaultxt","state":"verified","current_reviews":2}]})
        self.assertIn('id="store-review-sync-data"',html)
        self.assertIn("storeReviewSyncStatus = readEmbeddedJson(doc, 'store-review-sync-data')",html)
        self.assertIn("state.current_reviews",html)
        self.assertIn("storeReviewCountBasis",html)
        self.assertIn("snapshot_matches === true",html)

    def test_no_verification_claim_without_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(store_review_sync_status_item(Path(d)/"missing.csv"),{})

if __name__ == '__main__': unittest.main()
