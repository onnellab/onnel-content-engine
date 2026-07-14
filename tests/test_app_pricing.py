from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_app_pricing import AppPricingValidationError, validate_app_pricing  # noqa: E402


class AppPricingValidationTest(unittest.TestCase):
    def test_validates_current_registry(self) -> None:
        self.assertEqual(validate_app_pricing(ROOT / "data" / "app_pricing.csv"), 10)

    def test_rejects_duplicate_product_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_pricing.csv"
            path.write_text(
                "\n".join(
                    [
                        "app_slug,product_name,product_type,price,currency,price_note",
                        "aligna,Aligna Pro,pro,3300,KRW,Manual",
                        "aligna,Aligna Pro,pro,3300,KRW,Manual",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(AppPricingValidationError):
                validate_app_pricing(path)

    def test_rejects_fractional_krw(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app_pricing.csv"
            path.write_text(
                "\n".join(
                    [
                        "app_slug,product_name,product_type,price,currency,price_note",
                        "aligna,Aligna Pro,pro,3300.5,KRW,Manual",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(AppPricingValidationError):
                validate_app_pricing(path)


if __name__ == "__main__":
    unittest.main()
