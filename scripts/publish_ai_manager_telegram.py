#!/usr/bin/env python3
"""Send a non-authorizing AI Manager summary to Telegram."""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.telegram.org"
MESSAGE_LIMIT = 3900


def attention_id(item: dict) -> str:
    for key in ("review_id", "task_id", "finding_id", "release_id", "orchestration_id"):
        if item.get(key):
            return str(item[key])
    return "unidentified"


def message(report: dict, max_attention_items: int = 8) -> str:
    attention = report.get("requires_attention", [])
    summary = report.get("summary", {})
    lines = [
        "<b>ONNELLAB AI Manager</b>",
        f"Generated: <code>{html.escape(str(report.get('generated_at', '')))}</code>",
        f"Requires attention: <b>{len(attention)}</b>",
    ]
    for item in attention[:max_attention_items]:
        identifier = html.escape(attention_id(item))
        category = html.escape(str(item.get("category", "unknown")))
        lines.append(f"• <code>{identifier}</code> — {category}")
    if len(attention) > max_attention_items:
        lines.append(f"• …and {len(attention) - max_attention_items} more")
    nonzero = [(key, value) for key, value in summary.items() if value]
    if nonzero:
        lines.append("")
        lines.append("<b>Non-zero summary</b>")
        lines.extend(
            f"• {html.escape(key.replace('_', ' '))}: {html.escape(str(value))}"
            for key, value in nonzero
        )
    lines.extend(
        [
            "",
            "Informational only. Approval must be completed in the audited GitHub workflow.",
        ]
    )
    text = "\n".join(lines)
    if len(text) > MESSAGE_LIMIT:
        plain = html.unescape(text)
        text = html.escape(plain[: MESSAGE_LIMIT - 25].rstrip()) + "\n…report truncated"
    return text


def keyboard(repository: str) -> dict:
    root = f"https://github.com/{repository}/actions/workflows"
    return {
        "inline_keyboard": [
            [
                {"text": "Coder 작업 승인", "url": f"{root}/approve-ai-coder-task.yml"},
                {"text": "QA 통과 PR 병합", "url": f"{root}/merge-approved-app-pr.yml"},
            ],
            [
                {"text": "비공개 테스트 시작", "url": f"{root}/start-private-test-orchestration.yml"},
                {"text": "Actions 보기", "url": f"https://github.com/{repository}/actions"},
            ],
        ]
    }


def send(token: str, payload: dict) -> None:
    request = Request(
        f"{API}/bot{token}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "ONNELLAB-AI-Manager"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode())
        if not result.get("ok"):
            raise RuntimeError("Telegram API rejected the Manager report")
    except HTTPError as error:
        raise RuntimeError(f"Telegram Manager report failed with HTTP {error.code}") from error
    except (URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        raise RuntimeError(
            f"Telegram Manager report failed ({type(error).__name__})"
        ) from error


def main() -> int:
    config = json.loads(
        (ROOT / "data" / "ai_manager_telegram_config.json").read_text(encoding="utf-8")
    )
    if not config.get("enabled"):
        print("AI Manager Telegram report is disabled")
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required when Telegram reporting is enabled"
        )
    repository = str(config.get("repository", ""))
    if "/" not in repository:
        raise SystemExit("Telegram report repository must be owner/name")
    max_items = int(config.get("max_attention_items", 8))
    if max_items < 1 or max_items > 20:
        raise SystemExit("max_attention_items must be between 1 and 20")
    report = json.loads(
        (ROOT / "data" / "ai_manager_daily_report.json").read_text(encoding="utf-8")
    )
    send(
        token,
        {
            "chat_id": chat_id,
            "text": message(report, max_items),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": keyboard(repository),
        },
    )
    print("sent AI Manager Telegram report")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
