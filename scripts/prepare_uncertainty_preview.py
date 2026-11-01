#!/usr/bin/env python3
"""Validate the authored research source-notes bundle in an isolated copy; never publish."""
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
SLUG = "mark-uncertainty-clearly-in-research-notes"
CATEGORY = "research"
# No .git, installed packages, credentials, user home, or arbitrary source roots.
COPY_ROOTS = ("CODEX.md", "README.md", "docs", "topics", "templates",
              "generated", "scripts", ".github", "archive", "data", "preview", "drafts")
MARKER = ".research-uncertainty-disposable-stage.json"
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

DRAFT_DIRECTORY = "drafts/blog/mark-uncertainty-clearly-in-research-notes"
REVIEWED_BLOBS = {
    "fr": "3e8b5725b17d5995277d6b0515351f0fa2b68529",
    "en": "6c2e295cc9f2be82d7857dcd6c81cb3275bd58c3",
    "ja": "8894f625f9002396d32bcf351862085f6f36843d",
    "es": "1f76aadc427a116997c5fa8f65a2e34f3e8ef391",
    "zh-Hans": "7963bc8eaacea65981511b2aeb30e0f44f83c413",
    "zh-Hant": "d9ca7e7899393056f7c08b6a1661fab831f03a7e",
    "ko": "bd8ec694ef6456c0e10374b2679a811bf01033ac",
    "pt-BR": "e952058e39d0286fa58ffa70b5e82332b8cc567f",
    "de": "c49ef3085959abd8d7fad0c0fe80a52b334fb0b8"
}
REVIEWED_SVG_BLOBS = {
    "en": "fd6b053eddb384fcfd384349fd55e552f13c09b7",
    "ko": "7a23cbc2bc261da87e9c3064870354002260d1c2",
    "ja": "722088383ae6151295a8bda8c4e4e673d9887ad9",
    "zh-Hans": "249a2aca68ccc63dc5fa89d606e4697264f8e609",
    "zh-Hant": "0e9d271396da3b6686dec24494be3ff94e5f2516",
    "pt-BR": "f38dbca056e8657192ad50717df3feaf334bfafb",
    "de": "f851fc6df51833c1100a6117366d5077eb9ab335",
    "fr": "2af9135ddbcd00cb882322aa7c23aa01c2d3b148",
    "es": "0200209d14d8cf13e270a5502eb0b81c16fd607f"
}
IMAGE_COPY = {
    "en": {
        "title": "Clarify uncertainty",
        "subtitle": "Claim, evidence, reason, next check",
        "message": "Keep unresolved questions visible.",
        "steps": [
            [
                "Claim",
                "One checkable statement."
            ],
            [
                "Evidence",
                "A passage actually read."
            ],
            [
                "Reason",
                "What is uncertain and why."
            ],
            [
                "Next check",
                "A concrete next action."
            ]
        ]
    },
    "ko": {
        "title": "불확실성을 분명하게",
        "subtitle": "주장·근거·이유·다음 확인",
        "message": "아직 해결하지 못한 질문을 분명히 남겨요.",
        "steps": [
            [
                "주장",
                "확인 가능한 문장 하나"
            ],
            [
                "근거",
                "실제로 읽은 근거 구절"
            ],
            [
                "이유",
                "불확실한 부분과 이유"
            ],
            [
                "다음 확인",
                "구체적인 다음 확인"
            ]
        ]
    },
    "ja": {
        "title": "不確実な点を明確に",
        "subtitle": "主張・根拠・理由・次の確認",
        "message": "未解決の問いを見える状態にします。",
        "steps": [
            [
                "主張",
                "確認できる文を一つ"
            ],
            [
                "根拠",
                "実際に読んだ根拠"
            ],
            [
                "理由",
                "不確実な点と理由"
            ],
            [
                "次の確認",
                "具体的な次の確認"
            ]
        ]
    },
    "zh-Hans": {
        "title": "明确不确定之处",
        "subtitle": "主张、证据、原因、下一步核查",
        "message": "让尚未解决的问题清晰可见。",
        "steps": [
            [
                "主张",
                "可以核查的陈述"
            ],
            [
                "证据",
                "实际读过的证据"
            ],
            [
                "原因",
                "不确定之处及原因"
            ],
            [
                "下一步核查",
                "具体的核查行动"
            ]
        ]
    },
    "zh-Hant": {
        "title": "釐清不確定之處",
        "subtitle": "主張、證據、原因、下一步查證",
        "message": "讓尚未解決的問題清晰可見。",
        "steps": [
            [
                "主張",
                "可以查證的陳述"
            ],
            [
                "證據",
                "實際讀過的證據"
            ],
            [
                "原因",
                "不確定之處及原因"
            ],
            [
                "下一步查證",
                "具體的查證行動"
            ]
        ]
    },
    "pt-BR": {
        "title": "Registre a incerteza",
        "subtitle": "Afirmação, evidência, motivo e verificação",
        "message": "Deixe visíveis as questões não resolvidas.",
        "steps": [
            [
                "Frase",
                "Uma afirmação verificável"
            ],
            [
                "Evidência",
                "Um trecho realmente lido"
            ],
            [
                "Motivo",
                "O que é incerto e por quê"
            ],
            [
                "Checar",
                "Uma verificação concreta"
            ]
        ]
    },
    "de": {
        "title": "Unsicherheit klären",
        "subtitle": "Aussage, Beleg, Grund und nächste Prüfung",
        "message": "Offene Fragen bleiben sichtbar.",
        "steps": [
            [
                "Aussage",
                "Eine prüfbare Aussage"
            ],
            [
                "Beleg",
                "Die gelesene Fundstelle"
            ],
            [
                "Grund",
                "Unklarheit und Grund"
            ],
            [
                "Nächste Prüfung",
                "Ein konkreter Prüfschritt"
            ]
        ]
    },
    "fr": {
        "title": "Clarifier l’incertitude",
        "subtitle": "Affirmation, preuve, raison et vérification",
        "message": "Gardez les questions non résolues visibles.",
        "steps": [
            [
                "Énoncé",
                "Un énoncé vérifiable"
            ],
            [
                "Preuve",
                "Un passage réellement lu"
            ],
            [
                "Raison",
                "Le doute et sa raison"
            ],
            [
                "Vérifier",
                "Une vérification précise"
            ]
        ]
    },
    "es": {
        "title": "Aclara la incertidumbre",
        "subtitle": "Afirmación, prueba, motivo y comprobación",
        "message": "Mantén visibles las cuestiones pendientes.",
        "steps": [
            [
                "Frase",
                "Un enunciado comprobable"
            ],
            [
                "Prueba",
                "Un pasaje realmente leído"
            ],
            [
                "Motivo",
                "La duda y su motivo"
            ],
            [
                "Revisar",
                "Una comprobación concreta"
            ]
        ]
    }
}

