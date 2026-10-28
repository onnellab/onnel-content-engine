#!/usr/bin/env python3
"""Validate the reviewed Segra draft bundle in an isolated copy; never publish."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import re
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
SLUG = "choose-safe-audio-working-copy"
CATEGORY = "media"
TOPIC_ID = "TOPIC-0041"
RELATED_APP = "Segra"
PREVIEW_DIRECTORY = "preview/segra-working-copy"
MARKER = ".segra-working-copy-disposable-stage.json"
NATIVE_MANIFEST = "native-output-manifest.json"
NATIVE_MANIFEST_PREFIX = "SEGRA_NATIVE_OUTPUT_MANIFEST "
GATES = (
    ("validate_topics.py",),
    ("validate_foundation.py",),
    ("evaluate_all_articles.py",),
    ("check_nine_language_publication.py",),
    ("check_content_supply.py", "--require-healthy", "--minimum-ideas", "8"),
)
REVIEW_DIAGNOSTIC_PREFIX = "SEGRA_REVIEW_DIAGNOSTIC "
REVIEW_DIAGNOSTIC_UNAVAILABLE_PREFIX = "SEGRA_REVIEW_DIAGNOSTIC_UNAVAILABLE "
MAX_REVIEW_DIAGNOSTIC_BYTES = 65_536
MAX_REVIEW_DIAGNOSTIC_LINE = 2_048
REVIEW_DIAGNOSTIC_CHECK_NAMES = (
    "metadata_complete", "card_title_consistent", "brand_spelling",
    "required_sections", "short_answer_ready", "structured_answer",
    "clear_definitions", "primary_keyword", "external_reference",
    "product_after_education", "publish_ready_image", "social_card_source",
    "image_quality", "internal_links", "readability_depth", "translation_quality",
)
REVIEWED_BLOBS = {
    "en": "ef63fee551a8414ff5df715906e4de1ae2965ab3",
    "ko": "e17679a85f45c467a9fb11418ec3fd2642014931",
    "ja": "01deb67e16d76315c81a59db6f95a8c6f6c71114",
    "zh-Hans": "be26f6387df6b2e1206a25d06769327f839edecc",
    "zh-Hant": "2ef9b9d31805f305c5f79a0afbf010f114d12874",
    "pt-BR": "e45279739b6cecccc7e77b2b157c5f121aabcf8a",
    "de": "b42f3bbfc801ab87e207fae301dab5b39fbee97d",
    "fr": "f042341f0b9cc58861369105630d7f35519f5b70",
    "es": "ea9aedc477769cd44b0a3eac0e8c582d97e04c44"
}



APPROVED_IDEA_SEED = {
    "status": "idea",
    "category": "media",
    "primary_language": "en",
    "slug": "check-audio-export-settings-before-sharing",
    "primary_question": "What should I check in audio export settings before sharing a file?",
    "working_title": "Check Audio Export Settings Before Sharing",
    "priority": "normal",
    "search_intent": "workflow",
    "related_apps": "",
    "primary_keyword": "audio export settings",
    "secondary_keywords": "sample rate|bit depth|format compatibility",
    "evergreen": "true",
    "source_type": "editorial",
    "review_required": "true",
    "notes": "Independently reviewed product-neutral editorial hypothesis: check recipient accepted formats, preserve source settings and test a small output. No universal optimal values, lossless guarantee, app-capability or measured search-demand claim. Distinct from working-copy preservation and clip combining. ID remains unassigned until normal allocation."
}

def bounded_json(directory, filename, limit=100_000):
    path = safe_native_path(directory, filename, required=True)
    return json.loads(read_native_bytes(path, limit).decode("utf-8"),
                      object_pairs_hook=unique_native_object)

REVIEWED_HEADINGS = {
    "en": [
        "Question",
        "Short Answer",
        "What Is a Working Copy?",
        "A Practical Workflow",
        "Limits and Optional Tools",
        "Related Guides",
        "Conclusion",
        "FAQ"
    ],
    "ko": [
        "질문",
        "짧은 답변",
        "작업용 복사본이란 무엇인가요?",
        "작업 순서",
        "한계와 선택 가능한 도구",
        "관련 안내",
        "정리",
        "자주 묻는 질문"
    ],
    "ja": [
        "質問",
        "短い答え",
        "作業用コピーとバックアップの違い",
        "編集前後の手順",
        "確認できることと限界",
        "Segraを使う場合",
        "関連ガイド",
        "まとめ",
        "FAQ"
    ],
    "zh-Hans": [
        "问题",
        "简短回答",
        "工作副本不等于独立备份",
        "建议的操作顺序",
        "检查范围和局限",
        "Segra可以用在哪一步？",
        "相关指南",
        "总结",
        "常见问题"
    ],
    "zh-Hant": [
        "問題",
        "簡短回答",
        "工作副本不等於獨立備份",
        "建議的操作順序",
        "檢查範圍與限制",
        "Segra可以用在哪一步？",
        "相關指南",
        "總結",
        "常見問題"
    ],
    "pt-BR": [
        "Pergunta",
        "Resposta curta",
        "O que é uma cópia de trabalho?",
        "Um procedimento prático",
        "Limites e ferramentas opcionais",
        "Guias relacionados",
        "Conclusão",
        "Perguntas frequentes"
    ],
    "de": [
        "Frage",
        "Kurze Antwort",
        "Was ist eine Arbeitskopie?",
        "Praktisches Vorgehen",
        "Grenzen und optionale Werkzeuge",
        "Weiterführende Anleitungen",
        "Fazit",
        "Häufige Fragen"
    ],
    "fr": [
        "Question",
        "Réponse courte",
        "Qu’est-ce qu’une copie de travail ?",
        "Une méthode pratique",
        "Limites et outils possibles",
        "Guides connexes",
        "Conclusion",
        "Questions fréquentes"
    ],
    "es": [
        "Pregunta",
        "Respuesta breve",
        "Qué es una copia de trabajo",
        "Un procedimiento práctico",
        "Límites y herramientas opcionales",
        "Guías relacionadas",
        "Conclusión",
        "Preguntas frecuentes"
    ]
}

def require_reviewed_section_headings(body, locale):
    if [line[3:] for line in body.splitlines() if line.startswith("## ")] != REVIEWED_HEADINGS[locale]:
        raise ValueError(f"Reviewed section headings mismatch: {locale}")

def validate_drafts(directory):
    manifest = bounded_json(directory, "manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError("Unexpected authored draft manifest")
    expected = {
        "schema": "onnellab.editorial-draft.v1",
        "state": "TEXT_REVIEWED_NATIVE_RENDER_AND_PAGE_VALIDATION_PENDING_NOT_QUEUED",
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
        raise ValueError("Segra preview must remain unqueued and unpublished")
    artifacts = manifest.get("artifacts")
    if (not isinstance(artifacts, list) or len(artifacts) != 9 or
            {item.get("locale"): item.get("git_blob_sha1") for item in artifacts
             if isinstance(item, dict)} != REVIEWED_BLOBS):
        raise ValueError("Reviewed draft blob inventory mismatch")
    if manifest.get("published_at") is not None:
        raise ValueError("Preview cannot be published")
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
        raise ValueError("Exactly the reviewed unassigned editorial seed required")
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
            "notes": "Authored safe audio working-copy workflow; official App Store source bound in the reviewed draft. Editorial keyword hypothesis. Disposable validation only.",
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
            "notes": "Explain original, separate working file, input identity and output verification; not an application screenshot, backup guarantee or lossless claim.",
        }]
        spec["comparison_diagrams"] = []
        spec["screenshot_requirements"]["required"] = False
        spec["screenshot_requirements"]["reason"] = "The visual explains an editorial audio preservation workflow, not an application interface."
        write_json(spec_path, spec)
        generate_image_asset(spec_path)
    # All counterpart Markdown must exist before link and review generation.
    for row in candidates:
        generate_internal_links(row["id"])
    final = {r["id"]: r for r in store.read()}
    if any(final[r["id"]]["status"] != "review" or final[r["id"]]["scheduled_at"] for r in candidates):
        raise ValueError("Candidate must remain unscheduled review")
    return [final[r["id"]] for r in candidates]

def review_diagnostic_summary(report, locale):
    """Select only bounded native review facts, never article text or notes."""
    if locale not in LOCALES or not isinstance(report, dict):
        raise ValueError("Unsupported review diagnostic")
    if (type(report.get("version")) is not int or report["version"] != 4 or
            report.get("type") != "article_review"):
        raise ValueError("Unsupported review diagnostic")
    topic_id = report.get("topic_id")
    score = report.get("score")
    if (not isinstance(topic_id, str) or
            re.fullmatch(r"TOPIC-[0-9]{4}", topic_id) is None or
            type(report.get("passed")) is not bool or
            type(score) not in (int, float) or not 0 <= score <= 10 or
            not math.isfinite(score)):
        raise ValueError("Unsupported review diagnostic")
    checks = report.get("checks")
    if not isinstance(checks, list) or len(checks) != len(REVIEW_DIAGNOSTIC_CHECK_NAMES):
        raise ValueError("Unsupported review diagnostic")
    statuses = {}
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("Unsupported review diagnostic")
        name = check.get("name")
        if (not isinstance(name, str) or name not in REVIEW_DIAGNOSTIC_CHECK_NAMES or
                name in statuses or type(check.get("passed")) is not bool):
            raise ValueError("Unsupported review diagnostic")
        statuses[name] = check["passed"]
    return {
        "locale": locale, "topic_id": topic_id, "passed": report["passed"], "score": score,
        "checks": [{"name": name, "passed": statuses[name]}
                   for name in REVIEW_DIAGNOSTIC_CHECK_NAMES],
    }


def emit_failed_review_diagnostics(stage):
    """Best-effort, read-only summaries; no diagnostic can grant a gate pass."""
    for locale in LOCALES:
        try:
            report = bounded_json(
                stage, f"generated/reviews/{locale}/{CATEGORY}/{SLUG}/review.json",
                limit=MAX_REVIEW_DIAGNOSTIC_BYTES,
            )
            summary = review_diagnostic_summary(report, locale)
            line = REVIEW_DIAGNOSTIC_PREFIX + json.dumps(
                summary, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            if len(line.encode("utf-8")) > MAX_REVIEW_DIAGNOSTIC_LINE:
                raise ValueError("Review diagnostic exceeds size limit")
        except Exception:
            # Never interpolate an exception or unsupported report field.
            line = REVIEW_DIAGNOSTIC_UNAVAILABLE_PREFIX + locale
        print(line, file=sys.stderr, flush=True)


def run_gates(stage, output):
    for index, arguments in enumerate(GATES, 1):
        command = [sys.executable, str(stage / "scripts" / arguments[0]), *arguments[1:]]
        result = subprocess.run(command, cwd=stage, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180)
        (output / f"{index:02d}-{arguments[0]}.log").write_text(result.stdout, encoding="utf-8")
        if result.returncode:
            try:
                # Retain the existing JSON artifacts, but never print their raw content.
                for locale in LOCALES:
                    try:
                        review = safe_native_path(
                            stage, f"generated/reviews/{locale}/{CATEGORY}/{SLUG}/review.json",
                            required=True,
                        )
                        raw = read_native_bytes(review, MAX_REVIEW_DIAGNOSTIC_BYTES)
                        relative = f"failed-candidate-reviews/{locale}.json"
                        target = safe_native_path(output, relative, absent=True)
                        target.parent.mkdir(exist_ok=True)
                        target = safe_native_path(output, relative, absent=True)
                        with target.open("xb") as stream:
                            stream.write(raw)
                    except Exception:
                        # Retention is best-effort and cannot replace the gate failure.
                        continue
                emit_failed_review_diagnostics(stage)
                print(result.stdout, file=sys.stderr, flush=True)
            finally:
                # Diagnostic failures must not replace or suppress the native failure.
                raise ValueError(f"Native gate failed: {arguments[0]} (see retained log)") from None


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
    if output.resolve() != original / "preview-evidence/segra-working-copy":
        raise ValueError("Unexpected evidence destination")
    drafts = validate_drafts(ROOT / "preview/segra-working-copy")
    store, candidates, seeds = stage_topics(ROOT, drafts)
    candidates = materialize_candidates(ROOT, drafts, candidates, store)
    run_gates(ROOT, output)
    collect(ROOT, output, candidates, seeds)

def prepare(source=ROOT):
    if source.is_symlink():
        raise ValueError("Direct source symlink forbidden")
    source = source.resolve()
    evidence_parent = source / "preview-evidence"
    output = evidence_parent / "segra-working-copy"
    if evidence_parent.is_symlink() or output.exists() or output.is_symlink():
        raise ValueError("Evidence destination collision or symlink")
    validate_drafts(source / PREVIEW_DIRECTORY)
    before = source_inventory(source)
    output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="onnellab-segra-working-copy-preview-") as temporary:
            stage = Path(temporary)
            copy_source(source, stage, before)
            write_json(stage / MARKER, {"source": str(source), "output": str(output)})
            result = subprocess.run([sys.executable, str(stage / "scripts/prepare_segra_preview.py"),
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
