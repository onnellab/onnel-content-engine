"""Daily Aether orchestration tests. No local production or network execution."""
from datetime import datetime
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_daily_local as module


class CompilationSlot(unittest.TestCase):
    def test_asset_registration_failure_blocks_before_compilation_worker(self):
        report = {"blockers": [], "steps": []}
        blocked = json.dumps({
            "status": "blocked",
            "error": "aether_asset_approval_incomplete",
        })
        now = datetime(2026, 9, 27, 6, 20, tzinfo=ZoneInfo("Asia/Seoul"))
        with patch.object(module, "run_step", return_value=(2, blocked, "")) as run:
            module.run_compilation_slot(report, now)

        self.assertEqual("aether_asset_approval_incomplete", report["compilation_slot"]["error"])
        self.assertEqual(["aether_asset_approval_incomplete"], report["blockers"])
        self.assertEqual(1, run.call_count)
        self.assertTrue(any(
            str(arg).endswith("aether_compilation_assets.py")
            for arg in run.call_args.args[2]
        ))


if __name__ == "__main__":
    unittest.main()
