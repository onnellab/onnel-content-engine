#!/usr/bin/env python3
"""Validate the authored Aligna bundle in an isolated copy; never publish."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es")
SLUG = "design-consistent-file-naming-system"
CATEGORY = "productivity"
# No .git, installed packages, credentials, user home, or arbitrary source roots.
COPY_ROOTS = ("CODEX.md", "README.md", "docs", "topics", "templates",
              "generated", "scripts", ".github", "archive", "data", "preview")
MARKER = ".aligna-disposable-stage.json"
GATES = (
    ("validate_topics.py",),
    ("validate_foundation.py",),
    ("evaluate_all_articles.py",),
    ("check_nine_language_publication.py",),
    ("check_content_supply.py", "--require-healthy", "--minimum-ideas", "8"),
)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def source_inventory(source):
    """Reject symlinks before copy or hashing; bound input volume."""
    inventory = {}
    total = 0
    for name in COPY_ROOTS:
        root = source / name
        if not root.exists() or root.is_symlink():
            raise ValueError(f"Missing or symlink source root: {name}")
        for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
            if path.is_symlink():
                raise ValueError(f"Symlink source forbidden: {path.relative_to(source)}")
            if path.is_file():
                size = path.stat().st_size
                total += size
                if size > 25_000_000 or total > 100_000_000:
                    raise ValueError("Preview input exceeds bounded size")
                inventory[path.relative_to(source).as_posix()] = digest(path.read_bytes())
    return inventory

def copy_source(source, stage, inventory):
    if source.is_symlink() or stage.is_symlink():
        raise ValueError("Direct source/stage symlink forbidden")
    # Canonicalize OS-owned ancestor aliases (macOS /var -> /private/var).
    # Symlinks within the repository remain forbidden by inventory and copy checks.
    source, stage = source.resolve(), stage.resolve()
    if stage.resolve().is_relative_to(source.resolve()):
        raise ValueError("Stage must be outside source checkout")
    if stage.exists() and any(stage.iterdir()):
        raise ValueError("Stage must be empty")
    stage.mkdir(parents=True, exist_ok=True)
    for relative, expected in inventory.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[0] not in COPY_ROOTS:
            raise ValueError("Unexpected source path")
        original = source / path
        if original.is_symlink() or any(p.is_symlink() for p in original.parents):
            raise ValueError("Source path became a symlink")
        raw = original.read_bytes()
        if digest(raw) != expected:
            raise ValueError("Source changed during copy")
        target = stage / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    # Preserve empty required foundation directories without following links.
    for name in COPY_ROOTS:
        if (source / name).is_dir():
            for directory in [source / name, *(source / name).rglob("*")]:
                if directory.is_symlink():
                    raise ValueError("Source directory became a symlink")
                if directory.is_dir():
                    (stage / directory.relative_to(source)).mkdir(parents=True, exist_ok=True)

def validate_drafts(directory):
    drafts = {}
    changes = read_json(directory / "validation_text_changes.json")["changes"]
    if set(changes) != set(LOCALES):
        raise ValueError("Exactly nine editorial change maps required")
    manifest = read_json(directory / "manifest.json")
    if manifest.get("state") != "DRAFT_UNVALIDATED_NOT_QUEUED" or manifest.get("slug") != SLUG:
        raise ValueError("Unexpected authored draft manifest")
    if manifest.get("locales") != list(LOCALES) or manifest.get("queue_modified") is not False:
        raise ValueError("Unexpected locale or queue contract")
    for locale in LOCALES:
        path = directory / f"{locale}.json"
        if path.is_symlink() or path.stat().st_size > 100_000:
            raise ValueError("Unsafe draft file")
        draft = read_json(path)
        required = {"locale", "title", "description", "question", "primary_keyword",
                    "secondary_keywords", "short_answer", "body", "image"}
        if set(draft) != required or draft["locale"] != locale:
            raise ValueError("Draft schema/locale mismatch")
        if any(not isinstance(draft[k], str) or not draft[k].strip() for k in required - {"image"}):
            raise ValueError("Empty draft field")
        if not draft["body"].startswith("# " + draft["title"] + "\n"):
            raise ValueError("Draft title/H1 mismatch")
        if not isinstance(draft["image"], dict) or set(draft["image"]) != {"title", "subtitle", "message", "steps"}:
            raise ValueError("Image copy schema mismatch")
        if any(not isinstance(draft["image"][key], str) or not draft["image"][key].strip() for key in ("title", "subtitle", "message")):
            raise ValueError("Image copy text must be non-empty")
        for before, after in changes[locale]:
            if draft["body"].count(before) != 1:
                raise ValueError(f"Editorial change is not exact and unique: {locale}")
            draft["body"] = draft["body"].replace(before, after, 1)
        drafts[locale] = draft
    return drafts

def stage_topics(stage, drafts):
    from topic_management import TopicStore
    store = TopicStore(stage / "data/topics.csv", apps_path=stage / "data/apps_registry.csv",
                       mirror_path=stage / "topics/topics.csv")
    rows = store.read()
    matches = [r for r in rows if r["slug"] == SLUG]
    if len(matches) != 1 or matches[0]["id"] != "TOPIC-0035" or matches[0]["status"] != "idea":
        raise ValueError("Candidate is reserved, duplicated or no longer an idea")
    if matches[0]["primary_language"] != "en" or matches[0]["category"] != CATEGORY:
        raise ValueError("Unexpected candidate identity")
    original_other = [dict(r) for r in rows if r["id"] != "TOPIC-0035"]
    candidates = []
    for locale in LOCALES:
        d = drafts[locale]
        fields = {
            "category": CATEGORY, "primary_language": locale, "slug": SLUG,
            "primary_question": d["question"], "working_title": d["title"],
            "priority": "normal", "search_intent": "workflow", "related_apps": "Aligna",
            "primary_keyword": d["primary_keyword"], "secondary_keywords": d["secondary_keywords"],
            "evergreen": "true", "source_type": "editorial", "review_required": "true",
            "canonical_path": f"generated/markdown/{locale}/{CATEGORY}/{SLUG}.md",
            "notes": "Authored educational naming convention; editorial keyword hypothesis. Disposable validation only.",
        }
        if locale == "en":
            row = store.edit("TOPIC-0035", fields)
        else:
            row = store.add(fields)
        for status in ("approved", "research", "outline", "draft"):
            row = store.edit(row["id"], {"status": status})
        candidates.append(row)
    seeds = read_json(stage / "preview/aligna/idea_seeds.json")
    expected = {"mark-uncertainty-clearly-in-research-notes",
                "distinguish-duplicate-music-files-from-different-recordings"}
    if len(seeds) != 2 or {s["slug"] for s in seeds} != expected:
        raise ValueError("Exactly the two reviewed editorial seeds required")
    if any(s.get("related_apps") or s.get("id") or s.get("status") != "idea" for s in seeds):
        raise ValueError("Seeds cannot claim app capabilities or reserve IDs")
    seed_rows = [store.add(seed) for seed in seeds]
    final_by_id = {r["id"]: r for r in store.read()}
    if any(final_by_id[r["id"]] != r for r in original_other):
        raise ValueError("Unrelated topic rows changed")
    return store, candidates, seed_rows

def materialize_candidates(stage, drafts, candidates, store):
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
            "related_apps": "Aligna",
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
            "notes": "Explain filename fields; this is not an application screenshot or arbitrary-pattern capability claim.",
        }]
        spec["comparison_diagrams"] = []
        spec["screenshot_requirements"]["required"] = False
        spec["screenshot_requirements"]["reason"] = "The visual explains an educational naming convention, not an application interface."
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
            print(result.stdout, file=sys.stderr, flush=True)
            raise ValueError(f"Native gate failed: {arguments[0]} (see retained log)")

def collect(stage, output, candidates, seeds):
    # The native read-only gate also recomputes current fingerprints and requires
    # every mandatory check. It imports the existing score verifier, never its CLI.
    from check_nine_language_publication import check_reviewed_candidates
    check_reviewed_candidates(stage / "data/topics.csv")
    files = []
    for row in candidates:
        locale = row["primary_language"]
        asset_dir = stage / "generated/assets/blog" / locale / SLUG
        # Existing publisher uses the workflow as its social source, too.
        shutil.copyfile(asset_dir / "workflow-diagram.svg", asset_dir / "social-card.svg")
        shutil.copyfile(asset_dir / "workflow-diagram.png", asset_dir / "social-card.png")
        paths = [row["canonical_path"],
                 f"generated/images/{locale}/{CATEGORY}/{SLUG}/image_spec.json",
                 f"generated/metadata/{locale}/{CATEGORY}/{SLUG}/internal_links.json",
                 f"generated/reviews/{locale}/{CATEGORY}/{SLUG}/review.json"]
        paths += [f"generated/assets/blog/{locale}/{SLUG}/{name}" for name in
                  ("workflow-diagram.svg", "workflow-diagram.png", "social-card.svg", "social-card.png")]
        for relative in paths:
            src = stage / relative
            if not src.is_file() or src.is_symlink():
                raise ValueError(f"Missing native output: {relative}")
            target = output / "artifacts" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            if relative.endswith(".md") or relative.endswith(".svg"):
                content = src.read_text(encoding="utf-8")
                files.append({"path": relative, "content": content, "sha256": digest(content.encode())})
    bundle = {"schema": 1, "state": "UNSCHEDULED_PREVIEW_ONLY", "slug": SLUG,
              "locales": list(LOCALES), "files": files}
    write_json(output / "candidate.json", bundle)
    (output / "candidate.sha256").write_text(digest((output / "candidate.json").read_bytes()) + "  candidate.json\n")
    from prepare_blog_preview import validate_bundle
    validate_bundle(output / "candidate.json")
    write_json(output / "candidate-topic-rows.json", {"candidates": candidates, "idea_seeds": seeds,
                                                    "ids_reserved": False, "live_queue_modified": False})

def stage_worker():
    marker = ROOT / MARKER
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("Worker requires a disposable stage marker")
    settings = read_json(marker)
    original = Path(settings["source"]).resolve()
    if ROOT == original or ROOT.is_relative_to(original):
        raise ValueError("Worker cannot run in or beneath the source checkout")
    output = Path(settings["output"])
    if output.resolve() != original / "preview-evidence/aligna":
        raise ValueError("Unexpected evidence destination")
    drafts = validate_drafts(ROOT / "preview/aligna")
    store, candidates, seeds = stage_topics(ROOT, drafts)
    candidates = materialize_candidates(ROOT, drafts, candidates, store)
    run_gates(ROOT, output)
    collect(ROOT, output, candidates, seeds)

def prepare(source=ROOT):
    if source.is_symlink():
        raise ValueError("Direct source symlink forbidden")
    source = source.resolve()
    evidence_parent = source / "preview-evidence"
    output = evidence_parent / "aligna"
    if evidence_parent.is_symlink() or output.exists() or output.is_symlink():
        raise ValueError("Evidence destination collision or symlink")
    before = source_inventory(source)
    output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="onnellab-aligna-preview-") as temporary:
            stage = Path(temporary)
            copy_source(source, stage, before)
            write_json(stage / MARKER, {"source": str(source), "output": str(output)})
            result = subprocess.run([sys.executable, str(stage / "scripts/prepare_aligna_preview.py"),
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
        })
        if before != after:
            raise ValueError("Source checkout changed during disposable validation")
    print(f"Validated unscheduled preview: {output / 'candidate.json'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-worker", action="store_true")
    args = parser.parse_args()
    if args.stage_worker:
        stage_worker()
    else:
        prepare()
