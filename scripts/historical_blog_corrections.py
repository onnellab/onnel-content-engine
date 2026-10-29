"""Hash-bound historical prose corrections consumed only by the canonical exporter.

No scheduling, new article IDs, or publishing transport. Engine and homepage
commits are separate boundaries: corrected engine sources may precede the site,
but all nine site destinations are preflighted and committed together.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from publication_locales import REQUIRED_PUBLICATION_LANGUAGES


class CorrectionError(ValueError):
    pass


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def safe_file(root: Path, relative: str) -> Path:
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or not part.parts:
        raise CorrectionError("unsafe correction path")
    root = root.resolve()
    path = root / part
    if any((root / Path(*part.parts[:i])).is_symlink() for i in range(1, len(part.parts) + 1)):
        raise CorrectionError("linked correction path")
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise CorrectionError(f"missing correction source: {relative}")
    return path


def prepare_historical_corrections(project_root: Path, homepage_repo: Path, reviewed_root: Path | None = None):
    """Return updates and observed bytes; no destination is ever written here."""
    reviewed_root = reviewed_root or project_root
    registry = project_root / "data/historical_blog_corrections.json"
    if not registry.exists():
        return {}, {}
    config = json.loads(safe_file(project_root, "data/historical_blog_corrections.json").read_text())
    if config.get("schema") != "onnellab.historical-blog-corrections.v1":
        raise CorrectionError("unknown correction registry schema")
    updates, expected = {}, {}
    for entry in config["corrections"]:
        if (entry.get("id") != "tagweaver-multidisc-ios-save-251"
                or entry.get("slug") != "number-tracks-multi-disc-mp3-album"
                or entry.get("category") != "music"
                or entry.get("proposal_path") != "preview/tagweaver-album-artists/multidisc-ios-save-correction.proposed.json"
                or entry.get("proposal_blob_sha") != "912a25c5fd07199d02919c791d3d5eabe21f4b83"
                or entry.get("manuscript_directory") != "preview/tagweaver-multidisc-ios-save"):
            raise CorrectionError("correction is outside the approved allowlist")
        slug, category = entry["slug"], entry["category"]
        if not all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) for value in (slug, category)):
            raise CorrectionError("invalid correction identity")
        if entry.get("state") != "approved" or not entry.get("approval_reference"):
            raise CorrectionError("correction not approved")
        proposal_bytes = safe_file(reviewed_root, entry["proposal_path"]).read_bytes()
        if blob_sha(proposal_bytes) != entry["proposal_blob_sha"]:
            raise CorrectionError("changed correction proposal")
        proposal = json.loads(proposal_bytes)
        rows = proposal["corrections"]
        site_rows = [r for r in rows if r["repository"] == "onnellab/onnellab.github.io"]
        engine_rows = [r for r in rows if r["repository"] == "onnellab/onnel-content-engine"]
        if len(rows) != 11 or len(site_rows) != 9 or len(engine_rows) != 2:
            raise CorrectionError("correction must include nine site and two canonical sources")
        if {r["locale"] for r in site_rows} != set(REQUIRED_PUBLICATION_LANGUAGES) or {r["locale"] for r in engine_rows} != {"en", "ko"}:
            raise CorrectionError("incomplete correction locales")
        corrected_by_locale = {}
        for row in site_rows:
            locale = row["locale"]
            destination_path = f"src/content/blog/{locale}/{slug}.md"
            if row["path"] != destination_path:
                raise CorrectionError("out-of-scope correction destination")
            manuscript = safe_file(reviewed_root, f'{entry["manuscript_directory"]}/{locale}.md').read_bytes()
            if blob_sha(manuscript) != entry["manuscript_blob_shas"][locale]:
                raise CorrectionError("changed reviewed manuscript")
            old, new = row["old_sentence"].encode(), row["replacement_text"].encode()
            if not old or not new or old == new or manuscript.count(new) != 1 or old in manuscript:
                raise CorrectionError("ambiguous correction replacement")
            # Reconstruct and hash the entire original. This enforces unchanged
            # frontmatter, date, URLs, links, assets, headings and all other bytes.
            original = manuscript.replace(new, old, 1)
            if blob_sha(original) != row["source_blob_sha"]:
                raise CorrectionError("correction changes more than approved prose")
            if new in manuscript.split(b"\n---\n", 2)[0]:
                raise CorrectionError("correction must not change frontmatter")
            destination = safe_file(homepage_repo, destination_path)
            current = destination.read_bytes()
            if current not in (original, manuscript):
                raise CorrectionError(f"stale correction target: {destination_path}")
            if destination in expected:
                raise CorrectionError("duplicate correction destination")
            expected[destination] = current
            updates[destination] = manuscript
            corrected_by_locale[locale] = manuscript
        for row in engine_rows:
            locale = row["locale"]
            site_row = next(r for r in site_rows if r["locale"] == locale)
            if any(row[key] != site_row[key] for key in ("source_blob_sha", "old_sentence", "replacement_text")):
                raise CorrectionError("canonical and site correction disagree")
            if row["path"] != f"generated/markdown/{locale}/{category}/{slug}.md":
                raise CorrectionError("out-of-scope canonical source")
            if safe_file(project_root, row["path"]).read_bytes() != corrected_by_locale[locale]:
                raise CorrectionError("canonical source must already match reviewed correction")
    return updates, expected
