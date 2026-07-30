from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_crash_source_config import validate


class CrashSourceConfigTest(unittest.TestCase):
    def test_repository_config_covers_every_release_app(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_missing_coverage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "app_release_config.csv").write_text(
                "app_id,app_slug,repository,artifact_pattern,notes\nAPP-1,one,o/r,p,n\n",
                encoding="utf-8",
            )
            for name, key in (
                ("crashlytics_crash_sources.json", "apps"),
                ("sentry_crash_sources.json", "projects"),
            ):
                (data / name).write_text(json.dumps({key: [], "coverage": []}), encoding="utf-8")

            errors = validate(root)

        self.assertTrue(any("missing coverage for one" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
