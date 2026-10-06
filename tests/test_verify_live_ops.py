import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_live_ops as module


class LiveOpsVerificationTests(unittest.TestCase):
    def fixture(self, *, legacy_status=404, live=None):
        expected = (
            '<html><head>'
            '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">'
            '<meta name="googlebot" content="noindex,nofollow,noarchive,nosnippet,noimageindex">'
            '<meta name="naverbot" content="noindex,nofollow,noarchive,nosnippet,noimageindex">'
            '<meta name="yeti" content="noindex,nofollow,noarchive,nosnippet,noimageindex">'
            '</head><body>ops</body></html>'
        ).encode()
        pages = {
            "https://onnellab.com/ops/": (200, expected if live is None else live),
            "https://onnellab.com/robots.txt": (
                200, b"User-agent: *\nDisallow: /ops/\nDisallow: /manual-publish/\n"
            ),
            "https://onnellab.com/sitemap.xml": (404, b""),
            "https://onnellab.com/sitemap-index.xml": (
                200,
                b'<sitemapindex><sitemap><loc>https://onnellab.com/sitemap-0.xml</loc></sitemap></sitemapindex>',
            ),
            "https://onnellab.com/sitemap-0.xml": (
                200,
                b'<urlset><url><loc>https://onnellab.com/</loc></url></urlset>',
            ),
            "https://onnellab.com/": (
                200, b'<html><a href="/apps/">Apps</a></html>'
            ),
            "https://onnellab.com/manual-publish/": (legacy_status, b""),
        }

        def fetcher(url, timeout=20):
            return pages[url]

        return expected, fetcher

    def test_verified_only_when_live_bytes_and_obscurity_checks_match(self):
        expected, fetcher = self.fixture()
        result = module.verify_once(expected, "https://onnellab.com", fetcher)
        self.assertEqual("verified", result["state"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(module.digest(expected), result["live_sha256"])

    def test_legacy_route_becoming_public_fails(self):
        expected, fetcher = self.fixture(legacy_status=200)
        result = module.verify_once(expected, "https://onnellab.com", fetcher)
        self.assertEqual("failed", result["state"])
        self.assertFalse(result["checks"]["legacy_route_absent"])

    def test_stale_live_ops_bytes_fail_even_with_correct_meta(self):
        expected, _ = self.fixture()
        stale = expected.replace(b">ops<", b">stale<")
        _, fetcher = self.fixture(live=stale)
        result = module.verify_once(expected, "https://onnellab.com", fetcher)
        self.assertEqual("failed", result["state"])
        self.assertFalse(result["checks"]["ops_exact_deployed_bytes"])

    def test_run_records_deployment_sha_for_freshness_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected.html"
            output = root / "verification.json"
            expected.write_bytes(b"ops")
            verified = {
                "state": "verified",
                "expected_sha256": module.digest(b"ops"),
                "live_sha256": module.digest(b"ops"),
                "checks": {"ops_exact_deployed_bytes": True},
                "http": {"ops": 200},
            }
            with patch.object(module, "verify_once", return_value=verified):
                payload = module.run(
                    expected, output, "https://onnellab.com", 1, 0,
                    deployment_sha="abc123",
                )
            self.assertEqual("abc123", payload["deployment_sha"])
            self.assertEqual("abc123", json.loads(output.read_text())["deployment_sha"])


if __name__ == "__main__":
    unittest.main()
