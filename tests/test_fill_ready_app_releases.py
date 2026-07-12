from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path
import tempfile

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fill_ready_app_releases import FillReadyReleaseError, PUBLICATION_HEADER, fill_ready_app_releases  # noqa: E402
from prepare_app_release_rows import CONFIG_HEADER  # noqa: E402
from validate_app_releases import RELEASE_HEADER, validate_app_releases  # noqa: E402


def release_row() -> dict[str, str]:
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
            "summary": "VaultXT 1.2.3 public store update detected.",
            "changes": "Improved large-file scrolling.",
            "compatibility": "ios public release.",
            "upgrade_notes": "No special upgrade steps documented yet.",
        }
    )
    return row


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_config(path: Path, pattern: str) -> None:
    write_csv(
        path,
        CONFIG_HEADER,
        [
            {
                "app_id": "APP-0003",
                "app_slug": "vaultxt",
                "repository": "onnelakin/vaultxt",
                "artifact_pattern": pattern,
                "notes": "",
            }
        ],
    )


def write_publications(path: Path, public_release: str = "") -> None:
    rows = []
    if public_release:
        rows.append(
            {
                "release_id": "REL-0001",
                "public_release": public_release,
                "approved_at": "2026-07-12T09:00:00+09:00",
                "notes": "",
            }
        )
    write_csv(path, PUBLICATION_HEADER, rows)


class FillReadyAppReleasesTest(unittest.TestCase):
    def release_artifact(self, name: str = "VaultXT-release.ipa") -> Path:
        artifact = ROOT / "generated" / "releases" / "vaultxt" / "1.2.3" / "ios" / name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"release artifact")
        self.addCleanup(lambda: artifact.unlink(missing_ok=True))
        return artifact

    def test_fills_artifact_but_keeps_private_test_candidate_planned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            config = Path(temp) / "app_release_config.csv"
            publications = Path(temp) / "app_release_publications.csv"
            artifact = self.release_artifact()
            write_csv(releases, RELEASE_HEADER, [release_row()])
            write_config(config, "generated/releases/vaultxt/{version}/{platform}/*-release.*")
            write_publications(publications)

            updated = fill_ready_app_releases(releases, config, publications)

            self.assertEqual(len(updated), 1)
            row = updated[0]
            self.assertEqual(row["status"], "planned")
            self.assertEqual(row["artifact_path"], "generated/releases/vaultxt/1.2.3/ios/VaultXT-release.ipa")
            self.assertEqual(row["checksum_sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(validate_app_releases(releases), 1)

    def test_promotes_only_when_public_release_is_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            config = Path(temp) / "app_release_config.csv"
            publications = Path(temp) / "app_release_publications.csv"
            self.release_artifact()
            write_csv(releases, RELEASE_HEADER, [release_row()])
            write_config(config, "generated/releases/vaultxt/{version}/{platform}/*-release.*")
            write_publications(publications, "true")

            updated = fill_ready_app_releases(releases, config, publications)

            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["status"], "ready")
            self.assertEqual(validate_app_releases(releases), 1)

    def test_skips_when_no_artifact_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            config = Path(temp) / "app_release_config.csv"
            publications = Path(temp) / "app_release_publications.csv"
            write_csv(releases, RELEASE_HEADER, [release_row()])
            write_config(config, "generated/releases/vaultxt/{version}/{platform}/*-release.*")
            write_publications(publications)

            promoted = fill_ready_app_releases(releases, config, publications)

            self.assertEqual(promoted, [])
            self.assertEqual(validate_app_releases(releases), 1)

    def test_rejects_multiple_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases = Path(temp) / "app_releases.csv"
            config = Path(temp) / "app_release_config.csv"
            publications = Path(temp) / "app_release_publications.csv"
            self.release_artifact("VaultXT-release.ipa")
            self.release_artifact("VaultXT-alt-release.ipa")
            write_csv(releases, RELEASE_HEADER, [release_row()])
            write_config(config, "generated/releases/vaultxt/{version}/{platform}/*-release.*")
            write_publications(publications)

            with self.assertRaises(FillReadyReleaseError):
                fill_ready_app_releases(releases, config, publications)


if __name__ == "__main__":
    unittest.main()
