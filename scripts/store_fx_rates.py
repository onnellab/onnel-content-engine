"""Convert store report money to historical KRW estimates using ECB euro reference rates.

Each source record retains the ORIGINAL money/currency; never replace settlement
amounts with FX estimates and never infer Apple fees from the customer proceeds gap.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ECB_HISTORY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
WON = Decimal("1")
SOURCE = "European Central Bank (ECB) euro foreign exchange reference rates"


def parse_ecb_xml(raw: bytes) -> dict[str, dict[str, Decimal]]:
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("ECB history exceeds expected size")
    root = ET.fromstring(raw)
    result: dict[str, dict[str, Decimal]] = {}
    for item in root.iter():
        day = item.attrib.get("time", "")
        if len(day) != 10 or not day.startswith("20"):
            continue
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        rates = {"EUR": Decimal("1")}
        for quote in item:
            currency = quote.attrib.get("currency", "").upper()
            if len(currency) != 3 or not currency.isalpha():
                continue
            try:
                number = Decimal(quote.attrib["rate"])
            except (InvalidOperation, KeyError):
                continue
            if number.is_finite() and number > 0:
                rates[currency] = number
        if "KRW" in rates:
            result[day] = rates
    if not result:
        raise ValueError("ECB history contains no usable KRW reference rates")
    return result


def fetch_history() -> dict[str, dict[str, Decimal]]:
    request = urllib.request.Request(ECB_HISTORY, headers={"User-Agent":"ONNELLAB-Ops-FX/1.0"})
    with urllib.request.urlopen(request, timeout=35) as response:
        return parse_ecb_xml(response.read())


def quote(day: str, currency: str, history: dict) -> dict | None:
    currency = (currency or "").strip().upper()
    if currency == "KRW":
        return {"rate":"1", "as_of":day}
    if not currency or not day:
        return None
    days = sorted(history)
    pos = bisect.bisect_right(days, day) - 1
    if pos < 0:
        return None
    closest = days[pos]
    if (date.fromisoformat(day) - date.fromisoformat(closest)).days > 7:
        return None
    rates = history[closest]
    if currency not in rates or "KRW" not in rates:
        return None
    ratio = rates["KRW"] / rates[currency]
    if not ratio.is_finite() or ratio <= 0:
        return None
    return {"rate":format(ratio, "f"), "as_of":closest}


def won(value: object, rate: object) -> str:
    money = Decimal(str(value or "0"))
    conversion = Decimal(str(rate))
    if not money.is_finite() or not conversion.is_finite() or conversion <= 0:
        raise ValueError("Invalid finance conversion input")
    return str((money * conversion).quantize(WON, rounding=ROUND_HALF_UP))


def enrich_ledger(ledger: dict, previous: dict | None = None, history: dict | None = None,
                  fetcher=fetch_history) -> dict:
    """Attach independently auditable KRW estimates without mutating original values."""
    rows = ledger.get("rows", [])
    settlements = ledger.get("settlements", [])
    need_foreign = any(
        currency and currency != "KRW"
        for row in list(rows) + list(settlements)
        for currency in (row.get("currency"), row.get("proceeds_currency"),
                         row.get("customer_currency"))
    )
    state = "not_needed"
    errors = []
    if history is None and need_foreign:
        try:
            history = fetcher()
            state = "ok"
        except (OSError, ValueError, ET.ParseError) as exc:
            history = {}
            state = "unavailable"
            errors.append("ECB historical rates unavailable: " + type(exc).__name__)
    elif history is not None:
        state = "ok"
    history = history or {}
    previous_rates = (previous or {}).get("fx_rates", {})
    saved_rates = {}
    missing_sales = 0
    missing_fees = 0
    missing_settlement = 0

    def get_rate(day, currency):
        key = str(day) + "|" + str(currency or "").upper()
        current = quote(day, currency, history)
        if current is None:
            cached = previous_rates.get(key)
            if isinstance(cached, dict) and cached.get("rate") and cached.get("as_of"):
                current = cached
        if current:
            saved_rates[key] = current
        return current

    for row in rows:
        day = str(row.get("date", ""))
        currency = str(row.get("currency", "")).upper()
        fx = get_rate(day, currency)
        if fx:
            row["fx_sales_rate"] = fx["rate"]
            row["fx_sales_date"] = fx["as_of"]
            for field in ("gross", "refund"):
                row[field + "_krw"] = won(row.get(field, "0"), fx["rate"])
            # The displayed net must equal displayed gross + refund even when
            # independently rounded original values differ by one won.
            row["net_sales_krw"] = str(
                Decimal(row["gross_krw"]) + Decimal(row["refund_krw"])
            )
        else:
            for field in ("gross", "refund", "net_sales"):
                row.pop(field + "_krw", None)
            row.pop("fx_sales_rate", None)
            row.pop("fx_sales_date", None)
            missing_sales += 1
        if row.get("fee_confirmed") is True:
            if fx:
                row["fee_krw"] = won(row.get("fee", "0"), fx["rate"])
            else:
                row.pop("fee_krw", None)
                missing_fees += 1
        else:
            row.pop("fee_krw", None)
        if row.get("proceeds_currency"):
            proceeds_fx = get_rate(day, str(row.get("proceeds_currency")).upper())
            if proceeds_fx:
                row["proceeds_krw"] = won(row.get("proceeds", "0"), proceeds_fx["rate"])
            else:
                row.pop("proceeds_krw", None)

    for row in settlements:
        month = str(row.get("fiscal_month", ""))
        try:
            start = date.fromisoformat(month + "-01")
            following = date(start.year + (start.month == 12),
                             1 if start.month == 12 else start.month + 1, 1)
            day = (following.fromordinal(following.toordinal()-1)).isoformat()
        except ValueError:
            missing_settlement += 1
            continue
        proceeds_fx = get_rate(day, str(row.get("proceeds_currency", "")).upper())
        if proceeds_fx:
            row["proceeds_krw"] = won(row.get("proceeds", "0"), proceeds_fx["rate"])
            row["fx_proceeds_date"] = proceeds_fx["as_of"]
        else:
            row.pop("proceeds_krw", None)
            row.pop("fx_proceeds_date", None)
            missing_settlement += 1
        if row.get("customer_currency"):
            customer_fx = get_rate(day, str(row.get("customer_currency", "")).upper())
            if customer_fx:
                row["gross_krw"] = won(row.get("gross", "0"), customer_fx["rate"])
            else:
                row.pop("gross_krw", None)

    ledger["fx_rates"] = saved_rates
    ledger["fx_status"] = {
        "source": SOURCE,
        "url": ECB_HISTORY,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": state,
        "missing_sales_rows": missing_sales,
        "missing_fee_rows": missing_fees,
        "missing_settlement_rows": missing_settlement,
        "errors": errors,
        "interpretation": "Reference-date estimated KRW, not actual bank settlement FX.",
    }
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich private ledger with dated ECB KRW estimates")
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    record = json.loads(args.ledger.read_text(encoding="utf-8"))
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if (
        args.previous and args.previous.is_file()
    ) else None
    enrich_ledger(record, previous=previous)
    args.ledger.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    os.chmod(args.ledger, 0o600)
    print("FX_ESTIMATE_HEALTH=" + json.dumps(record["fx_status"],ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
