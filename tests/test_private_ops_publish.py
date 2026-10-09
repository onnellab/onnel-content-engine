"""Security checks for public static ciphertext-only dashboard deployment."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "private_ops_publish.mjs"
PASSWORD = "UNIT-TEST-ONLY-not-a-real-password-1234567890"


def run(*args, password=PASSWORD):
    env = os.environ.copy()
    env["ONNELLAB_OPS_PASSWORD"] = password
    return subprocess.run(["node", str(SCRIPT), *map(str, args)], text=True,
                          capture_output=True, env=env, check=False)


class PrivateOpsPublishTest(unittest.TestCase):
    def test_all_html_pages_encrypted_and_extra_assets_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "generated"
            target = root / "public" / "ops"
            (source / "sales").mkdir(parents=True)
            (source / "index.html").write_text('<h1>SECRET FINANCIAL DASHBOARD</h1>', encoding="utf-8")
            (source / "sales" / "index.html").write_text('<p>PRIVATE REVENUE KRW 555</p>', encoding="utf-8")
            (source / "sw.js").write_text("PUBLIC OLD SERVICE WORKER", encoding="utf-8")
            (source / "icon.png").write_bytes(b"PNG-ICON")
            process = run("seal-site", source, target)
            self.assertEqual(process.returncode, 0, process.stderr)
            root_html = (target / "index.html").read_text()
            sub_html = (target / "sales" / "index.html").read_text()
            self.assertNotIn("SECRET FINANCIAL", root_html)
            self.assertNotIn("PRIVATE REVENUE", sub_html)
            self.assertIn("PBKDF2", root_html)
            self.assertIn("ops-sealed-data", sub_html)
            self.assertIn('name="robots"', root_html)
            self.assertEqual((target / "icon.png").read_bytes(), b"PNG-ICON")
            self.assertNotIn("PUBLIC OLD", (target / "sw.js").read_text())

    def test_encrypt_decrypt_ledger_and_refuse_wrong_password(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plain = root / "secret.json"
            encrypted = root / "safe.enc.json"
            restored = root / "restored.json"
            plain.write_text(json.dumps({"private_revenue": 12345, "app": "TagWeaver"}))
            self.assertEqual(run("seal-data", plain, encrypted).returncode, 0)
            self.assertNotIn("private_revenue", encrypted.read_text())
            rejected = run("unseal-data", encrypted, restored, password="incorrect-strong-password-999999")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(restored.exists())
            correct = run("unseal-data", encrypted, restored)
            self.assertEqual(correct.returncode, 0, correct.stderr)
            self.assertEqual(json.loads(restored.read_text()), json.loads(plain.read_text()))

    def test_weak_or_missing_password_rejected_before_target_written(self):
        with tempfile.TemporaryDirectory() as temp:
            plain = Path(temp) / "private.json"
            plain.write_text('{"secret": true}')
            target = Path(temp) / "private.enc.json"
            self.assertNotEqual(run("seal-data", plain, target, password="short").returncode, 0)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