def validate_drafts(directory):
    from prepare_blog_preview import metadata, allowed_candidate_links
    import re
    manifest_path = safe_native_path(directory, "manifest.json", required=True)
    manifest = json.loads(read_native_bytes(manifest_path, 100_000).decode("utf-8"),
                          object_pairs_hook=unique_native_object)
    if (manifest.get("schema") != 1 or manifest.get("slug") != SLUG
            or manifest.get("state") != "draft_not_ready"
            or manifest.get("queue_modified") is not False
            or manifest.get("new_topic_ids_allocated") is not False
            or manifest.get("scheduled_at") is not None or manifest.get("published_at") is not None):
        raise ValueError("Unexpected uncertainty draft state")
    drafts = {}
    for locale in LOCALES:
        raw = read_native_bytes(safe_native_path(directory, locale + ".md", required=True), 100_000)
        if native_entry(locale + ".md", raw)["git_blob_sha1"] != REVIEWED_BLOBS[locale]:
            raise ValueError("Reviewed Markdown fingerprint mismatch: " + locale)
        svg = read_native_bytes(safe_native_path(directory, "assets/" + locale + "/workflow-diagram.svg", required=True), 100_000)
        if native_entry("workflow-diagram.svg", svg)["git_blob_sha1"] != REVIEWED_SVG_BLOBS[locale]:
            raise ValueError("Reviewed SVG fingerprint mismatch: " + locale)
        values, body = metadata(raw.decode("utf-8"))
        if (values.get("language") != locale or values.get("slug") != SLUG
                or values.get("category") != CATEGORY or values.get("status") != "draft"
                or values.get("related_apps") != "" or values.get("title") != values.get("card_title")
                or values.get("canonical_url") != f"https://onnellab.com/blog/{locale.lower()}/{SLUG}/"
                or any(k in values for k in ("topic_id", "scheduled_at", "published_at", "updated_at"))
                or not body.lstrip().startswith("# " + values["title"] + "\n")):
            raise ValueError("Draft identity or lifecycle mismatch: " + locale)
        allowed = allowed_candidate_links(SLUG, locale)
        if any(link not in allowed for link in re.findall(r"\]\(([^\s)]+)", body)):
            raise ValueError("Unexpected draft link")
        question = body.split("\n## ", 2)[1].split("\n", 1)[1].strip()
        draft = {key: values[key] for key in ("title", "description", "primary_keyword", "secondary_keywords", "short_answer")}
        draft.update(locale=locale, question=question, body=body.strip() + "\n", image=IMAGE_COPY[locale])
        drafts[locale] = draft
    return drafts

