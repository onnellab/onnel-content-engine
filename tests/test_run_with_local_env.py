from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_with_local_env import parse_env_file, run_with_local_env  # noqa: E402


class RunWithLocalEnvTest(unittest.TestCase):
    def test_parse_env_file_reads_export_lines_and_skips_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "env.md"
            path.write_text(
                '\n'.join(
                    [
                        'export ONNELLAB_RELEASE_TOKEN="real-token"',
                        'export GITHUB_TOKEN="..."',
                        'X_REFRESH_TOKEN_FILE=".tokens/x-refresh-token"',
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                parse_env_file(path),
                {
                    "ONNELLAB_RELEASE_TOKEN": "real-token",
                    "X_REFRESH_TOKEN_FILE": ".tokens/x-refresh-token",
                },
            )

    def test_dry_run_prints_names_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "env.md"
            path.write_text('export ONNELLAB_RELEASE_TOKEN="secret-value"\n', encoding="utf-8")

            with patch("builtins.print") as mocked_print:
                result = run_with_local_env([], path, dry_run=True)

            self.assertEqual(result, 0)
            printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list)
            self.assertIn("ONNELLAB_RELEASE_TOKEN", printed)
            self.assertNotIn("secret-value", printed)


if __name__ == "__main__":
    unittest.main()
