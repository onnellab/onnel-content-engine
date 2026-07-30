from __future__ import annotations

import json
import sys
import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collect_gmail_policy_alerts


class GmailPolicyAlertsTest(unittest.TestCase):
    def test_sync_status_keeps_both_non_sensitive_account_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data").mkdir()
            with patch.object(collect_gmail_policy_alerts, "ROOT", root):
                collect_gmail_policy_alerts.record_sync(
                    "developer", "collected", 2, "2026-07-30T00:00:00+00:00"
                )
                collect_gmail_policy_alerts.record_sync(
                    "official", "collected", 1, "2026-07-30T00:01:00+00:00"
                )
            status = json.loads(
                (root / "data/gmail_policy_alert_sync_status.json").read_text()
            )

        self.assertEqual(status["state"], "collected")
        self.assertEqual(status["imported"], 3)
        self.assertEqual(set(status["accounts"]), {"developer", "official"})
        self.assertNotIn("@", json.dumps(status))

    def test_collection_normalizes_sender_and_deduplicates_shared_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "gmail_policy_alert_config.json").write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "label": "onnel-store-policy",
                        "rules": [
                            {
                                "sender": "no-reply-googleplay-developer@google.com",
                                "subject_pattern": "Billing requirement",
                                "store": "google_play",
                                "app_slugs": ["tagweaver", "vaultxt"],
                                "kind": "billing",
                                "event_key": "billing-8-deadline",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (data / "store_policy_alerts.json").write_text(
                json.dumps({"alerts": []}), encoding="utf-8"
            )

            def fake_call(url: str, **_: object) -> dict:
                if "/messages?" in url:
                    return {"messages": [{"id": "mailbox-specific-id"}]}
                return {
                    "payload": {
                        "headers": [
                            {
                                "name": "From",
                                "value": "Google Play <no-reply-googleplay-developer@google.com>",
                            },
                            {"name": "Subject", "value": "Billing requirement"},
                            {"name": "Message-ID", "value": "<shared-message@google.com>"},
                        ]
                    }
                }

            with (
                patch.object(collect_gmail_policy_alerts, "ROOT", root),
                patch.object(collect_gmail_policy_alerts, "access_token", return_value="token"),
                patch.object(collect_gmail_policy_alerts, "call", side_effect=fake_call),
            ):
                previous = environ.get("GMAIL_ACCOUNT_ALIAS")
                try:
                    environ["GMAIL_ACCOUNT_ALIAS"] = "developer"
                    self.assertEqual(collect_gmail_policy_alerts.main(), 0)
                    environ["GMAIL_ACCOUNT_ALIAS"] = "official"
                    self.assertEqual(collect_gmail_policy_alerts.main(), 0)
                finally:
                    if previous is None:
                        environ.pop("GMAIL_ACCOUNT_ALIAS", None)
                    else:
                        environ["GMAIL_ACCOUNT_ALIAS"] = previous

            alerts = json.loads((data / "store_policy_alerts.json").read_text())["alerts"]
            status = json.loads(
                (data / "gmail_policy_alert_sync_status.json").read_text()
            )

        self.assertEqual(len(alerts), 2)
        self.assertEqual({item["app_slug"] for item in alerts}, {"tagweaver", "vaultxt"})
        self.assertTrue(all(item["source_accounts"] == ["developer", "official"] for item in alerts))
        self.assertTrue(all(item["event_key"] == "billing-8-deadline" for item in alerts))
        self.assertEqual(status["imported"], 2)


if __name__ == "__main__":
    unittest.main()
