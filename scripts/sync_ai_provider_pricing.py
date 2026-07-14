#!/usr/bin/env python3
"""Check AI provider price assumptions used by the manual dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROVIDER_PRICING = ROOT / "data" / "ai_provider_pricing.csv"
DEFAULT_STATUS_OUTPUT = ROOT / "data" / "ai_provider_pricing_status.json"
KST = ZoneInfo("Asia/Seoul")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def fetch_text(url: str, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": "ONNELLAB content engine pricing monitor"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def matches_pattern(text: str, pattern: str) -> bool:
    return bool(pattern and re.search(pattern, compact_text(text), flags=re.IGNORECASE))


def fetch_browser_text(url: str, timeout: float) -> str:
    script = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, locale: 'en-US' });
  await page.goto(process.argv[2], { waitUntil: 'networkidle', timeout: Number(process.argv[3]) });
  await page.waitForTimeout(2500);
  await page.evaluate(() => window.scrollTo(0, Math.min(document.body.scrollHeight, 2800)));
  await page.waitForTimeout(1200);
  console.log(await page.evaluate(() => document.body ? document.body.innerText : ''));
  await browser.close();
})().catch((error) => {
  console.error(String(error && error.stack || error));
  process.exit(2);
});
""".strip()
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", dir=ROOT, delete=False) as handle:
        handle.write(script)
        path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["node", str(path), url, str(int(timeout * 1000))],
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout + 10,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "browser process exited with an error").strip()
            if "Cannot find module 'playwright'" in detail:
                detail = "Playwright is not installed in this environment"
            detail = re.sub(r"Require stack:.*", "", detail, flags=re.DOTALL)
            detail = compact_text(detail)[:500]
            raise RuntimeError(detail)
        return completed.stdout
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"browser check timed out after {error.timeout} seconds") from error
    finally:
        path.unlink(missing_ok=True)


def sync_ai_provider_pricing(
    pricing_path: Path = DEFAULT_PROVIDER_PRICING,
    status_output: Path = DEFAULT_STATUS_OUTPUT,
    timeout: float = 20.0,
) -> dict[str, object]:
    providers: list[dict[str, object]] = []
    messages: list[str] = []
    outcome = "ok"
    for row in read_rows(pricing_path):
        provider_key = f"{row.get('provider', '')}:{row.get('service', '')}"
        source_url = row.get("source_url", "")
        source_browser_url = row.get("source_browser_url", "")
        pattern = row.get("source_pattern", "")
        manual_verified_at = row.get("manual_verified_at", "")
        status = {
            "provider": row.get("provider", ""),
            "service": row.get("service", ""),
            "unit": row.get("unit", ""),
            "expected_price_usd": row.get("price_usd", ""),
            "source_url": source_url,
            "source_browser_url": source_browser_url,
            "manual_verified_at": manual_verified_at,
            "manual_verification_note": row.get("manual_verification_note", ""),
            "status": "unchecked",
            "message": "",
            "confirmation_method": "",
        }
        try:
            text = fetch_text(source_url, timeout)
        except (OSError, URLError) as error:
            static_error = f"could not fetch source: {error}"
        else:
            static_error = ""
            if matches_pattern(text, pattern):
                status["status"] = "ok"
                status["message"] = "expected price pattern found in static source"
                status["confirmation_method"] = "static"
                providers.append(status)
                continue

        browser_error = ""
        if source_browser_url:
            try:
                browser_text = fetch_browser_text(source_browser_url, timeout)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                browser_error = f"browser check failed: {error}"
            else:
                if matches_pattern(browser_text, pattern):
                    status["status"] = "ok"
                    status["message"] = "expected price pattern found in browser-rendered source"
                    status["confirmation_method"] = "browser"
                    providers.append(status)
                    continue

        if manual_verified_at:
            status["status"] = "manual_ok"
            status["message"] = "automatic price check could not confirm the page, but local assumption is manually verified"
            status["confirmation_method"] = "manual"
            if static_error:
                status["static_error"] = static_error
            if browser_error:
                status["browser_error"] = browser_error
            messages.append(f"{provider_key} price requires manual confirmation; using manual verification from {manual_verified_at}")
            if outcome == "ok":
                outcome = "warning"
        else:
            status["status"] = "changed"
            status["message"] = "expected price pattern was not found; review provider pricing"
            if static_error:
                status["static_error"] = static_error
            if browser_error:
                status["browser_error"] = browser_error
            messages.append(f"{provider_key} price pattern changed or could not be confirmed")
            outcome = "changed"
        providers.append(status)
    report: dict[str, object] = {
        "checked_at": datetime.now(tz=KST).isoformat(timespec="seconds"),
        "outcome": outcome,
        "messages": messages or ["AI provider pricing matched local assumptions."],
        "providers": providers,
    }
    status_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AI provider pricing assumptions")
    parser.add_argument("--pricing-path", type=Path, default=DEFAULT_PROVIDER_PRICING)
    parser.add_argument("--status-output", type=Path, default=DEFAULT_STATUS_OUTPUT)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--fail-on-change", action="store_true")
    args = parser.parse_args()
    report = sync_ai_provider_pricing(args.pricing_path, args.status_output, args.timeout)
    print("; ".join(str(message) for message in report["messages"]))
    return 1 if args.fail_on_change and report["outcome"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
