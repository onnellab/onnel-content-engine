from __future__ import annotations

import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_store_versions import STORE_HEADER
from create_github_releases import release_body
from fill_ready_app_releases import FillReadyReleaseError, fill_ready_app_releases
from prepare_app_release_rows import CONFIG_HEADER
from validate_app_releases import RELEASE_HEADER, validate_app_releases


def release_row(**overrides: str) -> dict[str, str]:
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
            "release_type": "binary",
            "release_channel": "public",
            "status": "planned",
            "release_date": "2026-07-12",
            "release_title": "VaultXT v1.2.3",
            "summary": "VaultXT 1.2.3 update.",
            "changes": "Improved large-file scrolling.",
            "compatibility": "ios public release.",
            "upgrade_notes": "No special upgrade steps documented yet.",
        }
    )
    row.update(overrides)
    return row


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_config(path: Path, pattern: str = "generated/releases/vaultxt/{version}/{platform}/*-release.*") -> None:
    write_csv(
        path,
        CONFIG_HEADER,
        [
            {
                "app_id": "APP-0003",
                "app_slug": "vaultxt",
                "repository": "onnellab/vaultxt",
                "artifact_pattern": pattern,
                "notes": "",
            }
        ],
    )


def write_stores(
    path: Path, *,
    status: str = "unchanged",
    version: str = "1.2.3",
    notes: str = "",
) -> None:
    write_csv(
        path,
        STORE_HEADER,
        [
            {
                "app_id": "APP-0003",
                "app_slug": "vaultxt",
                "app_name": "VaultXT",
                "platform": "ios",
                "version": version,
                "status": status,
                "release_notes": "Improved large-file scrolling.",
                "checked_at": "2026-07-12T09:00:00Z",
                "notes": notes,
            }
        ],
    )


class FillReadyAppReleasesTest(unittest.TestCase):
    def release_artifact(self, name: str = "VaultXT-release.ipa") -> Path:
        artifact = ROOT / "generated" / "releases" / "vaultxt" / "1.2.3" / "ios" / name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"release artifact")
        self.addCleanup(lambda: artifact.unlink(missing_ok=True))
        return artifact

    def fixtures(self, temp: str, release: dict[str, str] | None = None) -> tuple[Path, Path, Path]:
        root = Path(temp)
        releases = root / "app_releases.csv"
        config = root / "app_release_config.csv"
        stores = root / "store_versions.csv"
        write_csv(releases, RELEASE_HEADER, [release or release_row()])
        write_config(config)
        write_stores(stores)
        return releases, config, stores

    def test_unverified_store_does_not_publish_binary_but_can_collect_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(temp)
            write_stores(stores, status="manual_check")
            artifact = self.release_artifact()
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["status"], "planned")
            self.assertEqual(updated[0]["release_type"], "binary")
            self.assertEqual(
                updated[0]["checksum_sha256"],
                hashlib.sha256(artifact.read_bytes()).hexdigest(),
            )
            self.assertEqual(validate_app_releases(releases), 1)

    def test_verified_public_binary_artifact_is_ready_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(temp)
            self.release_artifact()
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["status"], "ready")
            self.assertEqual(updated[0]["release_type"], "binary")
            self.assertTrue(updated[0]["artifact_path"])
            self.assertEqual(validate_app_releases(releases), 1)

    def test_confirmed_notes_only_is_ready_without_artifact_or_manual_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(
                temp, release_row(release_type="notes_only")
            )
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["status"], "ready")
            self.assertEqual(updated[0]["artifact_path"], "")
            self.assertEqual(updated[0]["checksum_sha256"], "")
            self.assertNotIn("Release build verified", release_body(updated[0]))
            self.assertIn("release notes only", release_body(updated[0]).lower())

    def test_confirmed_public_store_update_without_artifact_becomes_notes_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(temp)
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["status"], "ready")
            self.assertEqual(updated[0]["release_type"], "notes_only")
            self.assertEqual(updated[0]["artifact_path"], "")

    def test_public_release_with_missing_changes_uses_factual_store_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(temp, release_row(changes=""))
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertIn("public App Store", updated[0]["changes"])
            self.assertNotIn("bug fix", updated[0]["changes"].lower())

    def test_private_test_never_promotes_to_public_notes_even_when_store_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(
                temp, release_row(release_channel="private_test")
            )
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertEqual(updated, [])
            self.assertEqual(validate_app_releases(releases), 1)

    def test_private_test_artifact_readiness_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(
                temp, release_row(release_channel="private_test")
            )
            self.release_artifact()
            updated = fill_ready_app_releases(releases, config, stores)
            self.assertEqual(updated[0]["status"], "ready")
            self.assertEqual(updated[0]["release_channel"], "private_test")
            self.assertEqual(updated[0]["release_type"], "binary")

    def test_stale_version_or_failed_lookup_cannot_publish(self) -> None:
        for status, version, notes in (
            ("unchanged", "1.2.2", ""),
            ("not_released", "1.2.3", ""),
            ("updated", "1.2.3", "public page lookup failed"),
        ):
            with self.subTest(status=status, version=version):
                with tempfile.TemporaryDirectory() as temp:
                    releases, config, stores = self.fixtures(temp)
                    write_stores(stores, status=status, version=version, notes=notes)
                    updated = fill_ready_app_releases(releases, config, stores)
                    self.assertEqual(updated, [])
                    with releases.open(newline="", encoding="utf-8") as stream:
                        self.assertEqual(next(csv.DictReader(stream))["status"], "planned")

    def test_rejects_multiple_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(temp)
            self.release_artifact("VaultXT-release.ipa")
            self.release_artifact("VaultXT-alt-release.ipa")
            with self.assertRaises(FillReadyReleaseError):
                fill_ready_app_releases(releases, config, stores)

    def test_dry_run_does_not_write_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            releases, config, stores = self.fixtures(temp)
            original = releases.read_bytes()
            updated = fill_ready_app_releases(releases, config, stores, dry_run=True)
            self.assertEqual(updated[0]["status"], "ready")
            self.assertEqual(releases.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
