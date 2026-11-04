"""Collect official public Lyria sources without authorizing production.

This supplies real source files for review; it does not create proof.json,
attest account agreement/billing, change a guard, accept terms or call a model.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/lyria-paid-evidence/public-sources"
URLS = {
    "model": "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/lyria/lyria-3?hl=en",
    "preview": "https://cloud.google.com/terms/genai-preview-products?hl=en",
    "terms": "https://cloud.google.com/terms/service-terms?hl=en",
    "pricing": "https://cloud.google.com/model-garden/pricing?hl=en",
}


class SourceError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_HTML_BYTES:
        raise SourceError("aether_public_source_html_too_large_or_empty")
    parser = VisibleText()
    try:
        parser.feed(raw.decode("utf-8"))
        parser.close()
    except (UnicodeError, ValueError):
        raise SourceError("aether_public_source_encoding_invalid") from None
    text = " ".join(" ".join(parser.parts).split()) + "\n"
    if not 0 < len(text.strip().encode("utf-8")) <= MAX_TEXT_BYTES:
        raise SourceError("aether_public_source_text_too_large_or_empty")
    return text


def fetch_document(url, *, opener=None):
    if url not in URLS.values():
        raise SourceError("aether_public_source_url_not_allowed")
    request = Request(url, headers={"Accept": "text/html", "Accept-Language": "en", "Accept-Encoding": "identity"})
    try:
        with (opener or build_opener(NoRedirect)).open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != url:
                raise SourceError("aether_public_source_response_mismatch")
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise SourceError("aether_public_source_content_type_invalid")
            raw = response.read(MAX_HTML_BYTES + 1)
    except HTTPError as error:
        raise SourceError(f"aether_public_source_http_{error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise SourceError("aether_public_source_network_failed") from None
    return raw, visible_text(raw)


def documented_permission(texts):
    model, preview = texts["model"], texts["preview"]
    permission = "Customers may elect to use it for production or commercial purposes, or disclose Generated Output to third-parties"
    if ("lyria-3-pro-preview" not in model or permission not in model
            or "subject to the obligations and restrictions described in the agreement" not in model):
        raise SourceError("aether_public_model_permission_unverified")
    prefix, suffix = "The Additional Use Restrictions above do not apply to", "In addition to these terms"
    if prefix not in preview or suffix not in preview.split(prefix, 1)[1]:
        raise SourceError("aether_public_preview_exception_unverified")
    exception = preview.split(prefix, 1)[1].split(suffix, 1)[0]
    if not re.search(r"\bLyria 3 Pro\b", exception) or "Pre-GA Offerings" not in exception:
        raise SourceError("aether_public_preview_exception_unverified")
    return True


def collect(root=ROOT, *, fetch=fetch_document):
    documents = {}
    for name, url in URLS.items():
        try:
            documents[name] = fetch(url)
        except SourceError as error:
            raise SourceError(f"{name}:{error}") from None
    permission = documented_permission({name: text for name, (_, text) in documents.items()})
    root = Path(root)
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise SourceError("aether_public_source_path_unsafe")
    missing = []
    current = root
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise SourceError("aether_public_source_directory_not_private")
    sources = {}
    for name, (raw, text) in documents.items():
        content = text.encode("utf-8")
        sha = hashlib.sha256(content).hexdigest()
        path = root / f"{name}-{sha}.txt"
        if path.is_symlink():
            raise SourceError("aether_public_source_path_unsafe")
        if path.exists():
            if not path.is_file() or path.read_bytes() != content:
                raise SourceError("aether_public_source_existing_bytes_changed")
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        sources[name] = {"path": path.name, "sha256": sha, "reference": URLS[name],
                         "representation": "complete_visible_text_whitespace_normalized",
                         "html_sha256": hashlib.sha256(raw).hexdigest(),
                         "html_bytes": len(raw), "text_bytes": len(content)}
    result = {"kind": "aether_public_provider_sources", "checked_at": datetime.now(timezone.utc).isoformat(),
              "model": "lyria-3-pro-preview", "provider_permission_documented": permission,
              "account_agreement_verified": False, "account_billing_verified": False,
              "generation_authorized": False, "proof_created": False, "sources": sources}
    content = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    receipt = root / ("collection-" + hashlib.sha256(content).hexdigest() + ".json")
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return {**result, "receipt": str(receipt)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["collect"])
    parser.parse_args()
    try:
        print(json.dumps(collect(), ensure_ascii=False, indent=2))
    except (SourceError, OSError) as error:
        reason = str(error) if isinstance(error, SourceError) else "aether_public_source_storage_failed"
        print(json.dumps({"state": "not_collected", "error": reason}))
        raise SystemExit(2)
