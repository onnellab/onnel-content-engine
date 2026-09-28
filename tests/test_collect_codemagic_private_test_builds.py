import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_codemagic_private_test_builds as module


class CollectCodemagicPrivateTestBuilds(unittest.TestCase):
    def run_with(self, requests, *, token=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requests_path = root / "requests.json"
            status_path = root / "status.json"
            requests_path.write_text(
                json.dumps({"requests": requests}), encoding="utf-8"
            )
            env = {} if token is None else {"CODEMAGIC_API_TOKEN": token}
            with patch.object(module, "REQUESTS_PATH", requests_path), \
                 patch.object(module, "STATUS_PATH", status_path), \
                 patch.dict(os.environ, env, clear=True):
                code = module.main()
            return code, json.loads(status_path.read_text(encoding="utf-8"))

    def test_no_requests_is_not_applicable_without_token(self):
        code, status = self.run_with([])
        self.assertEqual(0, code)
        self.assertEqual("not_applicable", status["state"])
        self.assertEqual([], status["records"])

    def test_only_completed_artifact_ready_requests_do_not_require_token(self):
        code, status = self.run_with([
            {
                "release_id": "REL-1",
                "status": "artifact_ready",
                "codemagic_build_id": "build-1",
            }
        ])
        self.assertEqual(0, code)
        self.assertEqual("not_applicable", status["state"])

    def test_active_request_without_token_is_token_missing(self):
        code, status = self.run_with([
            {
                "release_id": "REL-2",
                "status": "running",
                "codemagic_build_id": "build-2",
            }
        ])
        self.assertEqual(0, code)
        self.assertEqual("token_missing", status["state"])


if __name__ == "__main__":
    unittest.main()
