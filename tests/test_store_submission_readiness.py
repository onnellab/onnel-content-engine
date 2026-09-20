from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_store_submission_readiness as readiness  # noqa: E402
from validate_app_releases import RELEASE_HEADER  # noqa: E402


def release(release_id: str, app_id: str, version: str, platform: str = "ios", channel: str = "public") -> dict[str, str]:
    row = {field: "" for field in RELEASE_HEADER}
    row.update({"release_id": release_id, "app_id": app_id, "app_slug": app_id.lower(), "app_name": app_id,
                "repository": "onnellab/example", "tag": f"v{version}", "version": version,
                "platform": platform, "build_type": "release", "release_type": "binary",
                "release_channel": channel, "status": "planned"})
    return row


class StoreSubmissionReadinessTest(unittest.TestCase):
    def test_exact_public_versions_are_already_available_and_private_is_excluded(self) -> None:
        rows = [release("REL-1", "APP-1", "1.2.3"), release("REL-2", "APP-2", "1.2.4", channel="private_test")]
        snapshots = [{"app_id": "APP-1", "platform": "ios", "status": "unchanged", "checked_at": "2026-09-20T09:00:00+09:00", "store_url": "https://apps.apple.com/app/id1", "version": "1.2.3", "notes": ""}]
        result = self.run_readiness(rows, snapshots)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "already_available")
        self.assertEqual(result[0]["public_store_snapshot"]["version"], "1.2.3")
        self.assertTrue(result[0]["reasons"])

    def test_newer_candidate_stays_blocked(self) -> None:
        result = self.run_readiness([release("REL-1", "APP-1", "1.2.4")], [{
            "app_id": "APP-1", "platform": "ios", "status": "updated", "checked_at": "now",
            "store_url": "https://apps.apple.com/app/id1", "version": "1.2.3", "notes": "",
        }])
        self.assertEqual(result[0]["status"], "blocked")

    def test_non_numeric_or_prerelease_versions_are_not_public_evidence(self) -> None:
        self.assertEqual(readiness.numeric_version("error 1.2"), ())
        self.assertEqual(readiness.numeric_version("1.2-beta"), ())
        self.assertEqual(readiness.numeric_version("1.2.3"), (1, 2, 3))

    def test_untrusted_or_missing_snapshots_stay_blocked(self) -> None:
        rows = [release("REL-failed", "APP-1", "1.0.0"), release("REL-not", "APP-2", "1.0.0"), release("REL-review", "APP-3", "1.0.0"), release("REL-empty", "APP-4", "1.0.0"), release("REL-android", "APP-5", "1.0.0", "android")]
        snapshots = [
            {"app_id": "APP-1", "platform": "ios", "status": "failed", "checked_at": "now", "store_url": "https://apps.apple.com/app/id1", "version": "1.0.0"},
            {"app_id": "APP-2", "platform": "ios", "status": "not_released", "checked_at": "now", "store_url": "https://apps.apple.com/app/id2", "version": "1.0.0"},
            {"app_id": "APP-3", "platform": "ios", "status": "in_review", "checked_at": "now", "store_url": "https://apps.apple.com/app/id3", "version": "1.0.0"},
            {"app_id": "APP-4", "platform": "ios", "status": "unchanged", "checked_at": "now", "store_url": "https://apps.apple.com/app/id4", "version": ""},
            {"app_id": "APP-5", "platform": "android", "status": "unchanged", "checked_at": "now", "store_url": "https://play.google.com/store/apps/details?id=x", "version": "1.0.0", "notes": "used fallback snapshot; public lookup unavailable"},
        ]
        result = self.run_readiness(rows, snapshots)
        self.assertEqual([item["status"] for item in result], ["blocked"] * len(rows))

    def run_readiness(self, rows: list[dict[str, str]], snapshots: list[dict[str, str]]) -> list[dict[str, object]]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            with (data / "app_releases.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=RELEASE_HEADER, lineterminator="\n")
                writer.writeheader(); writer.writerows(rows)
            (data / "store_submission_config.json").write_text(json.dumps({"app_store": {"enabled": False}, "google_play": {"enabled": False}}), encoding="utf-8")
            (data / "store_submission_approvals.json").write_text('{"approvals": []}', encoding="utf-8")
            with (data / "store_versions.csv").open("w", encoding="utf-8", newline="") as handle:
                fields = ["app_id", "app_slug", "app_name", "platform", "store_url", "store_app_id", "store_package", "version", "last_updated", "release_notes", "checked_at", "status", "notes"]
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader(); writer.writerows(snapshots)
            with patch.object(readiness, "ROOT", root), patch.object(readiness, "RELEASES_PATH", data / "app_releases.csv"), patch.object(readiness, "validate_app_releases", return_value=None):
                self.assertEqual(readiness.main(), 0)
            return json.loads((data / "store_submission_readiness.json").read_text(encoding="utf-8"))["records"]


if __name__ == "__main__":
    unittest.main()
