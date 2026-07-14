from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_ai_provider_pricing import sync_ai_provider_pricing  # noqa: E402


class AiProviderPricingSyncTest(unittest.TestCase):
    def test_confirms_with_browser_rendered_text_after_static_miss(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pricing = root / "pricing.csv"
            status = root / "status.json"
            pricing.write_text(
                "\n".join(
                    [
                        "provider,service,unit,price_usd,source_url,source_browser_url,source_pattern,manual_verified_at,manual_verification_note,price_note",
                        'deepl,deepl-api-pro,1m_characters,25.00,https://example.com,https://example.com,"\\$25.{0,40}million.{0,40}characters",,,DeepL',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with patch("sync_ai_provider_pricing.fetch_text", return_value="static shell"):
                with patch("sync_ai_provider_pricing.fetch_browser_text", return_value="$25 per million characters"):
                    report = sync_ai_provider_pricing(pricing, status)

            self.assertEqual(report["outcome"], "ok")
            self.assertEqual(report["providers"][0]["status"], "ok")
            self.assertEqual(report["providers"][0]["confirmation_method"], "browser")

    def test_manual_verification_prevents_changed_status_when_automatic_checks_miss(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pricing = root / "pricing.csv"
            status = root / "status.json"
            pricing.write_text(
                "\n".join(
                    [
                        "provider,service,unit,price_usd,source_url,source_browser_url,source_pattern,manual_verified_at,manual_verification_note,price_note",
                        'deepl,deepl-api-pro,1m_characters,25.00,https://example.com,https://example.com,"\\$25.{0,40}million.{0,40}characters",2026-07-14,Manual,DeepL',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with patch("sync_ai_provider_pricing.fetch_text", return_value="static shell"):
                with patch("sync_ai_provider_pricing.fetch_browser_text", return_value="pricing hidden"):
                    report = sync_ai_provider_pricing(pricing, status)

            self.assertEqual(report["outcome"], "warning")
            self.assertEqual(report["providers"][0]["status"], "manual_ok")
            self.assertEqual(report["providers"][0]["confirmation_method"], "manual")


if __name__ == "__main__":
    unittest.main()