def stage_topics(stage, drafts):
    from topic_management import TopicStore
    store = TopicStore(stage / "data/topics.csv", apps_path=stage / "data/apps_registry.csv",
                       mirror_path=stage / "topics/topics.csv")
    rows = store.read()
    matches = [r for r in rows if r["slug"] == SLUG]
    if len(matches) != 1 or matches[0]["id"] != "TOPIC-0086" or matches[0]["status"] != "idea":
        raise ValueError("Candidate is reserved, duplicated or no longer an idea")
    if matches[0]["primary_language"] != "en" or matches[0]["category"] != CATEGORY:
        raise ValueError("Unexpected candidate identity")
    original_other = [dict(r) for r in rows if r["id"] != "TOPIC-0086"]
    candidates = []
    for locale in LOCALES:
        d = drafts[locale]
        fields = {
            "category": CATEGORY, "primary_language": locale, "slug": SLUG,
            "primary_question": d["question"], "working_title": d["title"],
            "priority": "normal", "search_intent": "workflow", "related_apps": "",
            "primary_keyword": d["primary_keyword"], "secondary_keywords": d["secondary_keywords"],
            "evergreen": "true", "source_type": "editorial", "review_required": "true",
            "canonical_path": f"generated/markdown/{locale}/{CATEGORY}/{SLUG}.md",
            "notes": "Authored uncertainty-note workflow; editorial keyword hypothesis. Disposable validation only.",
        }
        if locale == "en":
            row = store.edit("TOPIC-0086", fields)
        else:
            row = store.add(fields)
        for status in ("approved", "research", "outline", "draft"):
            row = store.edit(row["id"], {"status": status})
        candidates.append(row)
    seeds = read_json(stage / "preview/research-uncertainty/idea_seeds.json")
    expected = {"distinguish-source-publication-date-from-access-date"}
    if len(seeds) != 1 or {s["slug"] for s in seeds} != expected:
        raise ValueError("Exactly the reviewed editorial seed required")
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
            "related_apps": "",
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
            "notes": "Explain claim, evidence, reason and next check; this is not an application screenshot or a real study result.",
        }]
        spec["comparison_diagrams"] = []
        spec["screenshot_requirements"]["required"] = False
        spec["screenshot_requirements"]["reason"] = "The visual explains uncertainty and verification steps, not an application interface."
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


NATIVE_MANIFEST = "native-output-manifest.json"
NATIVE_MANIFEST_PREFIX = "UNCERTAINTY_NATIVE_OUTPUT_MANIFEST "
MAX_NATIVE_BYTES = 25_000_000

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

