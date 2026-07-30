from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_store_policy_impact


class StorePolicyAutomationTest(unittest.TestCase):
    def test_changed_policy_uses_registry_slug_column(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "store_policy_watchlist.json").write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "store": "google_play",
                                "url": "https://example.test/policy",
                                "status": "changed",
                                "content_hash": "hash",
                                "checked_at": "2026-07-30T00:00:00+00:00",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (data / "store_policy_alerts.json").write_text(
                json.dumps({"alerts": []}), encoding="utf-8"
            )
            (data / "store_policy_impact_tasks.json").write_text(
                json.dumps({"tasks": []}), encoding="utf-8"
            )
            with (data / "apps_registry.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["slug", "platforms"])
                writer.writeheader()
                writer.writerow({"slug": "tagweaver", "platforms": "ios|android"})

            with patch.object(analyze_store_policy_impact, "ROOT", root):
                self.assertEqual(analyze_store_policy_impact.main(), 0)
            tasks = json.loads(
                (data / "store_policy_impact_tasks.json").read_text()
            )["tasks"]

        self.assertEqual(tasks[0]["app_slug"], "tagweaver")
        self.assertEqual(tasks[0]["task_id"], "policy-google_play-tagweaver")


if __name__ == "__main__":
    unittest.main()
