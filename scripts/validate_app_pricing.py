#!/usr/bin/env python3
"""Validate the paid product price registry used by the dashboard."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_PRICING = ROOT / "data" / "app_pricing.csv"
REQUIRED_COLUMNS = ("app_slug", "product_name", "product_type", "price", "currency", "price_note")
SUPPORTED_TYPES = {"paid_download", "pro", "ai_credit"}
SUPPORTED_CURRENCIES = {"KRW", "USD"}


class AppPricingValidationError(ValueError):
    """Raised when app pricing registry rows are invalid."""


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise AppPricingValidationError(f"app pricing registry does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise AppPricingValidationError(f"app pricing registry is missing column(s): {', '.join(missing)}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def validate_price(value: str, currency: str) -> None:
    if not value:
        raise AppPricingValidationError("price must not be empty")
    try:
        number = float(value)
    except ValueError as error:
        raise AppPricingValidationError(f"price must be numeric: {value}") from error
    if number <= 0:
        raise AppPricingValidationError(f"price must be positive: {value}")
    if currency == "KRW" and not number.is_integer():
        raise AppPricingValidationError(f"KRW price must be a whole number: {value}")
    if currency == "USD" and round(number, 2) != number:
        raise AppPricingValidationError(f"USD price must use at most two decimals: {value}")


def validate_app_pricing(path: Path = DEFAULT_APP_PRICING) -> int:
    rows = read_rows(path)
    if not rows:
        raise AppPricingValidationError("app pricing registry has no rows")
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows, start=2):
        slug = row["app_slug"]
        product_name = row["product_name"]
        product_type = row["product_type"]
        currency = row["currency"]
        if not slug:
            raise AppPricingValidationError(f"row {index} has empty app_slug")
        if not product_name:
            raise AppPricingValidationError(f"row {index} has empty product_name")
        if product_type not in SUPPORTED_TYPES:
            raise AppPricingValidationError(f"row {index} has unsupported product_type: {product_type}")
        if currency not in SUPPORTED_CURRENCIES:
            raise AppPricingValidationError(f"row {index} has unsupported currency: {currency}")
        key = (slug, product_name, product_type)
        if key in seen:
            raise AppPricingValidationError(f"duplicate app pricing row: {slug} {product_name} {product_type}")
        seen.add(key)
        validate_price(row["price"], currency)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate app pricing registry")
    parser.add_argument("--path", type=Path, default=DEFAULT_APP_PRICING)
    args = parser.parse_args()
    try:
        count = validate_app_pricing(args.path)
    except AppPricingValidationError as error:
        print(f"app pricing validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} app pricing row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
