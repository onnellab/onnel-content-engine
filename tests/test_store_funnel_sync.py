from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_store_funnel import (
    aggregate_apple_rows,
    apple_report_request,
    apple_request_body,
    build_summary,
    merge_daily_metrics,
    parse_google_sales_zip,
    parse_google_store_performance,
    recent_months,
    sync_apple,
)


APP = {
    "app_id": "APP-0002",
    "app_name": "TagWeaver",
    "slug": "tagweaver",
}


class StoreFunnelSyncTest(unittest.TestCase):
    def test_apple_reports_map_to_funnel_metrics(self):
        discovery = [
            {"Date": "2026-10-01", "Event": "Impression", "Page Type": "No page", "Counts": "120"},
            {"Date": "2026-10-01", "Event": "Page view", "Page Type": "Product page", "Counts": "30"},
            {"Date": "2026-10-01", "Event": "Page view", "Page Type": "In-app event", "Counts": "9"},
        ]
        downloads = [
            {"Date": "2026-10-01", "Download Type": "First-time Download", "Counts": "8"},
            {"Date": "2026-10-01", "Download Type": "Redownload", "Counts": "4"},
        ]
        purchases = [
            {"Date": "2026-10-01", "Purchases": "3"},
            {"Date": "2026-10-01", "Purchases": "-1"},
        ]

        rows = []
        rows += aggregate_apple_rows("discovery", discovery, APP, "now")
        rows += aggregate_apple_rows("downloads", downloads, APP, "now")
        rows += aggregate_apple_rows("purchases", purchases, APP, "now")
        values = {row["metric"]: row["value"] for row in rows}

        self.assertEqual(values["impressions"], 120)
        self.assertEqual(values["store_visitors"], 30)
        self.assertEqual(values["installs"], 8)
        self.assertEqual(values["purchases"], 2)

    def test_apple_snapshot_request_body_uses_one_time_snapshot(self):
        body = apple_request_body("123456789", "ONE_TIME_SNAPSHOT")
        self.assertEqual(
            body["data"]["attributes"]["accessType"],
            "ONE_TIME_SNAPSHOT",
        )

    def test_apple_snapshot_request_is_created_when_missing(self):
        with patch(
            "sync_store_funnel.json_request",
            side_effect=[
                {"data": []},
                {"data": {"id": "snapshot-request-id"}},
            ],
        ) as request:
            request_id, status = apple_report_request(
                "123456789", "token", "ONE_TIME_SNAPSHOT"
            )
        self.assertEqual(request_id, "snapshot-request-id")
        self.assertEqual(status, "created")
        self.assertEqual(
            request.call_args_list[1].kwargs["body"]["data"]["attributes"]["accessType"],
            "ONE_TIME_SNAPSHOT",
        )

    def test_apple_newer_instance_replaces_existing_metric_instead_of_adding(self):
        existing = [
            {
                "date": "2026-09-15",
                "app_slug": "tagweaver",
                "platform": "ios",
                "metric": "installs",
                "value": "5",
                "source": "apple_ongoing_downloads",
            }
        ]
        additions = [
            {
                "date": "2026-09-15",
                "app_slug": "tagweaver",
                "platform": "ios",
                "metric": "installs",
                "value": 7,
                "source": "apple_snapshot_downloads",
                "checked_at": "now",
                "_processing_date": "2026-10-08",
            }
        ]
        merged = merge_daily_metrics(
            existing,
            additions,
            [],
            {"status": "not_configured"},
            "now",
        )
        row = next(item for item in merged if item["platform"] == "ios")
        self.assertEqual(int(row["value"]), 7)
        self.assertNotIn("_processing_date", row)

    def test_sync_apple_requests_snapshot_and_ongoing_when_reports_are_pending(self):
        stores = [
            {
                "platform": "ios",
                "store_app_id": "123456789",
                "app_slug": "tagweaver",
            }
        ]
        state = {"schema_version": 1, "apple_processed_instances": []}
        with (
            patch(
                "sync_store_funnel.apple_report_request",
                side_effect=[
                    ("snapshot-id", "created"),
                    ("ongoing-id", "active"),
                ],
            ) as request,
            patch("sync_store_funnel.apple_reports", return_value={}),
        ):
            additions, status = sync_apple(
                [APP], stores, "token", state, "now"
            )
        self.assertEqual(additions, [])
        self.assertEqual(status["tagweaver"]["status"], "waiting_for_snapshot")
        self.assertEqual(
            status["tagweaver"]["snapshot_request_id"], "snapshot-id"
        )
        self.assertEqual(
            [call.args[2] for call in request.call_args_list],
            ["ONE_TIME_SNAPSHOT", "ONGOING"],
        )
        self.assertEqual(
            state["apple_snapshot_requests"]["tagweaver"],
            "snapshot-id",
        )

    def test_sync_apple_waits_when_report_definitions_have_no_instances(self):
        stores = [
            {
                "platform": "ios",
                "store_app_id": "123456789",
                "app_slug": "tagweaver",
            }
        ]
        state = {"schema_version": 1, "apple_processed_instances": []}
        with (
            patch(
                "sync_store_funnel.apple_report_request",
                side_effect=[
                    ("snapshot-id", "existing"),
                    ("ongoing-id", "active"),
                ],
            ),
            patch(
                "sync_store_funnel.apple_reports",
                return_value={"downloads": "report-id"},
            ),
            patch("sync_store_funnel.apple_daily_instances", return_value=[]),
        ):
            additions, status = sync_apple(
                [APP], stores, "token", state, "now"
            )
        self.assertEqual(additions, [])
        self.assertEqual(status["tagweaver"]["status"], "waiting_for_snapshot")
        self.assertEqual(
            status["tagweaver"]["requests"]["snapshot"]["status"],
            "waiting_for_report",
        )

    def test_sync_apple_keeps_latest_processing_date_across_snapshot_and_ongoing(self):
        stores = [
            {
                "platform": "ios",
                "store_app_id": "123456789",
                "app_slug": "tagweaver",
            }
        ]
        state = {"schema_version": 1, "apple_processed_instances": []}

        def reports(request_id: str, _token: str):
            return {"downloads": f"{request_id}-downloads"}

        def instances(report_id: str, _token: str):
            if report_id.startswith("snapshot"):
                return [
                    {
                        "id": "snapshot-instance",
                        "attributes": {"processingDate": "2026-10-07"},
                    }
                ]
            return [
                {
                    "id": "ongoing-instance",
                    "attributes": {"processingDate": "2026-10-08"},
                }
            ]

        def rows(instance_id: str, _token: str):
            count = "5" if instance_id == "snapshot-instance" else "7"
            return [
                {
                    "Date": "2026-09-15",
                    "Download Type": "First-time Download",
                    "Counts": count,
                }
            ]

        with (
            patch(
                "sync_store_funnel.apple_report_request",
                side_effect=[
                    ("snapshot-id", "existing"),
                    ("ongoing-id", "active"),
                ],
            ),
            patch("sync_store_funnel.apple_reports", side_effect=reports),
            patch("sync_store_funnel.apple_daily_instances", side_effect=instances),
            patch("sync_store_funnel.apple_instance_rows", side_effect=rows),
        ):
            additions, status = sync_apple(
                [APP], stores, "token", state, "now"
            )

        self.assertEqual(status["tagweaver"]["status"], "ok")
        installs = [
            row for row in additions
            if row["date"] == "2026-09-15" and row["metric"] == "installs"
        ]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0]["value"], 7)
        self.assertEqual(installs[0]["source"], "apple_ongoing_downloads")

    def test_google_store_performance_country_rows_aggregate_without_double_dimensions(self):
        raw = (
            "Date,Package name,Country,Store listing acquisitions,Store listing visitors,Store listing conversion rate\n"
            "2026-10-01,com.onnellab.tagweaver2,US,4,20,0.2\n"
            "2026-10-01,com.onnellab.tagweaver2,KR,3,10,0.3\n"
        ).encode()
        rows = parse_google_store_performance(
            raw, APP, "com.onnellab.tagweaver2", "now"
        )
        values = {row["metric"]: row["value"] for row in rows}
        self.assertEqual(values["store_visitors"], 30)
        self.assertEqual(values["installs"], 7)

    def test_google_estimated_sales_counts_charges_net_of_full_refunds(self):
        csv_text = (
            "Order number,Order charged date,Financial status,Package ID,Product type\n"
            "GPA.1,2026-10-01,Charged,com.onnellab.tagweaver2,one-time product\n"
            "GPA.2,2026-10-01,Charged,com.onnellab.tagweaver2,one-time product\n"
            "GPA.2,2026-10-02,Refund,com.onnellab.tagweaver2,one-time product\n"
            "GPA.3,2026-10-02,Partial refund,com.onnellab.tagweaver2,one-time product\n"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("salesreport.csv", csv_text)
        rows = parse_google_sales_zip(
            buffer.getvalue(),
            {"com.onnellab.tagweaver2": APP},
            "now",
        )
        by_date = {row["date"]: row["value"] for row in rows}
        self.assertEqual(by_date["2026-10-01"], 2)
        self.assertEqual(by_date["2026-10-02"], -1)

    def test_google_refresh_replaces_recent_month_metrics_but_preserves_apple(self):
        existing = [
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "android", "metric": "installs", "value": "99", "source": "google_store_performance"},
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "ios", "metric": "installs", "value": "5", "source": "apple_downloads"},
        ]
        google = [
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "android", "metric": "installs", "value": 7, "source": "google_store_performance", "checked_at": "now"},
        ]
        merged = merge_daily_metrics(
            existing,
            [],
            google,
            {"status": "ok", "store_performance_objects": 1, "financial": {"status": "permission_required"}},
            "now",
        )
        values = {(row["platform"], row["metric"]): int(row["value"]) for row in merged}
        self.assertEqual(values[("android", "installs")], 7)
        self.assertEqual(values[("ios", "installs")], 5)

    def test_summary_keeps_incomparable_visitor_counts_separate(self):
        rows = [
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "ios", "metric": "store_visitors", "value": 10},
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "ios", "metric": "installs", "value": 3},
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "android", "metric": "store_visitors", "value": 20},
            {"date": "2026-10-01", "app_slug": "tagweaver", "platform": "android", "metric": "installs", "value": 4},
        ]
        summary = build_summary(
            [APP],
            rows,
            "now",
            {"apple": {"status": "ok"}, "google": {"status": "ok"}},
            today=date(2026, 10, 7),
        )
        app = summary["apps"]["tagweaver"]
        self.assertEqual(app["platforms"]["ios"]["windows"]["7"]["store_visitors"], 10)
        self.assertEqual(app["platforms"]["android"]["windows"]["7"]["store_visitors"], 20)
        self.assertIsNone(app["combined"]["7"]["store_visitors"])
        self.assertEqual(app["combined"]["7"]["installs"], 7)
        self.assertIsNone(summary["metric_semantics"]["combined_visitors"])

    def test_recent_months_is_stable_across_year_boundary(self):
        self.assertEqual(
            recent_months(4, date(2026, 1, 2)),
            {"202601", "202512", "202511", "202510"},
        )


if __name__ == "__main__":
    unittest.main()
