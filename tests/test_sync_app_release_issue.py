from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_app_release_issue import has_attention, issue_body, sync_app_release_issue  # noqa: E402


REPORT_WITH_ATTENTION = """# App Release Status

## Attention Queue

| App | Platform | Status | Next action | Notes |
| --- | --- | --- | --- | --- |
| VaultXT | ios | planned | Add release artifact and checksum | - |
"""

REPORT_CLEAR = """# App Release Status

## Attention Queue

No release automation items need attention.
"""


class SyncAppReleaseIssueTest(unittest.TestCase):
    def test_attention_detection(self) -> None:
        self.assertTrue(has_attention(REPORT_WITH_ATTENTION))
        self.assertFalse(has_attention(REPORT_CLEAR))
        self.assertIn("generated/reports/app_releases.md", issue_body(REPORT_WITH_ATTENTION))

    def test_dry_run_does_not_require_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "app_releases.md"
            report.write_text(REPORT_WITH_ATTENTION, encoding="utf-8")

            message = sync_app_release_issue(report, "onnelakin/onnel-content-engine", dry_run=True)

            self.assertIn("would sync onnelakin/onnel-content-engine", message)

    def test_updates_existing_issue_when_attention_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "app_releases.md"
            report.write_text(REPORT_WITH_ATTENTION, encoding="utf-8")
            calls: list[tuple[str, str, dict[str, object] | None]] = []

            def fake_request(path: str, token: str, method: str = "GET", payload=None):
                calls.append((path, method, payload))
                if method == "GET":
                    return [{"number": 7, "title": "ONNELLAB App Release Attention Queue", "state": "closed"}]
                return {"number": 7}

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("sync_app_release_issue.github_request", fake_request):
                    message = sync_app_release_issue(report, "onnelakin/onnel-content-engine")

            self.assertEqual(message, "updated onnelakin/onnel-content-engine issue #7")
            self.assertEqual(calls[-1][1], "PATCH")
            self.assertEqual(calls[-1][2]["state"], "open")

    def test_closes_open_issue_when_attention_clears(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "app_releases.md"
            report.write_text(REPORT_CLEAR, encoding="utf-8")
            calls: list[tuple[str, str, dict[str, object] | None]] = []

            def fake_request(path: str, token: str, method: str = "GET", payload=None):
                calls.append((path, method, payload))
                if method == "GET":
                    return [{"number": 7, "title": "ONNELLAB App Release Attention Queue", "state": "open"}]
                return {"number": 7}

            with patch.dict("os.environ", {"GITHUB_TOKEN": "token"}):
                with patch("sync_app_release_issue.github_request", fake_request):
                    message = sync_app_release_issue(report, "onnelakin/onnel-content-engine")

            self.assertEqual(message, "closed onnelakin/onnel-content-engine issue #7")
            self.assertEqual(calls[-1][2], {"state": "closed"})


if __name__ == "__main__":
    unittest.main()
