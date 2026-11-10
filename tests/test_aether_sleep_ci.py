"""Sleep media regression dependencies must exist before offline tests."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class SleepMediaCI(unittest.TestCase):
    def test_each_supported_runner_installs_ffmpeg(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/unit-tests.yml").read_text())
        steps = workflow["jobs"]["test"]["steps"]
        for platform in ("Linux", "macOS"):
            with self.subTest(platform=platform):
                setup = "\n".join(step.get("run", "") for step in steps
                                  if step.get("if") == f"runner.os == '{platform}'")
                self.assertIn("ffmpeg", setup)

    def test_media_tools_are_checked_before_complete_suite(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/unit-tests.yml").read_text())
        steps = workflow["jobs"]["test"]["steps"]
        suite_index = next(i for i, step in enumerate(steps)
                           if step.get("run") == "python scripts/run_unit_tests.py")
        checks = "\n".join(step.get("run", "") for step in steps[:suite_index])
        self.assertIn("ffmpeg -version", checks)
        self.assertIn("ffprobe -version", checks)


if __name__ == "__main__":
    unittest.main()
