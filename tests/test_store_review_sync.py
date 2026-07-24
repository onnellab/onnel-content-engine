from __future__ import annotations

import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_store_reviews import apple_review_rows, google_review_rows  # noqa: E402


STORE = {
    "app_id": "APP-0001",
    "app_slug": "quivra",
    "app_name": "Quivra",
}


class StoreReviewSyncTest(unittest.TestCase):
    def test_parses_apple_review_and_response(self) -> None:
        rows = apple_review_rows(
            {
                "data": [
                    {
                        "type": "customerReviews",
                        "id": "apple-1",
                        "attributes": {
                            "rating": 2,
                            "title": "Needs work",
                            "body": "The app crashed.",
                            "createdDate": "2026-07-20T10:00:00Z",
                            "reviewTerritory": "USA",
                        },
                    }
                ],
                "included": [
                    {
                        "type": "customerReviewResponses",
                        "id": "response-1",
                        "attributes": {
                            "responseBody": "We are investigating.",
                            "lastModifiedDate": "2026-07-21T10:00:00Z",
                        },
                        "relationships": {
                            "review": {
                                "data": {
                                    "type": "customerReviews",
                                    "id": "apple-1",
                                }
                            }
                        },
                    }
                ],
            },
            STORE,
            "2026-07-24T00:00:00Z",
        )

        self.assertEqual(rows[0]["platform"], "ios")
        self.assertEqual(rows[0]["developer_reply"], "We are investigating.")
        self.assertEqual(rows[0]["status"], "replied")

    def test_parses_google_title_body_and_language(self) -> None:
        rows = google_review_rows(
            {
                "reviews": [
                    {
                        "reviewId": "google-1",
                        "comments": [
                            {
                                "userComment": {
                                    "text": "변환 오류\t파일을 고르면 멈춰요.",
                                    "starRating": 1,
                                    "reviewerLanguage": "ko",
                                    "appVersionName": "1.0.6",
                                    "lastModified": {"seconds": "1784505600"},
                                }
                            }
                        ],
                    }
                ]
            },
            STORE,
            "2026-07-24T00:00:00Z",
        )

        self.assertEqual(rows[0]["platform"], "android")
        self.assertEqual(rows[0]["title"], "변환 오류")
        self.assertEqual(rows[0]["body"], "파일을 고르면 멈춰요.")
        self.assertEqual(rows[0]["reviewer_language"], "ko")
        self.assertEqual(rows[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
