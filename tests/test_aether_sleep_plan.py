from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_sleep_plan as sleep


class SleepPlanTests(unittest.TestCase):
    def test_plan_retains_scoped_budget_and_no_execution(self):
        plan = sleep.build_plan()
        self.assertEqual("0.24", plan["base_total_usd_estimate"])
        self.assertEqual("0.30", plan["all_in_cap_usd"])
        self.assertFalse(plan["paid_authorized"])
        self.assertFalse(plan["publication_authorized"])
        self.assertFalse(plan["all_in_total_verified"])
        self.assertIsNone(plan["publish_slots"])
        self.assertEqual(3, len(plan["drafts"]))
        self.assertEqual(0, plan["paid_retries"])

    def test_drafts_are_distinct_and_sleep_specific(self):
        drafts = sleep.build_plan()["drafts"]
        self.assertEqual(3, len({row["prompt"] for row in drafts}))
        for draft in drafts:
            self.assertIn("about 180 seconds", draft["prompt"])
            self.assertIn("not an adventure single", draft["prompt"])
            self.assertIn("not a claim of 30 minutes", draft["prompt"])

    def test_184_second_source_covers_target_with_11_repeats(self):
        timeline = sleep.repeat_timeline(184)
        self.assertEqual(11, timeline["repeat_count"])
        self.assertEqual(144, timeline["trim_tail_seconds"])
        self.assertEqual(176, timeline["segment_starts_seconds"][1])
        self.assertFalse(timeline["seam_reviewed"])
        self.assertFalse(timeline["rendered"])

    def test_180_second_source_covers_target(self):
        timeline = sleep.repeat_timeline(180)
        last = timeline["segment_starts_seconds"][-1]
        self.assertGreaterEqual(last + 180, 1800)
        self.assertEqual(1800, last + 180 - timeline["trim_tail_seconds"])

    def test_invalid_or_nonfinite_source_rejected(self):
        for source in (True, float("inf"), float("nan"), -1, 29, 185):
            with self.subTest(source=source), self.assertRaises(ValueError):
                sleep.repeat_timeline(source)

    def test_bad_crossfade_rejected(self):
        for fade in (0, -1, 90, float("nan")):
            with self.subTest(fade=fade), self.assertRaises(ValueError):
                sleep.repeat_timeline(180, crossfade_seconds=fade)


if __name__ == "__main__":
    unittest.main()
