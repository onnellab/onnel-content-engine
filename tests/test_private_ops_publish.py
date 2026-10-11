"""Security checks for public static ciphertext-only dashboard deployment."""
import json
import os
import struct
import zlib
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "private_ops_publish.mjs"
PASSWORD = "UNIT-TEST-ONLY-not-a-real-password-1234567890"


def png_tile(size: int) -> bytes:
    """Valid tiny-compressed RGBA PNG fixture; use no imaging dependencies."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    pixel = bytes((250, 248, 245, 255))
    rows = (bytes((0,)) + pixel * size) * size
    return (bytes.fromhex("89504e470d0a1a0a") +
            chunk(b"IHDR", header) +
            chunk(b"IDAT", zlib.compress(rows)) +
            chunk(b"IEND", b""))


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
            brand = target.parent / "brand"
            brand.mkdir(parents=True)
            for size in (180, 192, 512):
                (brand / f"ops-mark-{size}.png").write_bytes(png_tile(size))
            process = run("seal-site", source, target)
            self.assertEqual(process.returncode, 0, process.stderr)
            root_html = (target / "index.html").read_text()
            sub_html = (target / "sales" / "index.html").read_text()
            self.assertNotIn("SECRET FINANCIAL", root_html)
            self.assertNotIn("PRIVATE REVENUE", sub_html)
            self.assertIn("PBKDF2", root_html)
            self.assertIn("ops-sealed-data", sub_html)
            self.assertIn('name="robots"', root_html)
            self.assertIn('rel="icon" href="/favicon.svg?v=20261008-open-monogram-v1"', root_html)
            self.assertIn('/ops/icon-180.png?v=20261008-open-monogram-v1', sub_html)
            self.assertEqual((target / "icon.png").read_bytes(), b"PNG-ICON")
            for size in (180, 192, 512):
                self.assertEqual((target / f"icon-{size}.png").read_bytes(),
                                 (brand / f"ops-mark-{size}.png").read_bytes())
            self.assertNotIn("PUBLIC OLD", (target / "sw.js").read_text())
            from validate_manual_publish_site import (
                DashboardArtifactError, validate_sealed_dashboard,
            )
            validate_sealed_dashboard(target / "index.html")
            (target / "icon-192.png").unlink()
            with self.assertRaisesRegex(DashboardArtifactError, "icon missing"):
                validate_sealed_dashboard(target / "index.html")

    def test_missing_or_corrupt_brand_source_preserves_existing_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "generated"
            source.mkdir()
            (source / "index.html").write_text("<main>PRIVATE</main>")
            target = root / "public" / "ops"
            target.mkdir(parents=True)
            previous = target / "previous.html"
            previous.write_text("PRIOR SAFE DEPLOYMENT")
            brand = target.parent / "brand"
            brand.mkdir()
            for size in (180, 192):
                (brand / f"ops-mark-{size}.png").write_bytes(png_tile(size))
            incomplete = run("seal-site", source, target)
            self.assertNotEqual(incomplete.returncode, 0)
            self.assertTrue(previous.exists())
            self.assertFalse((target / "index.html").exists())
            # Bad dimensions must likewise fail before deletion.
            (brand / "ops-mark-512.png").write_bytes(png_tile(180))
            corrupt = run("seal-site", source, target)
            self.assertNotEqual(corrupt.returncode, 0)
            self.assertIn("Invalid canonical Ops icon", corrupt.stderr)
            self.assertEqual(previous.read_text(), "PRIOR SAFE DEPLOYMENT")

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
