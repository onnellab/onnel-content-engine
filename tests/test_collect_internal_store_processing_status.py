from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_internal_store_processing_status import (
    android_version_code,
    apple_processing_status,
    collect,
    google_processing_status,
)


class FakeResponse:
    def __init__(self, payload: dict | None = None) -> None:
        self.body = json.dumps(payload).encode() if payload is not None else b""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body


class QueueOpener:
    def __init__(self, responses: list[dict | None | Exception]) -> None:
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout: int):
        self.calls.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


class InternalStoreProcessingStatusTest(unittest.TestCase):
    def test_google_reads_exact_version_and_deletes_temporary_edit(self) -> None:
        opener = QueueOpener(
            [
                {"id": "edit-1"},
                {"releases": [{"versionCodes": ["51"], "status": "draft"}, {"versionCodes": ["52"], "status": "completed"}]},
                None,
            ]
        )

        result = google_processing_status("com.onnellab.vaultxt", "52", "token", opener=opener)

        self.assertEqual(result["processing_status"], "processed")
        self.assertEqual(result["provider_status"], "completed")
        self.assertEqual([call[0].method for call in opener.calls], ["POST", "GET", "DELETE"])
        self.assertNotIn("commit", " ".join(call[0].full_url for call in opener.calls))

    def test_google_deletes_temporary_edit_when_track_lookup_fails(self) -> None:
        opener = QueueOpener([{"id": "edit-2"}, ValueError("bad response"), None])

        with self.assertRaisesRegex(ValueError, "bad response"):
            google_processing_status("com.onnellab.vaultxt", "52", "token", opener=opener)

        self.assertEqual([call[0].method for call in opener.calls], ["POST", "GET", "DELETE"])

    def test_apple_matches_release_and_recent_upload(self) -> None:
        opener = QueueOpener(
            [
                {"data": [{"id": "bundle-resource"}]},
                {
                    "included": [
                        {"type": "preReleaseVersions", "id": "pre-old", "attributes": {"version": "1.0.5"}},
                        {"type": "preReleaseVersions", "id": "pre-new", "attributes": {"version": "1.0.6"}},
                    ],
                    "data": [
                        {
                            "type": "builds",
                            "id": "build-old-version",
                            "attributes": {"version": "51", "processingState": "VALID", "uploadedDate": "2026-07-28T09:10:00Z"},
                            "relationships": {"preReleaseVersion": {"data": {"id": "pre-old"}}},
                        },
                        {
                            "type": "builds",
                            "id": "build-52",
                            "attributes": {"version": "52", "processingState": "PROCESSING", "uploadedDate": "2026-07-28T09:05:00Z"},
                            "relationships": {"preReleaseVersion": {"data": {"id": "pre-new"}}},
                        },
                    ],
                },
            ]
        )

        result = apple_processing_status(
            "com.onnellab.vaultxt",
            "1.0.6",
            "2026-07-28T09:00:00+00:00",
            "token",
            opener=opener,
        )

        self.assertEqual(result["processing_status"], "processing")
        self.assertEqual(result["store_build_id"], "build-52")
        self.assertEqual(result["build_number"], "52")
        self.assertTrue(all(call[0].method == "GET" for call in opener.calls))

    def test_apple_does_not_match_an_old_build_with_the_same_version(self) -> None:
        opener = QueueOpener(
            [
                {"data": [{"id": "bundle-resource"}]},
                {
                    "included": [{"type": "preReleaseVersions", "id": "pre", "attributes": {"version": "1.0.6"}}],
                    "data": [
                        {
                            "id": "stale-build",
                            "attributes": {"version": "51", "processingState": "VALID", "uploadedDate": "2026-07-27T01:00:00Z"},
                            "relationships": {"preReleaseVersion": {"data": {"id": "pre"}}},
                        }
                    ],
                },
            ]
        )

        result = apple_processing_status(
            "com.onnellab.vaultxt",
            "1.0.6",
            "2026-07-28T09:00:00+00:00",
            "token",
            opener=opener,
        )

        self.assertEqual(result["processing_status"], "not_found")

    def test_android_version_code_uses_exact_package_and_version(self) -> None:
        code = android_version_code(
            {"identifier": "com.onnellab.vaultxt"},
            {"version": "1.0.6"},
            [
                {"package": "com.onnellab.vaultxt", "version": "1.0.5", "notes": "version 1.0.5+51"},
                {"package": "com.onnellab.vaultxt", "version": "1.0.6", "notes": "Imported version 1.0.6+52"},
            ],
        )

        self.assertEqual(code, "52")

    def test_collect_preserves_history_and_skips_human_confirmed_builds(self) -> None:
        submissions = [
            {
                "release_id": "REL-1",
                "provider": "google_play",
                "identifier": "com.example.one",
                "channel": "internal",
                "checksum_sha256": "a" * 64,
                "status": "uploaded",
                "uploaded_at": "2026-07-28T09:00:00+00:00",
                "build_number": "7",
            },
            {
                "release_id": "REL-2",
                "provider": "google_play",
                "identifier": "com.example.two",
                "status": "uploaded",
            },
        ]
        records: list[dict] = []
        releases = [{"release_id": "REL-1", "version": "1.2.3"}, {"release_id": "REL-2", "version": "2.0.0"}]
        observed = {
            "processing_status": "processing",
            "provider_status": "inProgress",
            "store_build_id": "7",
            "source_url": "https://androidpublisher.googleapis.com/example",
        }
        with patch("collect_internal_store_processing_status.google_processing_status", return_value=observed) as lookup:
            collect(
                submissions,
                releases,
                [],
                {"REL-2"},
                records,
                google_token="token",
                apple_token="",
                now="2026-07-28T10:00:00+00:00",
            )
            collect(
                submissions,
                releases,
                [],
                {"REL-2"},
                records,
                google_token="token",
                apple_token="",
                now="2026-07-28T11:00:00+00:00",
            )

        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]["history"]), 1)
        self.assertEqual(records[0]["last_checked_at"], "2026-07-28T11:00:00+00:00")

    def test_workflow_is_collection_only_and_scheduled(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "sync-internal-store-processing-status.yml").read_text()

        self.assertIn('cron: "17 * * * *"', workflow)
        self.assertIn("collect_internal_store_processing_status.py", workflow)
        self.assertIn("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", workflow)
        self.assertIn("APP_STORE_CONNECT_PRIVATE_KEY", workflow)
        self.assertIn("data/internal_store_processing_status.json", workflow)
        self.assertNotIn("fastlane supply", workflow)
        self.assertNotIn("fastlane pilot upload", workflow)


if __name__ == "__main__":
    unittest.main()
