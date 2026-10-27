#!/usr/bin/env python3
"""Regenerate one unposted English primary X draft from a hash-bound correction.

No network, approval, posting, article/card generation, or scheduling effects.
The existing full generator is unchanged; verify the final draft again at posting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from publication_history import publication_history, publication_key
from publishing import social_generation_lock, social_process_lock, x_weighted_length


class CorrectionError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CorrectionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def regular(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise CorrectionError("invalid relative path")
    parts = Path(relative).parts
    if any(p in {".", ".."} for p in parts) or str(Path(relative)) != relative:
        raise CorrectionError("noncanonical path")
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise CorrectionError("symlink input")
    if not path.is_file():
        raise CorrectionError(f"missing regular file: {relative}")
    return path


def tree_bytes(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise CorrectionError("invalid social tree")
    result = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CorrectionError("symlink in social tree")
        if path.is_file():
            result[str(path.relative_to(root))] = path.read_bytes()
        elif not path.is_dir():
            raise CorrectionError("nonregular social entry")
    return result


def regenerate(root: Path, correction_path: Path, *, write=False) -> dict:
    root = root.resolve(strict=True)
    output = root / "generated/social"
    with social_generation_lock(output), social_process_lock(output):
        before = tree_bytes(output)
        correction_bytes = correction_path.read_bytes()
        spec = load_json(correction_path)
        fields = {"schema_version", "manual_key", "article_path", "article_sha256",
                  "canonical_url", "original_draft", "original_draft_sha256", "replacement_opening"}
        if not isinstance(spec, dict) or set(spec) != fields or spec["schema_version"] != 1:
            raise CorrectionError("invalid correction schema")
        key = spec["manual_key"]
        if not isinstance(key, str) or not re.fullmatch(r"TOPIC-\d{4}::x::en::x", key):
            raise CorrectionError("only one English primary X key is supported")
        original = spec["original_draft"]
        if not isinstance(original, str) or "\r" in original or not original.endswith("\n"):
            raise CorrectionError("original must be exact LF-terminated source")
        if digest(original.encode()) != spec["original_draft_sha256"]:
            raise CorrectionError("original digest mismatch")
        old_head, sep, tail = original.partition("\n\n")
        opening = spec["replacement_opening"]
        if (not sep or not old_head or not tail or not isinstance(opening, str)
                or not 30 <= len(opening) <= 200 or not opening.endswith(".")
                or any(c in opening for c in "\r\n") or "..." in opening or "…" in opening
                or "http" in opening.lower() or opening != opening.strip()):
            raise CorrectionError("invalid complete replacement opening")
        text = opening + "\n\n" + tail
        weighted = x_weighted_length(text.removesuffix("\n"))
        if weighted > 240:
            raise CorrectionError("corrected X text exceeds 240 weighted characters")
        manifest_path = regular(root, "generated/social/manifest.json")
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("posts"), list):
            raise CorrectionError("malformed manifest")
        canonical = lambda value: (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        if canonical(manifest) != before["manifest.json"]:
            raise CorrectionError("noncanonical manifest formatting; preserve rather than rewrite")
        posts = manifest["posts"]
        if any(not isinstance(item, dict) for item in posts):
            raise CorrectionError("malformed manifest item")
        keys = [publication_key(item) for item in posts]
        if len(keys) != len(set(keys)) or keys.count(key) != 1:
            raise CorrectionError("duplicate or missing manifest identity")
        item = posts[keys.index(key)]
        if (item.get("platform") != "x" or item.get("language") != "en"
                or item.get("template_id") != "x" or item.get("is_variant") is not False
                or item.get("source_status") != "published" or item.get("publish_after_canonical") is not False
                or item.get("status") not in {"draft", "failed"}
                or any(item.get(f) for f in ("approved_by", "approved_at", "post_id", "posted_url", "posted_at"))):
            raise CorrectionError("only unapproved, unposted published-source drafts may be corrected")
        guards = {}
        for rel in ("data/manual_publish_state.json", "data/remote_browser_publications.json"):
            guards[rel] = regular(root, rel).read_bytes()
            load_json(root / rel)
        if key in publication_history(root):
            raise CorrectionError("publication history forbids replacing this draft")
        category, slug = item.get("category"), item.get("slug")
        if (not isinstance(category, str) or not re.fullmatch(r"[a-z]+", category)
                or not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)):
            raise CorrectionError("invalid article identity")
        expected_article = f"generated/markdown/en/{category}/{slug}.md"
        expected_draft = f"generated/social/x/en/{category}/{slug}.txt"
        expected_url = f"https://onnellab.com/blog/en/{slug}/"
        if (spec["article_path"] != expected_article or item.get("draft_path") != expected_draft
                or spec["canonical_url"] != expected_url or item.get("canonical_url") != expected_url):
            raise CorrectionError("source identity mismatch")
        article = regular(root, expected_article)
        guards[expected_article] = article.read_bytes()
        if digest(guards[expected_article]) != spec["article_sha256"]:
            raise CorrectionError("article changed; correction requires fresh review")
        draft = regular(root, expected_draft)
        current = draft.read_bytes()
        if current not in (original.encode(), text.encode()):
            raise CorrectionError("draft changed; do not replace unreviewed bytes")
        item["weighted_length"] = weighted
        desired = dict(before)
        desired[str(draft.relative_to(output))] = text.encode()
        desired["manifest.json"] = canonical(manifest)
        result = {"manual_key": key, "draft_sha256": digest(text.encode()),
                  "posted_body_sha256": digest(text.removesuffix("\n").encode()),
                  "weighted_length": weighted, "changed": desired != before, "written": False}
        if not write or desired == before:
            return result
        stage = Path(tempfile.mkdtemp(prefix=".x-correction-stage-", dir=output.parent))
        backup = None
        committed = False
        try:
            shutil.copytree(output, stage, dirs_exist_ok=True)
            if tree_bytes(stage) != before:
                raise CorrectionError("social source changed during staging")
            for rel in ("manifest.json", str(draft.relative_to(output))):
                (stage / rel).write_bytes(desired[rel])
            if tree_bytes(stage) != desired:
                raise CorrectionError("staging changed outside selected draft and weight")
            if (tree_bytes(output) != before or correction_path.read_bytes() != correction_bytes
                    or any(regular(root, rel).read_bytes() != data for rel, data in guards.items())):
                raise CorrectionError("input changed before commit")
            backup = Path(tempfile.mkdtemp(prefix=".x-correction-backup-", dir=output.parent))
            backup.rmdir()
            output.rename(backup)
            try:
                stage.rename(output)
            except Exception as commit_error:
                try:
                    backup.rename(output)
                except Exception as rollback_error:
                    raise CorrectionError(
                        f"HOLD: replacement and rollback failed; original preserved at {backup}; "
                        f"commit={commit_error}; rollback={rollback_error}"
                    ) from rollback_error
                backup = None
                raise
            committed = True
            result["written"] = True
            return result
        finally:
            if stage.exists():
                shutil.rmtree(stage)
            if committed and backup is not None and backup.exists():
                shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("correction", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(regenerate(args.root, args.correction, write=args.write), sort_keys=True))
        return 0
    except (CorrectionError, ValueError, OSError) as exc:
        print(f"X correction failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
