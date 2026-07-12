from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_app_releases import AppReleaseValidationError, RELEASE_HEADER, validate_app_releases


def release_csv(row: dict[str, str] | None = None) -> str:
    lines = [",".join(RELEASE_HEADER)]
    if row:
        lines.append(",".join(f'"{row.get(field, "")}"' for field in RELEASE_HEADER))
    return "\n".join(lines) + "\n"


class AppReleaseTest(unittest.TestCase):
    def test_empty_release_manifest_is_valid(self) -> None:
        self.assertEqual(validate_app_releases(ROOT / "data" / "app_releases.csv"), 0)

    def test_ready_release_requires_release_artifact_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            artifact = ROOT / "generated" / "release-artifact.apk"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"release artifact")
            checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.addCleanup(lambda: artifact.unlink(missing_ok=True))
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0001",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnelakin/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "artifact_path": "generated/release-artifact.apk",
                        "checksum_sha256": checksum,
                        "previous_tag": "v1.1.0",
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.0",
                        "summary": "Release build for VaultXT.",
                        "changes": "Improved large file handling.",
                        "compatibility": "Android release build.",
                        "upgrade_notes": "No migration required.",
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(validate_app_releases(path), 1)

    def test_debug_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0002",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnelakin/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "artifact_path": "build/app-debug.apk",
                        "status": "planned",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(AppReleaseValidationError):
                validate_app_releases(path)


if __name__ == "__main__":
    unittest.main()
