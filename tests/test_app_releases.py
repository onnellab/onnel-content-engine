from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_app_releases import AppReleaseValidationError, RELEASE_HEADER, validate_app_releases
from create_github_releases import GitHubReleaseError, create_github_releases


def release_csv(row: dict[str, str] | None = None) -> str:
    lines = [",".join(RELEASE_HEADER)]
    if row:
        lines.append(",".join(f'"{row.get(field, "")}"' for field in RELEASE_HEADER))
    return "\n".join(lines) + "\n"


class AppReleaseTest(unittest.TestCase):
    def release_artifact(self, name: str) -> tuple[Path, str, str]:
        artifact = ROOT / "generated" / name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"release artifact")
        checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.addCleanup(lambda: artifact.unlink(missing_ok=True))
        return artifact, f"generated/{name}", checksum

    def test_empty_release_manifest_is_valid(self) -> None:
        self.assertEqual(validate_app_releases(ROOT / "data" / "app_releases.csv"), 0)

    def test_ready_release_requires_release_artifact_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            _artifact, artifact_path, checksum = self.release_artifact("vaultxt-release-validation.apk")
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
                        "artifact_path": artifact_path,
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
                        "checksum_sha256": "0" * 64,
                        "status": "ready",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(AppReleaseValidationError):
                validate_app_releases(path)

    def test_create_github_releases_dry_run_does_not_require_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            _artifact, artifact_path, checksum = self.release_artifact("vaultxt-release-dry-run.apk")
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0003",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnelakin/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "artifact_path": artifact_path,
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

            messages = create_github_releases(path, dry_run=True)

            self.assertEqual(messages, [f"would create onnelakin/vaultxt v1.2.0 with {artifact_path}"])

    def test_create_github_releases_posts_draft_and_updates_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            _artifact, artifact_path, checksum = self.release_artifact("vaultxt-release-create.apk")
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0004",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnelakin/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "artifact_path": artifact_path,
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
            calls: list[tuple[str, str, dict[str, object] | None]] = []

            def fake_request(path_or_url: str, token: str, method: str = "GET", payload=None, data=None, content_type: str = "application/json"):
                calls.append((path_or_url, method, payload))
                if method == "GET":
                    raise GitHubReleaseError("HTTP 404 from releases/tags")
                if method == "POST" and path_or_url.endswith("/releases"):
                    self.assertTrue(payload["draft"])
                    return {"upload_url": "https://uploads.github.com/repos/onnelakin/vaultxt/releases/1/assets{?name,label}"}
                return {"state": "uploaded"}

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("create_github_releases.github_request", fake_request):
                    messages = create_github_releases(path)

            self.assertEqual(messages, [f"created onnelakin/vaultxt v1.2.0 with {artifact_path}"])
            self.assertIn("/repos/onnelakin/vaultxt/releases", [call[0] for call in calls])
            self.assertIn(",released,", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
