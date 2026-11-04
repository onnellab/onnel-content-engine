"""Public-source collection regressions; no credentials or production calls."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from urllib.error import URLError
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_lyria_rights as module

MODEL_TEXT = (
    "lyria-3-pro-preview Customers may elect to use it for production or commercial purposes, "
    "or disclose Generated Output to third-parties subject to the obligations and restrictions "
    "described in the agreement"
)
PREVIEW_TEXT = (
    "The Additional Use Restrictions above do not apply to Gemini Enterprise Agent Platform "
    "when used with these Pre-GA Offerings: Lyria 3 Pro In addition to these terms other terms apply."
)


PRICE_TEXT = (
    "Price (USD) Lyria 3 Pro Full song music generation "
    "Lyria 3 Pro creates full-length musical compositions from multimodal inputs "
    "Text, Image Full song $0.08 / 1 count Lyria 3 30 second music clip generation"
)


class SourcesTests(unittest.TestCase):
    def response(self, raw, url=None):
        result = io.BytesIO(raw)
        result.status = 200
        result.headers = {"Content-Type": "text/html; charset=utf-8"}
        result.geturl = lambda: url or module.URLS["model"]
        return result

    def test_large_framework_html_is_not_a_network_failure(self):
        raw = b"<html><script>" + b"x" * (2 * 1024 * 1024 + 1) + b"</script><main>actual document</main></html>"
        opener = SimpleNamespace(open=lambda *a, **k: self.response(raw))
        downloaded, text = module.fetch_document(module.URLS["model"], opener=opener)
        self.assertEqual(raw, downloaded)
        self.assertEqual("actual document\n", text)
        self.assertLess(len(text), module.MAX_TEXT_BYTES)

    def test_oversize_html_has_specific_error_and_stays_bounded(self):
        with patch.object(module, "MAX_HTML_BYTES", 20):
            with self.assertRaisesRegex(module.SourceError, "html_too_large"):
                module.visible_text(b"x" * 21)

    def test_visible_text_limit_is_distinct(self):
        with patch.object(module, "MAX_TEXT_BYTES", 10):
            with self.assertRaisesRegex(module.SourceError, "text_too_large"):
                module.visible_text(b"<main>" + b"x" * 11 + b"</main>")

    def test_untrusted_url_is_rejected_without_request(self):
        with patch.object(module, "build_opener") as opener:
            with self.assertRaisesRegex(module.SourceError, "url_not_allowed"):
                module.fetch_document("https://example.invalid/terms")
            opener.assert_not_called()

    def test_actual_transport_failure_is_classified_separately(self):
        def fail(*a, **k):
            raise URLError("fixture")
        with self.assertRaisesRegex(module.SourceError, "network_failed"):
            module.fetch_document(module.URLS["model"], opener=SimpleNamespace(open=fail))

    def test_redirect_content_type_and_encoding_do_not_become_permission(self):
        response = self.response(b"<main>x</main>", "https://example.invalid/redirect")
        with self.assertRaisesRegex(module.SourceError, "response_mismatch"):
            module.fetch_document(module.URLS["model"], opener=SimpleNamespace(open=lambda *a, **k: response))
        with self.assertRaisesRegex(module.SourceError, "encoding_invalid"):
            module.visible_text(b"\xff")

    def test_explicit_model_and_exception_are_both_required(self):
        texts = {"model": MODEL_TEXT, "preview": PREVIEW_TEXT}
        self.assertTrue(module.documented_permission(texts))
        for key, value in (("model", "lyria-3-pro-preview"), ("preview", PREVIEW_TEXT.replace("Lyria 3 Pro", "Other model"))):
            with self.subTest(key=key), self.assertRaises(module.SourceError):
                module.documented_permission({**texts, key: value})

    def test_real_source_bytes_and_receipt_never_create_active_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            proof = parent / "proof.json"
            proof.write_bytes(b"existing proof must not change")
            originals = {name: ("<main>" + (MODEL_TEXT if name == "model" else PREVIEW_TEXT if name == "preview" else PRICE_TEXT if name == "pricing" else "Fixture public document") + "</main>").encode() for name in module.URLS}
            def fetch(url):
                name = next(name for name, source in module.URLS.items() if source == url)
                return originals[name], module.visible_text(originals[name])
            result = module.collect(parent / "public-sources", fetch=fetch)
            self.assertTrue(result["provider_permission_documented"])
            for key in ("generation_authorized", "account_billing_verified", "account_agreement_verified", "proof_created"):
                self.assertFalse(result[key])
            for name, source in result["sources"].items():
                file = parent / "public-sources" / source["path"]
                self.assertEqual(source["sha256"], hashlib.sha256(file.read_bytes()).hexdigest())
                self.assertEqual(source["html_sha256"], hashlib.sha256(originals[name]).hexdigest())
                self.assertEqual(0, file.stat().st_mode & 0o077)
            self.assertEqual(b"existing proof must not change", proof.read_bytes())
            self.assertEqual("aether_public_provider_sources", json.loads(Path(result["receipt"]).read_text())["kind"])

    def test_price_requires_exact_usd_model_unit_and_unambiguous_row(self):
        self.assertEqual("0.08", module.documented_price(PRICE_TEXT))
        for text in (PRICE_TEXT.replace("USD", "CAD"),
                     PRICE_TEXT.replace("/ 1 count", "/ 100 count"),
                     PRICE_TEXT.replace("Lyria 3 Pro", "Other model"),
                     PRICE_TEXT + " " + PRICE_TEXT):
            with self.subTest(text=text), self.assertRaises(module.SourceError):
                module.documented_price(text)

    def test_failed_collection_does_not_create_partial_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "sources"
            with self.assertRaises(module.SourceError):
                module.collect(root, fetch=lambda url: (b"missing", "missing"))
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
