from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from download_codemagic_artifacts import (  # noqa: E402
    CODEMAGIC_HEADER,
    CodemagicArtifactError,
    download_codemagic_artifacts,
)
from validate_app_releases import RELEASE_HEADER  # noqa: E402


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def planned_release() -> dict[str, str]:
    row = {field: "" for field in RELEASE_HEADER}
    row.update(
        {
            "release_id": "REL-0001",
            "app_id": "APP-0003",
            "app_slug": "vaultxt",
            "app_name": "VaultXT",
            "repository": "onnelakin/vaultxt",
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


def artifact_row(name: str = "VaultXT.ipa") -> dict[str, str]:
    return {
        "release_id": "REL-0001",
        "app_id": "APP-0003",
        "app_slug": "vaultxt",
        "version": "1.2.3",
        "platform": "ios",
        "artifact_url": "/artifacts/build/app/VaultXT.ipa",
        "artifact_name": name,
        "notes": "",
    }


class DownloadCodemagicArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(lambda: shutil.rmtree(ROOT / "generated" / "releases" / "vaultxt", ignore_errors=True))

    def test_dry_run_does_not_require_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            artifacts = Path(temp) / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(artifacts, CODEMAGIC_HEADER, [artifact_row()])

            downloaded = download_codemagic_artifacts(releases, artifacts, dry_run=True)

            self.assertEqual(len(downloaded), 1)
            self.assertEqual(downloaded[0][1].name, "vaultxt-ios-1.2.3-release.ipa")
            self.assertFalse(downloaded[0][1].exists())

    def test_downloads_with_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            artifacts = Path(temp) / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(artifacts, CODEMAGIC_HEADER, [artifact_row()])

            with patch.dict("os.environ", {"CODEMAGIC_API_TOKEN": "token"}):
                with patch("download_codemagic_artifacts.download", return_value=b"ipa"):
                    downloaded = download_codemagic_artifacts(releases, artifacts)

            self.assertEqual(downloaded[0][1].read_bytes(), b"ipa")
            downloaded[0][1].unlink(missing_ok=True)

    def test_empty_artifact_manifest_does_not_require_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            artifacts = Path(temp) / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(artifacts, CODEMAGIC_HEADER, [])

            with patch.dict("os.environ", {}, clear=True):
                downloaded = download_codemagic_artifacts(releases, artifacts)

            self.assertEqual(downloaded, [])

    def test_debug_artifact_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            artifacts = Path(temp) / "codemagic_artifacts.csv"
            write_csv(releases, RELEASE_HEADER, [planned_release()])
            write_csv(artifacts, CODEMAGIC_HEADER, [artifact_row("VaultXT-debug.ipa")])

            with self.assertRaises(CodemagicArtifactError):
                download_codemagic_artifacts(releases, artifacts, dry_run=True)


if __name__ == "__main__":
    unittest.main()
