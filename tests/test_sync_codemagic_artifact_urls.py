from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from download_codemagic_artifacts import CODEMAGIC_HEADER  # noqa: E402
from sync_codemagic_artifact_urls import (  # noqa: E402
    CODEMAGIC_BUILDS_HEADER,
    CodemagicBuildSyncError,
    sync_codemagic_artifact_urls,
)
from validate_app_releases import RELEASE_HEADER  # noqa: E402


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def planned_release() -> dict[str, str]:
    row = {field: "" for field in RELEASE_HEADER}
    row.update(
        {
            "release_id": "REL-0001",
            "app_id": "APP-0003",
            "app_slug": "vaultxt",
            "app_name": "VaultXT",
            "repository": "onnellab/vaultxt",
            "tag": "v1.2.3",
            "version": "1.2.3",
            "platform": "ios",
            "build_type": "release",
            "status": "planned",
            "release_date": "2026-07-12",
            "release_title": "VaultXT v1.2.3",
            "summary": "VaultXT update.",
            "changes": "Update.",
            "compatibility": "ios public release.",
        }
    )
    return row


def build_row(artifact_name: str = "VaultXT.ipa") -> dict[str, str]:
    return {
        "release_id": "REL-0001",
        "codemagic_app_id": "codemagic-app",
        "workflow_id": "release",
        "build_id": "build-1",
        "artifact_name": artifact_name,
        "notes": "",
    }


class SyncCodemagicArtifactUrlsTest(unittest.TestCase):
    def test_empty_build_manifest_does_not_require_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            releases = root / "app_releases.csv"
            builds = root / "codemagic_builds.csv"
            artifacts = root / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(builds, CODEMAGIC_BUILDS_HEADER, [])
            write_csv(artifacts, CODEMAGIC_HEADER, [])

            with patch.dict("os.environ", {}, clear=True):
                synced = sync_codemagic_artifact_urls(releases, builds, artifacts)

            self.assertEqual(synced, [])

    def test_syncs_matching_artifact_url_from_build_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            releases = root / "app_releases.csv"
            builds = root / "codemagic_builds.csv"
            artifacts = root / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(builds, CODEMAGIC_BUILDS_HEADER, [build_row()])
            write_csv(artifacts, CODEMAGIC_HEADER, [])
            payload = {
                "build": {
                    "artifacts": [
                        {
                            "name": "VaultXT.ipa",
                            "url": "https://api.codemagic.io/artifacts/app/build/VaultXT.ipa",
                        }
                    ]
                }
            }

            with patch.dict("os.environ", {"CODEMAGIC_API_TOKEN": "token"}):
                with patch("sync_codemagic_artifact_urls.request_json", return_value=payload):
                    synced = sync_codemagic_artifact_urls(releases, builds, artifacts)

            self.assertEqual(len(synced), 1)
            rows = read_csv(artifacts)
            self.assertEqual(rows[0]["release_id"], "REL-0001")
            self.assertEqual(rows[0]["artifact_name"], "VaultXT.ipa")
            self.assertEqual(rows[0]["artifact_url"], "https://api.codemagic.io/artifacts/app/build/VaultXT.ipa")

    def test_multiple_artifacts_require_preferred_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            releases = root / "app_releases.csv"
            builds = root / "codemagic_builds.csv"
            artifacts = root / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(builds, CODEMAGIC_BUILDS_HEADER, [build_row("")])
            write_csv(artifacts, CODEMAGIC_HEADER, [])
            payload = {
                "artifacts": [
                    "https://api.codemagic.io/artifacts/app/build/VaultXT.ipa",
                    "https://api.codemagic.io/artifacts/app/build/VaultXT-symbols.ipa",
                ]
            }

            with patch.dict("os.environ", {"CODEMAGIC_API_TOKEN": "token"}):
                with patch("sync_codemagic_artifact_urls.request_json", return_value=payload):
                    with self.assertRaises(CodemagicBuildSyncError):
                        sync_codemagic_artifact_urls(releases, builds, artifacts)


if __name__ == "__main__":
    unittest.main()
