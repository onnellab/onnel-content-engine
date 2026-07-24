from __future__ import annotations

import unittest
import base64
import json

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_store_reviews import (  # noqa: E402
    app_store_connect_token,
    apple_review_rows,
    der_signature_to_raw,
    fetch_apple_review_pages,
    fetch_google_review_pages,
    google_report_review_rows,
    google_service_account_assertion,
    google_review_rows,
)


STORE = {
    "app_id": "APP-0001",
    "app_slug": "quivra",
    "app_name": "Quivra",
}


class StoreReviewSyncTest(unittest.TestCase):
    def test_builds_short_lived_app_store_connect_jwt(self) -> None:
        r = bytes.fromhex("01" * 32)
        s = bytes.fromhex("80" + "02" * 31)
        der = b"\x30\x45\x02\x20" + r + b"\x02\x21\x00" + s
        calls: list[tuple[bytes, str]] = []

        def signer(signing_input: bytes, private_key: str) -> bytes:
            calls.append((signing_input, private_key))
            return der

        token = app_store_connect_token(
            "KEY123",
            "issuer-123",
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            issued_at=1_800_000_000,
            signer=signer,
        )
        header_segment, payload_segment, signature_segment = token.split(".")

        def decode(segment: str) -> bytes:
            return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))

        self.assertEqual(json.loads(decode(header_segment)), {"alg": "ES256", "kid": "KEY123", "typ": "JWT"})
        payload = json.loads(decode(payload_segment))
        self.assertEqual(payload["aud"], "appstoreconnect-v1")
        self.assertEqual(payload["exp"] - payload["iat"], 19 * 60)
        self.assertEqual(len(decode(signature_segment)), 64)
        self.assertEqual(calls[0][0], f"{header_segment}.{payload_segment}".encode("ascii"))

    def test_converts_der_ecdsa_signature_to_raw(self) -> None:
        der = b"\x30\x06\x02\x01\x01\x02\x01\x02"
        raw = der_signature_to_raw(der)
        self.assertEqual(raw[:32], b"\x00" * 31 + b"\x01")
        self.assertEqual(raw[32:], b"\x00" * 31 + b"\x02")

    def test_builds_google_androidpublisher_service_account_assertion(self) -> None:
        calls: list[tuple[bytes, str]] = []

        def signer(signing_input: bytes, private_key: str) -> bytes:
            calls.append((signing_input, private_key))
            return b"rsa-signature"

        token = google_service_account_assertion(
            {
                "client_email": "reviews@example.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            },
            issued_at=1_800_000_000,
            signer=signer,
        )
        header_segment, payload_segment, signature_segment = token.split(".")

        def decode(segment: str) -> bytes:
            return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))

        self.assertEqual(json.loads(decode(header_segment)), {"alg": "RS256", "typ": "JWT"})
        payload = json.loads(decode(payload_segment))
        self.assertIn("https://www.googleapis.com/auth/androidpublisher", payload["scope"])
        self.assertIn("https://www.googleapis.com/auth/devstorage.read_only", payload["scope"])
        self.assertEqual(payload["aud"], "https://oauth2.googleapis.com/token")
        self.assertEqual(payload["exp"] - payload["iat"], 60 * 60)
        self.assertEqual(decode(signature_segment), b"rsa-signature")
        self.assertEqual(calls[0][0], f"{header_segment}.{payload_segment}".encode("ascii"))

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

    def test_fetches_every_apple_review_page(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _token: str) -> dict[str, object]:
            calls.append(url)
            if len(calls) == 1:
                return {
                    "data": [{"id": "apple-1"}],
                    "included": [{"id": "reply-1"}],
                    "links": {"next": "https://apple.example/reviews?cursor=next"},
                }
            return {"data": [{"id": "apple-2"}], "included": [], "links": {}}

        payload = fetch_apple_review_pages("https://apple.example/reviews", "token", fetcher=fetcher)

        self.assertEqual([item["id"] for item in payload["data"]], ["apple-1", "apple-2"])
        self.assertEqual([item["id"] for item in payload["included"]], ["reply-1"])
        self.assertEqual(len(calls), 2)

    def test_fetches_every_google_review_page(self) -> None:
        calls: list[str] = []

        def fetcher(url: str, _token: str) -> dict[str, object]:
            calls.append(url)
            if len(calls) == 1:
                return {
                    "reviews": [{"reviewId": "google-1"}],
                    "tokenPagination": {"nextPageToken": "page two"},
                }
            return {"reviews": [{"reviewId": "google-2"}]}

        payload = fetch_google_review_pages(
            "https://google.example/reviews?maxResults=200",
            "token",
            fetcher=fetcher,
        )

        self.assertEqual([item["reviewId"] for item in payload["reviews"]], ["google-1", "google-2"])
        self.assertIn("token=page+two", calls[1])

    def test_reads_google_lifetime_review_report(self) -> None:
        report = (
            "Package Name,App Version Code,App Version Name,Reviewer Language,Review Submit Date and Time,"
            "Review Submit Millis Since Epoch,Review Last Update Date and Time,"
            "Review Last Update Millis Since Epoch,Star Rating,Review Title,Review Text,"
            "Developer Reply Date and Time,Developer Reply Millis Since Epoch,Developer Reply Text,Review Link\n"
            "com.onnellab.quivra2,77,1.0.6,ko,2026-01-02T03:04:05Z,1767323045000,"
            "2026-01-02T03:04:05Z,1767323045000,5,좋아요,잘 사용하고 있어요.,,,,https://example/#ReviewPlace:id=review-77\n"
        ).encode("utf-8")

        rows = google_report_review_rows(
            "gs://pubsite_prod_rev_123",
            {**STORE, "store_package": "com.onnellab.quivra2"},
            "token",
            "2026-07-24T00:00:00Z",
            json_fetcher=lambda _url, _token: {
                "items": [{"name": "reviews/reviews_com.onnellab.quivra2_202601.csv"}]
            },
            bytes_fetcher=lambda _url, _token: report,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_id"], "review-77")
        self.assertEqual(rows[0]["platform"], "android")
        self.assertEqual(rows[0]["body"], "잘 사용하고 있어요.")


if __name__ == "__main__":
    unittest.main()