def safe_native_path(root, relative, *, required=False, absent=False):
    """Reject noncanonical paths and symlinks before any read or write."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Unsafe native output path")
    path = Path(relative)
    if not path.parts or path.is_absolute() or path.as_posix() != relative or ".." in path.parts:
        raise ValueError("Unsafe native output path")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing or symlink native root")
    root = root.resolve()
    current = root
    for index, part in enumerate(path.parts):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink native output path: {relative}")
        if current.exists():
            if index < len(path.parts) - 1 and not current.is_dir():
                raise ValueError(f"Invalid native output parent: {relative}")
            if index == len(path.parts) - 1 and not current.is_file():
                raise ValueError(f"Invalid native output file: {relative}")
    if required and not current.is_file():
        raise ValueError(f"Missing native output: {relative}")
    if absent and current.exists():
        raise ValueError(f"Native evidence collision: {relative}")
    return current

def read_native_bytes(path, limit=MAX_NATIVE_BYTES):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Native output exceeds size limit")
    return raw

def unique_native_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate native manifest JSON key")
        value[key] = item
    return value

def native_entry(relative, raw):
    if len(raw) > MAX_NATIVE_BYTES:
        raise ValueError(f"Native output exceeds size limit: {relative}")
    header = f"blob {len(raw)}\0".encode("ascii")
    return {"path": relative, "byte_length": len(raw), "sha256": digest(raw),
            "git_blob_sha1": hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()}

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


REGISTERED_AUDIT = "data/blog_review_supply_20261101_uncertainty.json"
REGISTERED_IDS = dict(zip(LOCALES, (
    "TOPIC-0086", "TOPIC-0124", "TOPIC-0125", "TOPIC-0126",
    "TOPIC-0127", "TOPIC-0128", "TOPIC-0129", "TOPIC-0130", "TOPIC-0131",
)))

def read_registered_json(stage, relative, limit=100_000):
    path = safe_native_path(stage, relative, required=True)
    return json.loads(read_native_bytes(path, limit).decode("utf-8"),
                      object_pairs_hook=unique_native_object)

def validate_registered_candidates(stage):
    """Read existing registration; never repair, regenerate, or reserve IDs."""
    from topic_management import TOPIC_HEADER, read_csv
    from check_nine_language_publication import check_reviewed_candidates

    audit = read_registered_json(stage, REGISTERED_AUDIT)
    if (not isinstance(audit, dict) or type(audit.get("schema")) is not int or
            audit["schema"] != 1 or
            audit.get("kind") != "review_supply_audit_not_publication_receipt" or
            audit.get("slug") != SLUG or audit.get("category") != CATEGORY or
            audit.get("stage") != "review" or
            any(key not in audit or audit[key] is not None
                for key in ("scheduled_at", "published_at", "published_url")) or
            audit.get("queue_ids") != list(REGISTERED_IDS.values())):
        raise ValueError("Invalid registered research audit identity")

    manifest = validate_native_manifest({
        "schema": 1, "slug": SLUG, "locales": list(LOCALES),
        "files": audit.get("reviewed_files"),
    })
    validate_drafts(stage / DRAFT_DIRECTORY)
    if audit.get("reviewed_source_git_blobs") != REVIEWED_BLOBS or audit.get("reviewed_svg_git_blobs") != REVIEWED_SVG_BLOBS:
        raise ValueError("Registered reviewed source pins mismatch")

    topics = safe_native_path(stage, "data/topics.csv", required=True)
    mirror = safe_native_path(stage, "topics/topics.csv", required=True)
    if read_native_bytes(topics) != read_native_bytes(mirror):
        raise ValueError("Registered topic mirror mismatch")
    rows = read_csv(topics, TOPIC_HEADER)
    selected = [row for row in rows
                if row["slug"] == SLUG or row["id"] in REGISTERED_IDS.values()]
    identities = {(row["primary_language"], row["id"]) for row in selected}
    if len(selected) != 9 or identities != set(REGISTERED_IDS.items()):
        raise ValueError("Exactly nine registered candidate identities required")
    by_locale = {row["primary_language"]: row for row in selected}
    candidates = [by_locale[locale] for locale in LOCALES]
    for row in candidates:
        locale = row["primary_language"]
        if (row["slug"] != SLUG or row["category"] != CATEGORY or
                row["status"] != "review" or row["review_required"] != "true" or
                row["canonical_path"] !=
                f"generated/markdown/{locale}/{CATEGORY}/{SLUG}.md" or
                any(row[key] != "" for key in
                    ("related_apps", "scheduled_at", "published_at", "published_url"))):
            raise ValueError("Registered candidate must remain unscheduled review")

    for entry in manifest["files"]:
        path = safe_native_path(stage, entry["path"], required=True)
        if native_entry(entry["path"], read_native_bytes(path)) != entry:
            raise ValueError(f"Registered artifact fingerprint mismatch: {entry['path']}")
    for row in candidates:
        review = read_registered_json(
            stage, f"generated/reviews/{row['primary_language']}/{CATEGORY}/{SLUG}/review.json")
        if (not isinstance(review, dict) or type(review.get("version")) is not int or
                review["version"] != 4 or review.get("topic_id") != row["id"]):
            raise ValueError("Registered candidate requires its version 4 review")
    # This read-only gate compares persisted reports against newly computed
    # current fingerprints, strict >9.0 scores, and every mandatory check.
    check_reviewed_candidates(topics)
    return candidates, manifest

def run_registered_gates(stage, output):
    """Preserve registered bytes while native evaluators write in another copy."""
    before = source_inventory(stage)
    with tempfile.TemporaryDirectory(prefix="onnellab-registered-research-gates-") as temporary:
        gate_stage = Path(temporary)
        copy_source(stage, gate_stage, before)
        run_gates(gate_stage, output)
    if source_inventory(stage) != before:
        raise ValueError("Registered stage changed during native validation")
    validate_registered_candidates(stage)

def collect(stage, output, candidates, seeds, *, registered_manifest=None):
    # The native read-only gate also recomputes current fingerprints and requires
    # every mandatory check. It imports the existing score verifier, never its CLI.
    from check_nine_language_publication import check_reviewed_candidates
    check_reviewed_candidates(stage / "data/topics.csv")
    if registered_manifest is not None:
        actual_candidates, actual_manifest = validate_registered_candidates(stage)
        if candidates != actual_candidates or registered_manifest != actual_manifest or seeds:
            raise ValueError("Registered collection evidence mismatch")
    expected_entries = ({entry["path"]: entry for entry in registered_manifest["files"]}
                        if registered_manifest is not None else None)
    expected = native_output_paths()
    if (len(candidates) != len(LOCALES) or
            {row["primary_language"] for row in candidates} != set(LOCALES)):
        raise ValueError("Exactly nine distinct native candidate locales required")
    for row in candidates:
        canonical = f"generated/markdown/{row['primary_language']}/{CATEGORY}/{SLUG}.md"
        if row["canonical_path"] != canonical:
            raise ValueError("Unexpected native candidate Markdown path")
    aliases = {}
    for locale in (() if registered_manifest is not None else LOCALES):
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
        if expected_entries is not None and entry != expected_entries[relative]:
            raise ValueError(f"Registered artifact changed during collection: {relative}")
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
                                                    "ids_reserved": registered_manifest is not None, "live_queue_modified": False})
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
    if output.resolve() != original / "preview-evidence/research-uncertainty":
        raise ValueError("Unexpected evidence destination")
    audit_path = safe_native_path(ROOT, REGISTERED_AUDIT)
    if audit_path.exists():
        candidates, manifest = validate_registered_candidates(ROOT)
        run_registered_gates(ROOT, output)
        collect(ROOT, output, candidates, [], registered_manifest=manifest)
    else:
        drafts = validate_drafts(ROOT / DRAFT_DIRECTORY)
        store, candidates, seeds = stage_topics(ROOT, drafts)
        candidates = materialize_candidates(ROOT, drafts, candidates, store)
        run_gates(ROOT, output)
        collect(ROOT, output, candidates, seeds)

def prepare(source=ROOT):
    if source.is_symlink():
        raise ValueError("Direct source symlink forbidden")
    source = source.resolve()
    evidence_parent = source / "preview-evidence"
    output = evidence_parent / "research-uncertainty"
    if evidence_parent.is_symlink() or output.exists() or output.is_symlink():
        raise ValueError("Evidence destination collision or symlink")
    validate_drafts(source / DRAFT_DIRECTORY)
    before = source_inventory(source)
    output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="onnellab-research-uncertainty-preview-") as temporary:
            stage = Path(temporary)
            copy_source(source, stage, before)
            write_json(stage / MARKER, {"source": str(source), "output": str(output)})
            result = subprocess.run([sys.executable, str(stage / "scripts/prepare_uncertainty_preview.py"),
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
