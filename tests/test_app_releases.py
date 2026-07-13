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
from sync_github_release_status import sync_github_release_status


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

    def test_current_release_manifest_is_valid(self) -> None:
        path = ROOT / "data" / "app_releases.csv"
        row_count = len(path.read_text(encoding="utf-8").splitlines()) - 1
        self.assertEqual(validate_app_releases(path), row_count)

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
                        "repository": "onnellab/vaultxt",
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
                        "repository": "onnellab/vaultxt",
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
                        "repository": "onnellab/vaultxt",
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

            self.assertEqual(messages, [f"would create onnellab/vaultxt v1.2.0 with {artifact_path}"])

    def test_private_test_ready_release_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0006",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnellab/vaultxt",
                        "tag": "v1.2.1",
                        "version": "1.2.1",
                        "platform": "ios",
                        "build_type": "release",
                        "release_type": "notes_only",
                        "release_channel": "private_test",
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.1",
                        "summary": "VaultXT private test build.",
                        "changes": "Internal TestFlight changes.",
                        "compatibility": "ios private test build.",
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(create_github_releases(path, dry_run=True), [])

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
                        "repository": "onnellab/vaultxt",
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
                    return {
                        "id": 123,
                        "html_url": "https://github.com/onnellab/vaultxt/releases/tag/v1.2.0",
                        "published_at": "2026-07-12T00:00:00Z",
                        "upload_url": "https://uploads.github.com/repos/onnellab/vaultxt/releases/1/assets{?name,label}",
                    }
                return {"state": "uploaded"}

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("create_github_releases.github_request", fake_request):
                    messages = create_github_releases(path)

            self.assertEqual(messages, [f"created onnellab/vaultxt v1.2.0 with {artifact_path}"])
            self.assertIn("/repos/onnellab/vaultxt/releases", [call[0] for call in calls])
            self.assertIn(",released,", path.read_text(encoding="utf-8"))
            self.assertIn("https://github.com/onnellab/vaultxt/releases/tag/v1.2.0", path.read_text(encoding="utf-8"))

    def test_create_github_releases_syncs_existing_release_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            _artifact, artifact_path, checksum = self.release_artifact("vaultxt-release-existing.apk")
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0005",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnellab/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "artifact_path": artifact_path,
                        "checksum_sha256": checksum,
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.0",
                        "summary": "Release build for VaultXT.",
                        "changes": "Improved large file handling.",
                        "compatibility": "Android release build.",
                    }
                ),
                encoding="utf-8",
            )

            def fake_request(path_or_url: str, token: str, method: str = "GET", payload=None, data=None, content_type: str = "application/json"):
                self.assertEqual(method, "GET")
                return {
                    "id": 456,
                    "html_url": "https://github.com/onnellab/vaultxt/releases/tag/v1.2.0",
                    "published_at": "2026-07-12T00:00:00Z",
                }

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("create_github_releases.github_request", fake_request):
                    messages = create_github_releases(path)

            text = path.read_text(encoding="utf-8")
            self.assertEqual(messages, ["synced existing onnellab/vaultxt v1.2.0 https://github.com/onnellab/vaultxt/releases/tag/v1.2.0"])
            self.assertIn(",released,", text)
            self.assertIn(",456,", text)

    def test_sync_github_release_status_updates_public_existing_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0005",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnellab/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "release_type": "notes_only",
                        "release_channel": "public",
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.0",
                        "summary": "Release notes for VaultXT.",
                        "changes": "Improved large file handling.",
                        "compatibility": "Android public release.",
                    }
                ),
                encoding="utf-8",
            )

            def fake_request(path_or_url: str, token: str, method: str = "GET", payload=None, data=None, content_type: str = "application/json"):
                self.assertEqual(method, "GET")
                return {
                    "id": 789,
                    "html_url": "https://github.com/onnellab/vaultxt/releases/tag/v1.2.0",
                    "published_at": "2026-07-12T00:00:00Z",
                }

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("sync_github_release_status.github_request", fake_request):
                    messages = sync_github_release_status(path, status_output=Path(temp) / "sync_status.json")

            text = path.read_text(encoding="utf-8")
            self.assertEqual(messages, ["synced onnellab/vaultxt v1.2.0 https://github.com/onnellab/vaultxt/releases/tag/v1.2.0"])
            self.assertIn(",released,", text)
            self.assertIn(",789,", text)
            self.assertIn('"outcome": "synced"', (Path(temp) / "sync_status.json").read_text(encoding="utf-8"))

    def test_sync_github_release_status_can_skip_missing_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            path.write_text(release_csv(), encoding="utf-8")
            status_output = Path(temp) / "sync_status.json"

            with patch.dict("os.environ", {}, clear=True):
                messages = sync_github_release_status(path, allow_missing_token=True, status_output=status_output)

            self.assertEqual(messages, ["skipped GitHub release status sync: token not configured"])
            self.assertIn('"outcome": "skipped"', status_output.read_text(encoding="utf-8"))

    def test_create_github_releases_supports_notes_only_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0006",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnellab/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "release_type": "notes_only",
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.0",
                        "summary": "Release notes for VaultXT.",
                        "changes": "Improved large file handling.",
                        "compatibility": "Android public release.",
                    }
                ),
                encoding="utf-8",
            )
            calls: list[tuple[str, str, dict[str, object] | None]] = []

            def fake_request(path_or_url: str, token: str, method: str = "GET", payload=None, data=None, content_type: str = "application/json"):
                calls.append((path_or_url, method, payload))
                if method == "GET":
                    raise GitHubReleaseError("HTTP 404 from releases/tags")
                return {
                    "id": 789,
                    "html_url": "https://github.com/onnellab/vaultxt/releases/tag/v1.2.0",
                    "published_at": "2026-07-12T00:00:00Z",
                }

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("create_github_releases.github_request", fake_request):
                    messages = create_github_releases(path)

            self.assertEqual(messages, ["created onnellab/vaultxt v1.2.0 as release notes"])
            self.assertEqual([call for call in calls if "uploads.github.com" in call[0]], [])
            self.assertIn("https://github.com/onnellab/vaultxt/releases/tag/v1.2.0", path.read_text(encoding="utf-8"))

    def test_private_test_release_is_not_created_as_github_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            _artifact, artifact_path, checksum = self.release_artifact("vaultxt-private-candidate-release.apk")
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0007",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnellab/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "release_channel": "private_test",
                        "artifact_path": artifact_path,
                        "checksum_sha256": checksum,
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.0",
                        "summary": "Private test build for VaultXT.",
                        "changes": "Internal QA build.",
                        "compatibility": "Android private test build.",
                    }
                ),
                encoding="utf-8",
            )

            messages = create_github_releases(path, dry_run=True)

            self.assertEqual(messages, [])

    def test_public_ready_release_rejects_local_metadata_placeholder_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_releases.csv"
            _artifact, artifact_path, checksum = self.release_artifact("vaultxt-placeholder-release.apk")
            path.write_text(
                release_csv(
                    {
                        "release_id": "REL-0008",
                        "app_id": "APP-0003",
                        "app_slug": "vaultxt",
                        "app_name": "VaultXT",
                        "repository": "onnellab/vaultxt",
                        "tag": "v1.2.0",
                        "version": "1.2.0",
                        "platform": "android",
                        "build_type": "release",
                        "release_channel": "public",
                        "artifact_path": artifact_path,
                        "checksum_sha256": checksum,
                        "status": "ready",
                        "release_date": "2026-07-12",
                        "release_title": "VaultXT v1.2.0",
                        "summary": "Public release for VaultXT.",
                        "changes": "Local Flutter build metadata version.",
                        "compatibility": "Android public release.",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(AppReleaseValidationError):
                validate_app_releases(path)


if __name__ == "__main__":
    unittest.main()
