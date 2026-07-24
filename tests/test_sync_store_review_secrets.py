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
    def test_requires_all_apple_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SecretSyncError, "APP_STORE_CONNECT_KEY_ID"):
                sync_store_review_secrets(dry_run=True)

    def test_dry_run_accepts_complete_credentials(self) -> None:
        env = {key: f"value-{index}" for index, key in enumerate(SECRET_KEYS)}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(sync_store_review_secrets(dry_run=True), list(SECRET_KEYS))

    def test_syncs_optional_reports_bucket_when_present(self) -> None:
        env = {key: f"value-{index}" for index, key in enumerate(SECRET_KEYS)}
        env["GOOGLE_PLAY_REPORTS_BUCKET"] = "pubsite_prod_rev_123"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                sync_store_review_secrets(dry_run=True),
                [*SECRET_KEYS, "GOOGLE_PLAY_REPORTS_BUCKET"],
            )


if __name__ == "__main__":
    unittest.main()
