#!/usr/bin/env python3
"""Validate the unchanged TagWeaver draft bundle in an isolated copy; never publish."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from prepare_research_preview import (
    COPY_ROOTS, MAX_NATIVE_BYTES, digest, read_json, write_json,
    source_inventory, copy_source, safe_native_path, read_native_bytes,
    unique_native_object, native_entry,
)
ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es")
SLUG = "consistent-album-artist-names"
CATEGORY = "music"
TOPIC_ID = "TOPIC-0039"
RELATED_APP = "TagWeaver"
PREVIEW_DIRECTORY = "preview/tagweaver-album-artists"
MARKER = ".tagweaver-album-artists-disposable-stage.json"
NATIVE_MANIFEST = "native-output-manifest.json"
NATIVE_MANIFEST_PREFIX = "TAGWEAVER_NATIVE_OUTPUT_MANIFEST "
GATES = (
    ("validate_topics.py",),
    ("validate_foundation.py",),
    ("evaluate_all_articles.py",),
    ("check_nine_language_publication.py",),
    ("check_content_supply.py", "--require-healthy", "--minimum-ideas", "8"),
)
REVIEWED_BLOBS = {
    "en": "af5023281da5168cedea7aecfef358dddf9534f1",
    "pt-BR": "362f19a71dc492c641ad5e9d1696f1efde4c9d9f",
    "de": "eca448f36491bb56f118502a706e101a8691d8d6",
    "ko": "d42c002343c9c8422c3efd02357f3390c01d4c25",
    "ja": "12eedc391ddce89161f5f12cfc3c285f1623f5b1",
    "fr": "d140f2688370385042b1ca1201c431398605b7b2",
    "zh-Hans": "f939947c649d46d9bff56875534037bfa08ddd5e",
    "es": "055fa43f5aa9a0b1e661902cd2c3c3b73387a1dd",
    "zh-Hant": "544100d95b0590cd3b09e876c08f0c4929115877"
}

APPROVED_IDEA_SEED = {
    "status": "idea",
    "category": "music",
    "primary_language": "en",
    "slug": "distinguish-recording-date-from-release-date",
    "primary_question": "How can I distinguish a recording date from a release date when documenting music metadata?",
    "working_title": "Distinguish Recording Dates from Release Dates in Music Metadata",
    "priority": "normal",
    "search_intent": "workflow",
    "related_apps": "",
    "primary_keyword": "recording date versus release date",
    "secondary_keywords": "music metadata dates|release booklet|official release information",
    "evergreen": "true",
    "source_type": "editorial",
    "review_required": "true",
    "notes": "Product-neutral editorial hypothesis: compare official release information and the booklet, record the evidence and keep an unknown recording or release date unknown rather than estimating it. No app-capability, search-demand or ranking claim. Separate from album/artist naming, duplicate recordings and multi-disc numbering. ID remains unassigned until normal allocation."
}

def bounded_json(directory, filename, limit=100_000):
    path = safe_native_path(directory, filename, required=True)
    return json.loads(read_native_bytes(path, limit).decode("utf-8"),
                      object_pairs_hook=unique_native_object)

def require_reviewed_section_headings(body, locale):
    from article_localization import tagweaver_section_aliases
    from evaluate_article import SECTION_ALIASES, _h2_heading_positions
    headings = _h2_heading_positions(body)
    for key, approved in tagweaver_section_aliases(locale).items():
        matching = [heading for heading, _ in headings if heading in SECTION_ALIASES[key]]
        if len(matching) != 1 or matching[0] not in approved:
            raise ValueError(f"Exactly one reviewed {key} heading required: {locale}")


def validate_drafts(directory):
    manifest = bounded_json(directory, "manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError("Unexpected authored draft manifest")
    expected = {
        "schema": "onnellab.editorial-draft.v1",
        "state": "DRAFT_UNVALIDATED_NOT_QUEUED",
        "slug": SLUG, "category": CATEGORY,
        "existing_english_topic_id": TOPIC_ID,
        "locales": list(LOCALES), "related_apps": [RELATED_APP],
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Unexpected authored draft identity or state")
    if (manifest.get("queue_modified") is not False or
            manifest.get("counterpart_topic_ids_reserved") is not False or
            manifest.get("scheduled_at") is not None or
            manifest.get("publication_receipt") is not False):
        raise ValueError("TagWeaver preview must remain unqueued and unpublished")
    verification = manifest.get("verification")
    if not isinstance(verification, dict) or verification.get("final_blobs") != REVIEWED_BLOBS:
        raise ValueError("Reviewed draft blob inventory mismatch")
    drafts = {}
    required = {"locale", "title", "description", "question", "primary_keyword",
                "secondary_keywords", "short_answer", "body", "image"}
    for locale in LOCALES:
        path = safe_native_path(directory, f"{locale}.json", required=True)
        raw = read_native_bytes(path, 100_000)
        if native_entry(f"{locale}.json", raw)["git_blob_sha1"] != REVIEWED_BLOBS[locale]:
            raise ValueError(f"Reviewed source blob mismatch: {locale}")
        draft = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_native_object)
        if not isinstance(draft, dict) or set(draft) != required or draft["locale"] != locale:
            raise ValueError("Draft schema/locale mismatch")
        if any(not isinstance(draft[key], str) or not draft[key].strip()
               for key in required - {"image"}):
            raise ValueError("Empty draft field")
        if not draft["body"].startswith("# " + draft["title"] + "\n"):
            raise ValueError("Draft title/H1 mismatch")
        image = draft["image"]
        if not isinstance(image, dict) or set(image) != {"title", "subtitle", "message", "steps"}:
            raise ValueError("Image copy schema mismatch")
        if any(not isinstance(image[key], str) or not image[key].strip()
               for key in ("title", "subtitle", "message")):
            raise ValueError("Image copy text must be non-empty")
        steps = image["steps"]
        if (not isinstance(steps, list) or len(steps) != 4 or
                any(not isinstance(pair, list) or len(pair) != 2 or
                    any(not isinstance(text, str) or not text.strip() for text in pair)
                    for pair in steps)):
            raise ValueError("Exactly four image heading/detail pairs required")
        require_reviewed_section_headings(draft["body"], locale)
        drafts[locale] = draft
    return drafts

def stage_topics(stage, drafts):
    from topic_management import TopicStore
    store = TopicStore(stage / "data/topics.csv", apps_path=stage / "data/apps_registry.csv",
                       mirror_path=stage / "topics/topics.csv")
    rows = store.read()
    matches = [r for r in rows if r["slug"] == SLUG]
    if len(matches) != 1 or matches[0]["id"] != TOPIC_ID or matches[0]["status"] != "idea":
        raise ValueError("Candidate is reserved, duplicated or no longer an idea")
    if (matches[0]["primary_language"] != "en" or matches[0]["category"] != CATEGORY or
            matches[0]["related_apps"] != RELATED_APP or any(matches[0][key] for key in
                ("canonical_path", "scheduled_at", "published_at", "published_url"))):
        raise ValueError("Unexpected candidate identity")
    seeds = bounded_json(stage / PREVIEW_DIRECTORY, "idea_seeds.json")
    if seeds != [APPROVED_IDEA_SEED]:
        raise ValueError("Exactly the approved, unassigned editorial seed required")
    if any(row["slug"] == APPROVED_IDEA_SEED["slug"] for row in rows):
        raise ValueError("Reviewed editorial seed already exists; do not duplicate")
    if set(drafts) != set(LOCALES):
        raise ValueError("Exactly nine draft locales required")
    original_other = [dict(r) for r in rows if r["id"] != TOPIC_ID]
    candidates = []
    for locale in LOCALES:
        d = drafts[locale]
        fields = {
            "category": CATEGORY, "primary_language": locale, "slug": SLUG,
            "primary_question": d["question"], "working_title": d["title"],
            "priority": "normal", "search_intent": "workflow", "related_apps": RELATED_APP,
            "primary_keyword": d["primary_keyword"], "secondary_keywords": d["secondary_keywords"],
            "evergreen": "true", "source_type": "editorial", "review_required": "true",
            "canonical_path": f"generated/markdown/{locale}/{CATEGORY}/{SLUG}.md",
            "notes": "Authored album and artist tag workflow; official store sources bound in the reviewed draft. Editorial keyword hypothesis. Disposable validation only.",
        }
        if locale == "en":
            row = store.edit(TOPIC_ID, fields)
        else:
            row = store.add(fields)
        for status in ("approved", "research", "outline", "draft"):
            row = store.edit(row["id"], {"status": status})
        candidates.append(row)
    seed_rows = [store.add(seed) for seed in seeds]
    final_by_id = {r["id"]: r for r in store.read()}
    if any(final_by_id[r["id"]] != r for r in original_other):
        raise ValueError("Unrelated topic rows changed")
    return store, candidates, seed_rows

def materialize_candidates(stage, drafts, candidates, store):
    # Check every locale before the first Markdown/spec/image write.
    if set(drafts) != set(LOCALES):
        raise ValueError("Exactly nine draft locales required")
    for locale in LOCALES:
        require_reviewed_section_headings(drafts[locale]["body"], locale)
    from generate_image_spec import generate_image_spec
    from generate_image_assets import generate_image_asset
    from generate_internal_links import generate_internal_links
    for row in candidates:
        d = drafts[row["primary_language"]]
        locale = row["primary_language"]
        metadata = {
            "title": d["title"], "card_title": d["title"], "slug": SLUG,
            "category": CATEGORY, "language": locale, "description": d["description"],
            "status": "review", "topic_id": row["id"], "search_intent": "workflow",
            "primary_keyword": d["primary_keyword"], "secondary_keywords": d["secondary_keywords"],
            "tags": d["primary_keyword"], "short_answer": d["short_answer"],
            "related_apps": RELATED_APP,
            "canonical_url": f"https://onnellab.com/blog/{locale.lower()}/{SLUG}/",
        }
        markdown = "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in metadata.items()) + "---\n\n" + d["body"].rstrip() + "\n"
        path = stage / row["canonical_path"]
        if path.exists():
            raise ValueError("Candidate Markdown collision")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        spec_path = generate_image_spec(path)
        spec = read_json(spec_path)
        image = d["image"]
        spec["editorial_workflow"] = {
            "subtitle": image["subtitle"], "message": image["message"],
            "description": d["short_answer"], "steps": image["steps"],
        }
        spec["workflow_diagrams"][0]["title"] = image["title"]
        spec["workflow_diagrams"][0]["steps"] = [pair[0] for pair in image["steps"]]
        spec["required_infographic_types"] = [{
            "id": "workflow-primary", "type": "workflow", "required": True,
            "question_answered": d["question"],
            "structure": [pair[0] for pair in image["steps"]],
            "notes": "Explain release identification, shared fields, sample saving and verification; not an application screenshot or a player-grouping guarantee.",
        }]
        spec["comparison_diagrams"] = []
        spec["screenshot_requirements"]["required"] = False
        spec["screenshot_requirements"]["reason"] = "The visual explains an editorial metadata workflow, not an application interface."
        write_json(spec_path, spec)
        generate_image_asset(spec_path)
    # All counterpart Markdown must exist before link and review generation.
    for row in candidates:
        generate_internal_links(row["id"])
    final = {r["id"]: r for r in store.read()}
    if any(final[r["id"]]["status"] != "review" or final[r["id"]]["scheduled_at"] for r in candidates):
        raise ValueError("Candidate must remain unscheduled review")
    return [final[r["id"]] for r in candidates]

def run_gates(stage, output):
    for index, arguments in enumerate(GATES, 1):
        command = [sys.executable, str(stage / "scripts" / arguments[0]), *arguments[1:]]
        result = subprocess.run(command, cwd=stage, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        (output / f"{index:02d}-{arguments[0]}.log").write_text(result.stdout, encoding="utf-8")
        if result.returncode:
            diagnostics = output / "failed-candidate-reviews"
            for locale in LOCALES:
                review = stage / f"generated/reviews/{locale}/{CATEGORY}/{SLUG}/review.json"
                if review.is_file() and not review.is_symlink():
                    diagnostics.mkdir(exist_ok=True)
                    (diagnostics / f"{locale}.json").write_bytes(review.read_bytes())
            print(result.stdout, file=sys.stderr, flush=True)
            raise ValueError(f"Native gate failed: {arguments[0]} (see retained log)")


def native_output_paths():
    paths = []
    for locale in LOCALES:
        paths.extend((
            f"generated/markdown/{locale}/{CATEGORY}/{SLUG}.md",
            f"generated/images/{locale}/{CATEGORY}/{SLUG}/image_spec.json",
            f"generated/metadata/{locale}/{CATEGORY}/{SLUG}/internal_links.json",
            f"generated/reviews/{locale}/{CATEGORY}/{SLUG}/review.json",
            *(f"generated/assets/blog/{locale}/{SLUG}/{name}" for name in
              ("workflow-diagram.svg", "workflow-diagram.png", "social-card.svg", "social-card.png")),
        ))
    if len(paths) != 72 or len(set(paths)) != 72:
        raise ValueError("Exactly 72 distinct native output paths required")
    return tuple(paths)

def validate_native_manifest(manifest):
    expected = native_output_paths()
    if (not isinstance(manifest, dict) or
            set(manifest) != {"schema", "slug", "locales", "files"} or
            type(manifest["schema"]) is not int or manifest["schema"] != 1 or
            manifest["slug"] != SLUG or manifest["locales"] != list(LOCALES)):
        raise ValueError("Invalid native manifest identity")
    entries = manifest["files"]
    if not isinstance(entries, list) or len(entries) != 72:
        raise ValueError("Native manifest requires exactly 72 entries")
    seen = set()
    total = 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "byte_length", "sha256", "git_blob_sha1"}:
            raise ValueError("Invalid native manifest entry")
        relative = entry["path"]
        if not isinstance(relative, str) or relative not in expected or relative in seen:
            raise ValueError("Duplicate or unexpected native manifest path")
        seen.add(relative)
        size = entry["byte_length"]
        if type(size) is not int or not 0 <= size <= MAX_NATIVE_BYTES:
            raise ValueError("Invalid native manifest byte length")
        total += size
        for key, length in (("sha256", 64), ("git_blob_sha1", 40)):
            value = entry[key]
            if not isinstance(value, str) or len(value) != length or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Invalid native manifest digest")
    if seen != set(expected) or total > 100_000_000:
        raise ValueError("Native manifest path set or total size mismatch")
    return manifest

def verified_native_manifest(output):
    manifest_path = safe_native_path(output, NATIVE_MANIFEST, required=True)
    raw = read_native_bytes(manifest_path, 100_000)
    manifest = validate_native_manifest(json.loads(raw.decode("utf-8"), object_pairs_hook=unique_native_object))
    artifacts = output / "artifacts"
    if artifacts.is_symlink() or not artifacts.is_dir():
        raise ValueError("Missing or symlink native artifacts root")
    actual = set()
    for path in artifacts.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink native artifact")
        if path.is_file():
            actual.add(path.relative_to(artifacts).as_posix())
            if len(actual) > 72:
                raise ValueError("Unexpected native artifact count")
        elif not path.is_dir():
            raise ValueError("Invalid native artifact type")
    if actual != set(native_output_paths()):
        raise ValueError("Native artifact path set mismatch")
    for entry in manifest["files"]:
        path = safe_native_path(output, "artifacts/" + entry["path"], required=True)
        if native_entry(entry["path"], read_native_bytes(path)) != entry:
            raise ValueError(f"Native artifact fingerprint mismatch: {entry['path']}")
    return manifest

def collect(stage, output, candidates, seeds):
    # The native read-only gate also recomputes current fingerprints and requires
    # every mandatory check. It imports the existing score verifier, never its CLI.
    from check_nine_language_publication import check_reviewed_candidates
    check_reviewed_candidates(stage / "data/topics.csv")
    validate_drafts(stage / PREVIEW_DIRECTORY)
    expected = native_output_paths()
    if (len(candidates) != len(LOCALES) or
            {row["primary_language"] for row in candidates} != set(LOCALES)):
        raise ValueError("Exactly nine distinct native candidate locales required")
    for row in candidates:
        canonical = f"generated/markdown/{row['primary_language']}/{CATEGORY}/{SLUG}.md"
        if (row["canonical_path"] != canonical or row["slug"] != SLUG or
                row["category"] != CATEGORY or row["related_apps"] != RELATED_APP or
                row["status"] != "review" or any(row[key] for key in
                    ("scheduled_at", "published_at", "published_url"))):
            raise ValueError("Unexpected native candidate Markdown path")
    aliases = {}
    for locale in LOCALES:
        base = f"generated/assets/blog/{locale}/{SLUG}/"
        for suffix in ("svg", "png"):
            aliases[base + "social-card." + suffix] = base + "workflow-diagram." + suffix
    artifacts = output / "artifacts"
    if artifacts.exists() or artifacts.is_symlink():
        raise ValueError("Native artifacts destination collision")
    # Validate every source, social-alias destination, and evidence destination
    # before the first copy. A late invalid locale must not mutate early aliases.
    for relative in expected:
        safe_native_path(stage, relative, required=relative not in aliases)
        safe_native_path(output, "artifacts/" + relative, absent=True)
    for name in ("candidate.json", "candidate.sha256", "candidate-topic-rows.json", NATIVE_MANIFEST):
        safe_native_path(output, name, absent=True)
    planned_bytes = 0
    for relative in expected:
        src = safe_native_path(stage, aliases.get(relative, relative), required=True)
        size = src.stat().st_size
        if size > MAX_NATIVE_BYTES:
            raise ValueError(f"Native output exceeds size limit: {relative}")
        planned_bytes += size
    if planned_bytes > 100_000_000:
        raise ValueError("Native outputs exceed total size limit")
    for destination, source in aliases.items():
        src = safe_native_path(stage, source, required=True)
        target = safe_native_path(stage, destination)
        shutil.copyfile(src, target)
    files = []
    entries = []
    total = 0
    for relative in expected:
        src = safe_native_path(stage, relative, required=True)
        raw = read_native_bytes(src)
        total += len(raw)
        if total > 100_000_000:
            raise ValueError("Native outputs exceed total size limit")
        entry = native_entry(relative, raw)
        target = safe_native_path(output, "artifacts/" + relative, absent=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = safe_native_path(output, "artifacts/" + relative, absent=True)
        with target.open("xb") as stream:
            stream.write(raw)
        entries.append(entry)
        if relative.endswith(".md") or relative.endswith(".svg"):
            files.append({"path": relative, "content": raw.decode("utf-8"), "sha256": entry["sha256"]})
    bundle = {"schema": 1, "state": "UNSCHEDULED_PREVIEW_ONLY", "slug": SLUG,
              "locales": list(LOCALES), "files": files}
    write_json(output / "candidate.json", bundle)
    (output / "candidate.sha256").write_text(digest((output / "candidate.json").read_bytes()) + "  candidate.json\n")
    from prepare_blog_preview import validate_bundle
    validate_bundle(output / "candidate.json")
    write_json(output / "candidate-topic-rows.json", {"candidates": candidates, "idea_seeds": seeds,
                                                    "ids_reserved": False, "live_queue_modified": False})
    manifest = validate_native_manifest({"schema": 1, "slug": SLUG, "locales": list(LOCALES), "files": entries})
    write_json(output / NATIVE_MANIFEST, manifest)
    verified_native_manifest(output)

def stage_worker():
    marker = ROOT / MARKER
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("Worker requires a disposable stage marker")
    settings = read_json(marker)
    original = Path(settings["source"]).resolve()
    if ROOT == original or ROOT.is_relative_to(original):
        raise ValueError("Worker cannot run in or beneath the source checkout")
    output = Path(settings["output"])
    if output.resolve() != original / "preview-evidence/tagweaver-album-artists":
        raise ValueError("Unexpected evidence destination")
    drafts = validate_drafts(ROOT / "preview/tagweaver-album-artists")
    store, candidates, seeds = stage_topics(ROOT, drafts)
    candidates = materialize_candidates(ROOT, drafts, candidates, store)
    run_gates(ROOT, output)
    collect(ROOT, output, candidates, seeds)

def prepare(source=ROOT):
    if source.is_symlink():
        raise ValueError("Direct source symlink forbidden")
    source = source.resolve()
    evidence_parent = source / "preview-evidence"
    output = evidence_parent / "tagweaver-album-artists"
    if evidence_parent.is_symlink() or output.exists() or output.is_symlink():
        raise ValueError("Evidence destination collision or symlink")
    validate_drafts(source / PREVIEW_DIRECTORY)
    before = source_inventory(source)
    output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="onnellab-tagweaver-album-artists-preview-") as temporary:
            stage = Path(temporary)
            copy_source(source, stage, before)
            write_json(stage / MARKER, {"source": str(source), "output": str(output)})
            result = subprocess.run([sys.executable, str(stage / "scripts/prepare_tagweaver_preview.py"),
                                     "--stage-worker"], cwd=stage, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            (output / "generation.log").write_text(result.stdout, encoding="utf-8")
            if result.returncode:
                print(result.stdout, file=sys.stderr, flush=True)
                raise ValueError("Disposable native validation failed; inspect generation and gate logs")
    finally:
        after = source_inventory(source)
        write_json(output / "source-integrity.json", {
            "source_unchanged": before == after,
            "topics_before": before["data/topics.csv"], "topics_after": after["data/topics.csv"],
            "mirror_before": before["topics/topics.csv"], "mirror_after": after["topics/topics.csv"],
            "source_commit": os.environ.get("GITHUB_SHA", ""),
            "publication_dates_assigned": False,
            "reviewed_source_sha256": {
                locale: before[f"{PREVIEW_DIRECTORY}/{locale}.json"] for locale in LOCALES
            },
        })
        if before != after:
            raise ValueError("Source checkout changed during disposable validation")
    # The worker's output remains in generation.log. Emit only the verified,
    # fixed-path fingerprint manifest after the finally block proves integrity.
    manifest = verified_native_manifest(output)
    print(NATIVE_MANIFEST_PREFIX + json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), flush=True)
    print(f"Validated unscheduled preview: {output / 'candidate.json'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-worker", action="store_true")
    args = parser.parse_args()
    if args.stage_worker:
        stage_worker()
    else:
        prepare()
