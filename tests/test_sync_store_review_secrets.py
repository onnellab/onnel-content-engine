from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_store_review_secrets import SECRET_KEYS, SecretSyncError, sync_store_review_secrets  # noqa: E402


class StoreReviewSecretSyncTest(unittest.TestCase):
    @staticmethod
    def complete_env() -> dict[str, str]:
        env = {key: f"value-{index}" for index, key in enumerate(SECRET_KEYS)}
        env["GOOGLE_PLAY_REPORTS_BUCKET"] = "pubsite_prod_rev_123"
        return env

    def test_requires_all_apple_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SecretSyncError, "APP_STORE_CONNECT_KEY_ID"):
                sync_store_review_secrets(dry_run=True)

    def test_dry_run_accepts_complete_credentials(self) -> None:
        env = self.complete_env()
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(sync_store_review_secrets(dry_run=True), list(SECRET_KEYS))

    def test_requires_lifetime_reports_bucket(self) -> None:
        env = self.complete_env()
        env.pop("GOOGLE_PLAY_REPORTS_BUCKET")
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretSyncError, "GOOGLE_PLAY_REPORTS_BUCKET"):
                sync_store_review_secrets(dry_run=True)

    def test_syncs_lifetime_reports_bucket(self) -> None:
        env = self.complete_env()
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                sync_store_review_secrets(dry_run=True),
                list(SECRET_KEYS),
            )

    def test_rejects_non_report_bucket(self) -> None:
        env = self.complete_env()
        env["GOOGLE_PLAY_REPORTS_BUCKET"] = "ordinary-project-bucket"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretSyncError, "must start with"):
                sync_store_review_secrets(dry_run=True)


if __name__ == "__main__":
    unittest.main()
