"""Closed allowlists for supported nonpublishing preview candidates."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_blog_preview import candidate_profile, allowed_candidate_links, prepare, validate_bundle, LOCALES

RESEARCH_SLUG = "separate-source-notes-from-conclusions"
RESEARCH_SOURCES = {
    "https://library.leeds.ac.uk/info/1401/academic-skills/85/note-making",
    "https://owl.purdue.edu/owl/research_and_citation/using_research/quoting_paraphrasing_and_summarizing/index.html",
}

class PreviewCandidateProfiles(unittest.TestCase):
    def test_unknown_candidate_and_locale_fail_closed(self):
        for slug in ("", "../aligna", "other-product", "design-consistent-file-naming-system-extra",
                     RESEARCH_SLUG + "-extra", "consistent-album-artist-names-extra", "choose-safe-audio-working-copy-extra"):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                candidate_profile(slug)
        with self.assertRaises(ValueError):
            allowed_candidate_links("design-consistent-file-naming-system", "zh-hans")

    def test_aligna_exact_links_and_tables(self):
        slug = "design-consistent-file-naming-system"
        stores = [
            "https://apps.apple.com/us/app/aligna-file-renamer/id6783642658",
            "https://play.google.com/store/apps/details?id=com.onnellab.aligna",
        ]
        profile = candidate_profile(slug)
        self.assertEqual(profile["category"], "productivity")
        self.assertEqual(profile["faq_count"], 4)
        self.assertEqual(profile["source_urls"], [])
        self.assertEqual(profile["store_urls"], stores)
        for locale in LOCALES:
            expected = {f"/blog-assets/{locale}/{slug}/workflow-diagram.svg", "/apps/aligna/", *stores}
            expected.update(f"https://onnellab.com/blog/{locale.lower()}/{related}/" for related in
                            ("rename-files-safely-preview-workflow", "organize-downloads-small-folder-system"))
            self.assertEqual(allowed_candidate_links(slug, locale), expected)
            self.assertEqual(profile["table_rows"][locale], 5 if locale == "en" else 6)

    def test_clipnest_profile_remains_exact(self):
        slug = "turn-repeated-text-into-reusable-snippets"
        profile = candidate_profile(slug)
        self.assertEqual(profile["category"], "productivity")
        self.assertEqual(profile["faq_count"], 4)
        self.assertEqual(profile["source_urls"], [])
        for locale in LOCALES:
            self.assertEqual(profile["table_rows"][locale], 3)
            self.assertEqual(allowed_candidate_links(slug, locale), {
                f"/blog-assets/{locale}/{slug}/workflow-diagram.svg",
                "/apps/clipnest/",
                "https://apps.apple.com/us/app/clipnest-clipboard-tool/id6779928552",
                f"https://onnellab.com/blog/{locale.lower()}/reuse-copied-text-snippets-iphone/",
            })

    def test_research_profile_has_only_reviewed_sources_and_localized_guide(self):
        profile = candidate_profile(RESEARCH_SLUG)
        self.assertEqual(profile["category"], "research")
        self.assertEqual(profile["faq_count"], 3)
        self.assertIsNone(profile["app_path"])
        self.assertEqual(profile["store_urls"], [])
        self.assertEqual(set(profile["source_urls"]), RESEARCH_SOURCES)
        self.assertEqual(profile["related_slugs"], ["keep-durable-research-reading-log"])
        for locale in LOCALES:
            with self.subTest(locale=locale):
                self.assertEqual(profile["table_rows"][locale], 3)
                self.assertEqual(allowed_candidate_links(RESEARCH_SLUG, locale), {
                    f"/blog-assets/{locale}/{RESEARCH_SLUG}/workflow-diagram.svg",
                    f"https://onnellab.com/blog/{locale.lower()}/keep-durable-research-reading-log/",
                    *RESEARCH_SOURCES,
                })

    def test_profiles_do_not_share_mutable_state(self):
        for slug in ("design-consistent-file-naming-system",
                     "turn-repeated-text-into-reusable-snippets", RESEARCH_SLUG, "consistent-album-artist-names", "choose-safe-audio-working-copy"):
            with self.subTest(slug=slug):
                expected = candidate_profile(slug)
                profile = candidate_profile(slug)
                for key in ("store_urls", "source_urls", "related_slugs"):
                    profile[key].append("https://example.invalid/")
                profile["table_rows"]["en"] = 999
                self.assertEqual(candidate_profile(slug), expected)
                self.assertNotIn("https://example.invalid/", allowed_candidate_links(slug, "en"))

    def test_tagweaver_exact_closed_profile(self):
        slug = "consistent-album-artist-names"
        profile = candidate_profile(slug)
        stores = [
            "https://apps.apple.com/app/id6759609875",
            "https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2",
        ]
        self.assertEqual(profile["category"], "music")
        self.assertEqual(profile["faq_count"], 4)
        self.assertEqual(profile["store_urls"], stores)
        self.assertEqual(profile["source_urls"], [])
        for locale in LOCALES:
            self.assertEqual(profile["table_rows"][locale], 4)
            self.assertEqual(allowed_candidate_links(slug, locale), {
                f"/blog-assets/{locale}/{slug}/workflow-diagram.svg",
                "/apps/tagweaver/", *stores,
                f"https://onnellab.com/blog/{locale.lower()}/clean-up-mp3-metadata-before-organizing-music/",
                f"https://onnellab.com/blog/{locale.lower()}/number-tracks-multi-disc-mp3-album/",
            })


class ResearchPreviewBundle(unittest.TestCase):
    def setUp(self):
        self.bundle = {
            "schema": 1, "state": "UNSCHEDULED_PREVIEW_ONLY",
            "slug": RESEARCH_SLUG, "locales": list(LOCALES), "files": [],
        }
        for locale in LOCALES:
            draft = json.loads((ROOT / "preview/research-source-notes" / f"{locale}.json").read_text())
            header = {
                "title": draft["title"], "card_title": draft["title"],
                "category": "research", "language": locale, "slug": RESEARCH_SLUG,
                "status": "review", "related_apps": "",
                "canonical_url": f"https://onnellab.com/blog/{locale.lower()}/{RESEARCH_SLUG}/",
            }
            markdown = "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
                                         for key, value in header.items()) + "---\n\n" + draft["body"] + "\n"
            self.add_file(f"generated/markdown/{locale}/research/{RESEARCH_SLUG}.md", markdown)
            for kind in ("workflow-diagram", "social-card"):
                self.add_file(f"generated/assets/blog/{locale}/{RESEARCH_SLUG}/{kind}.svg",
                              '<svg xmlns="http://www.w3.org/2000/svg"><title>Fixture only</title></svg>')

    def add_file(self, path, content):
        self.bundle["files"].append({
            "path": path, "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        })

    def replace_content(self, bundle, index, content):
        bundle["files"][index]["content"] = content
        bundle["files"][index]["sha256"] = hashlib.sha256(content.encode()).hexdigest()

    def write_bundle(self, directory, bundle=None, corrupt_checksum=False):
        path = Path(directory) / "candidate.json"
        raw = json.dumps(self.bundle if bundle is None else bundle, ensure_ascii=False).encode()
        path.write_bytes(raw)
        checksum = "0" * 64 if corrupt_checksum else hashlib.sha256(raw).hexdigest()
        path.with_suffix(".sha256").write_text(checksum + "  candidate.json\n")
        return path

    def validate(self, bundle=None, corrupt_checksum=False):
        with tempfile.TemporaryDirectory() as directory:
            return validate_bundle(self.write_bundle(directory, bundle, corrupt_checksum))

    def test_reviewed_nine_locale_research_payloads_validate(self):
        result, digest = self.validate()
        self.assertEqual(result, self.bundle)
        self.assertEqual(len(result["files"]), 27)
        self.assertEqual(len(digest), 64)

    def test_category_paths_and_metadata_are_profile_bound(self):
        for bad_path in (
            f"generated/markdown/en/productivity/{RESEARCH_SLUG}.md",
            f"generated/markdown/en/research/{RESEARCH_SLUG}-extra.md",
            f"generated/markdown/zh-hans/research/{RESEARCH_SLUG}.md",
            "../outside.md",
        ):
            bundle = copy.deepcopy(self.bundle)
            bundle["files"][0]["path"] = bad_path
            with self.subTest(path=bad_path), self.assertRaisesRegex(ValueError, "exact"):
                self.validate(bundle)
        bundle = copy.deepcopy(self.bundle)
        self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
            'category: "research"', 'category: "productivity"'))
        with self.assertRaisesRegex(ValueError, "category"):
            self.validate(bundle)

    def test_research_cannot_inherit_product_or_unreviewed_links(self):
        for link in (
            "/apps/aligna/", "/apps/clipnest/",
            "https://apps.apple.com/us/app/clipnest-clipboard-tool/id6779928552",
            "https://play.google.com/store/apps/details?id=com.onnellab.aligna",
            "https://library.leeds.ac.uk/info/1401/academic-skills/85/note-making?tracking=1",
            "https://owl.purdue.edu/",
            "https://onnellab.com/blog/ko/keep-durable-research-reading-log/",
        ):
            bundle = copy.deepcopy(self.bundle)
            # Untrusted bundle fields cannot enlarge the closed allowlist.
            bundle["store_urls"] = [link]
            bundle["source_urls"] = [link]
            self.replace_content(bundle, 0, bundle["files"][0]["content"] + f"\n[Unexpected]({link})\n")
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "link/resource"):
                self.validate(bundle)
        for app in ("Aligna", "ClipNest", "[]"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                'related_apps: ""', "related_apps: " + json.dumps(app)))
            with self.subTest(app=app), self.assertRaisesRegex(ValueError, "related apps"):
                self.validate(bundle)

    def test_research_preserves_exact_locale_file_and_checksum_gates(self):
        mutations = (
            lambda b: b["locales"].__setitem__(0, "ko"),
            lambda b: b["locales"].reverse(),
            lambda b: b["files"].pop(),
            lambda b: b["files"].append(copy.deepcopy(b["files"][0])),
            lambda b: b["files"].__setitem__(-1, copy.deepcopy(b["files"][0])),
            lambda b: b["files"][0].__setitem__("content", b["files"][0]["content"] + "tampered"),
        )
        for index, mutate in enumerate(mutations):
            bundle = copy.deepcopy(self.bundle)
            mutate(bundle)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                self.validate(bundle)
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.validate(corrupt_checksum=True)

    def test_research_preserves_html_image_svg_and_date_gates(self):
        for payload in (
            '<script>alert(1)</script>',
            "![Unexpected](https://example.invalid/tracker.png)",
            "[resource]: https://example.invalid/",
            f"![Duplicate](/blog-assets/en/{RESEARCH_SLUG}/workflow-diagram.svg)",
        ):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"] + "\n" + payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.validate(bundle)
        for key in ("published_at", "updated_at", "scheduled_at"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                "---\n", f'---\n{key}: "2026-10-20"\n', 1))
            with self.subTest(date=key), self.assertRaisesRegex(ValueError, "publication dates"):
                self.validate(bundle)
        for svg in (
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
            '<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:red"/></svg>',
            '<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>',
        ):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 1, svg)
            with self.subTest(svg=svg), self.assertRaises(ValueError):
                self.validate(bundle)

    def test_overlay_manifest_uses_closed_profile_not_bundle_claims(self):
        bundle = copy.deepcopy(self.bundle)
        bundle.update(category="productivity", faq_count=99, store_urls=["https://example.invalid/"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            homepage = root / "homepage"
            (homepage / ".git").mkdir(parents=True)
            (homepage / "astro.config.mjs").write_text("// fixture only\n")
            bundle_path = self.write_bundle(root, bundle)

            def fake_render(command, **kwargs):
                Path(command[-1]).write_bytes(b"fixture PNG; renderer not invoked")

            with patch("publishing.homepage_approved_blog_mark", return_value="fixture mark"), \
                    patch("prepare_blog_preview.branded_preview_svg", return_value=b"fixture branded SVG"), \
                    patch("prepare_blog_preview.subprocess.run", side_effect=fake_render) as renderer, \
                    patch("prepare_blog_preview.subprocess.check_output", return_value="fixture-sha\n"):
                record = prepare(bundle_path, homepage, root / "evidence")
            manifest = json.loads((homepage / "preview-candidate.json").read_text())
            self.assertEqual(manifest, {
                "slug": RESEARCH_SLUG, "locales": list(LOCALES),
                "category": "research", "faq_count": 3, "store_urls": [],
                "table_rows": {locale: 3 for locale in LOCALES},
            })
            self.assertEqual(renderer.call_count, 9)
            self.assertEqual(len(record["overlay_sha256"]), 36)
            self.assertFalse(record["publication_dates_added"])
            for locale in LOCALES:
                self.assertTrue((homepage / "src/content/blog" / locale / f"{RESEARCH_SLUG}.md").is_file())


class TagWeaverPreviewBundle(unittest.TestCase):
    add_file = ResearchPreviewBundle.add_file
    replace_content = ResearchPreviewBundle.replace_content
    write_bundle = ResearchPreviewBundle.write_bundle
    validate = ResearchPreviewBundle.validate

    def setUp(self):
        slug = "consistent-album-artist-names"
        self.bundle = {"schema": 1, "state": "UNSCHEDULED_PREVIEW_ONLY",
                       "slug": slug, "locales": list(LOCALES), "files": []}
        for locale in LOCALES:
            draft = json.loads((ROOT / "preview/tagweaver-album-artists" / f"{locale}.json").read_text())
            header = {
                "title": draft["title"], "card_title": draft["title"],
                "category": "music", "language": locale, "slug": slug,
                "status": "review", "related_apps": "TagWeaver",
                "canonical_url": f"https://onnellab.com/blog/{locale.lower()}/{slug}/",
            }
            markdown = "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
                                         for key, value in header.items()) + "---\n\n" + draft["body"]
            markdown += f'\n![Workflow](/blog-assets/{locale}/{slug}/workflow-diagram.svg)\n'
            self.add_file(f"generated/markdown/{locale}/music/{slug}.md", markdown)
            for kind in ("workflow-diagram", "social-card"):
                self.add_file(f"generated/assets/blog/{locale}/{slug}/{kind}.svg",
                              '<svg xmlns="http://www.w3.org/2000/svg"><title>Fixture only</title></svg>')

    def test_nine_exact_reviewed_drafts_validate(self):
        result, digest = self.validate()
        self.assertEqual(result, self.bundle)
        self.assertEqual(len(result["files"]), 27)
        self.assertEqual(len(digest), 64)

    def test_tagweaver_identity_cannot_be_substituted(self):
        for app in ("", "Aligna", "TagWeaver|Aligna"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                'related_apps: "TagWeaver"', "related_apps: " + json.dumps(app)))
            with self.subTest(app=app), self.assertRaisesRegex(ValueError, "reviewed app"):
                self.validate(bundle)
        for link in ("https://example.invalid/", "/apps/aligna/",
                     "https://play.google.com/store/apps/details?id=com.onnellab.aligna"):
            bundle = copy.deepcopy(self.bundle)
            bundle["store_urls"] = [link]
            self.replace_content(bundle, 0, bundle["files"][0]["content"] + f"\n[Foreign]({link})\n")
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "link/resource"):
                self.validate(bundle)

    def test_tagweaver_retains_dates_paths_and_hash_guards(self):
        for key in ("published_at", "updated_at", "scheduled_at"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                "---\n", f'---\n{key}: "2026-10-23"\n', 1))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "publication dates"):
                self.validate(bundle)
        bundle = copy.deepcopy(self.bundle)
        bundle["files"][0]["path"] = bundle["files"][0]["path"].replace("/music/", "/research/")
        with self.assertRaises(ValueError):
            self.validate(bundle)
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.validate(corrupt_checksum=True)

class VaultXTPreviewBundle(unittest.TestCase):
    add_file = ResearchPreviewBundle.add_file
    replace_content = ResearchPreviewBundle.replace_content
    write_bundle = ResearchPreviewBundle.write_bundle
    validate = ResearchPreviewBundle.validate

    def setUp(self):
        slug = "make-long-plain-text-easier-to-navigate"
        self.bundle = {"schema": 1, "state": "UNSCHEDULED_PREVIEW_ONLY",
                       "slug": slug, "locales": list(LOCALES), "files": []}
        for locale in LOCALES:
            draft = json.loads((ROOT / "preview/vaultxt-text-navigation" / f"{locale}.json").read_text())
            header = {
                "title": draft["title"], "card_title": draft["title"],
                "category": "reading", "language": locale, "slug": slug,
                "status": "review", "related_apps": "VaultXT",
                "canonical_url": f"https://onnellab.com/blog/{locale.lower()}/{slug}/",
            }
            markdown = "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
                                         for key, value in header.items()) + "---\n\n" + draft["body"]
            markdown += f'\n![Workflow](/blog-assets/{locale}/{slug}/workflow-diagram.svg)\n'
            self.add_file(f"generated/markdown/{locale}/reading/{slug}.md", markdown)
            for kind in ("workflow-diagram", "social-card"):
                self.add_file(f"generated/assets/blog/{locale}/{slug}/{kind}.svg",
                              '<svg xmlns="http://www.w3.org/2000/svg"><title>Fixture only</title></svg>')

    def test_nine_exact_reviewed_drafts_validate(self):
        result, digest = self.validate()
        self.assertEqual(result, self.bundle)
        self.assertEqual(len(result["files"]), 27)
        self.assertEqual(len(digest), 64)

    def test_vaultxt_identity_cannot_be_substituted(self):
        for app in ("", "Aligna", "VaultXT|Aligna"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                'related_apps: "VaultXT"', "related_apps: " + json.dumps(app)))
            with self.subTest(app=app), self.assertRaisesRegex(ValueError, "reviewed app"):
                self.validate(bundle)
        for link in ("https://example.invalid/", "/apps/aligna/",
                     "https://play.google.com/store/apps/details?id=com.onnellab.aligna"):
            bundle = copy.deepcopy(self.bundle)
            bundle["store_urls"] = [link]
            self.replace_content(bundle, 0, bundle["files"][0]["content"] + f"\n[Foreign]({link})\n")
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "link/resource"):
                self.validate(bundle)

    def test_vaultxt_retains_dates_paths_and_hash_guards(self):
        for key in ("published_at", "updated_at", "scheduled_at"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                "---\n", f'---\n{key}: "2026-10-23"\n', 1))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "publication dates"):
                self.validate(bundle)
        bundle = copy.deepcopy(self.bundle)
        bundle["files"][0]["path"] = bundle["files"][0]["path"].replace("/reading/", "/research/")
        with self.assertRaises(ValueError):
            self.validate(bundle)
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.validate(corrupt_checksum=True)


class SegraPreviewBundle(unittest.TestCase):
    add_file = ResearchPreviewBundle.add_file
    replace_content = ResearchPreviewBundle.replace_content
    write_bundle = ResearchPreviewBundle.write_bundle
    validate = ResearchPreviewBundle.validate

    def setUp(self):
        slug = "choose-safe-audio-working-copy"
        self.bundle = {"schema": 1, "state": "UNSCHEDULED_PREVIEW_ONLY",
                       "slug": slug, "locales": list(LOCALES), "files": []}
        for locale in LOCALES:
            draft = json.loads((ROOT / "preview/segra-working-copy" / f"{locale}.json").read_text())
            header = {
                "title": draft["title"], "card_title": draft["title"],
                "category": "media", "language": locale, "slug": slug,
                "status": "review", "related_apps": "Segra",
                "canonical_url": f"https://onnellab.com/blog/{locale.lower()}/{slug}/",
            }
            markdown = "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
                                         for key, value in header.items()) + "---\n\n" + draft["body"]
            markdown += f'\n![Workflow](/blog-assets/{locale}/{slug}/workflow-diagram.svg)\n'
            self.add_file(f"generated/markdown/{locale}/media/{slug}.md", markdown)
            for kind in ("workflow-diagram", "social-card"):
                self.add_file(f"generated/assets/blog/{locale}/{slug}/{kind}.svg",
                              '<svg xmlns="http://www.w3.org/2000/svg"><title>Fixture only</title></svg>')

    def test_nine_exact_reviewed_drafts_validate(self):
        result, digest = self.validate()
        self.assertEqual(result, self.bundle)
        self.assertEqual(len(result["files"]), 27)
        self.assertEqual(len(digest), 64)

    def test_segra_identity_cannot_be_substituted(self):
        for app in ("", "Aligna", "Segra|Aligna"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                'related_apps: "Segra"', "related_apps: " + json.dumps(app)))
            with self.subTest(app=app), self.assertRaisesRegex(ValueError, "reviewed app"):
                self.validate(bundle)
        for link in ("https://example.invalid/", "/apps/aligna/",
                     "https://play.google.com/store/apps/details?id=com.onnellab.aligna",
                     "https://play.google.com/store/apps/details?id=com.onnellab.segra",
                     "https://onnellab.com/blog/ko/trim-audio-recordings-without-full-editor/"):
            bundle = copy.deepcopy(self.bundle)
            bundle["store_urls"] = [link]
            self.replace_content(bundle, 0, bundle["files"][0]["content"] + f"\n[Foreign]({link})\n")
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "link/resource"):
                self.validate(bundle)

    def test_segra_retains_dates_paths_and_hash_guards(self):
        for key in ("published_at", "updated_at", "scheduled_at"):
            bundle = copy.deepcopy(self.bundle)
            self.replace_content(bundle, 0, bundle["files"][0]["content"].replace(
                "---\n", f'---\n{key}: "2026-10-23"\n', 1))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "publication dates"):
                self.validate(bundle)
        bundle = copy.deepcopy(self.bundle)
        bundle["files"][0]["path"] = bundle["files"][0]["path"].replace("/media/", "/research/")
        with self.assertRaises(ValueError):
            self.validate(bundle)
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.validate(corrupt_checksum=True)


    def test_exact_segra_profile_and_authored_structure(self):
        import re
        slug = "choose-safe-audio-working-copy"
        profile = candidate_profile(slug)
        self.assertEqual(profile["category"], "media")
        self.assertEqual(profile["faq_count"], 3)
        self.assertEqual(profile["app_path"], "/apps/segra/")
        self.assertEqual(profile["source_urls"], [])
        self.assertEqual(profile["store_urls"], ["https://apps.apple.com/us/app/segra-audio-cutter-merger/id6779433972"])
        related = ["trim-audio-recordings-without-full-editor", "verify-audio-clips-before-combining"]
        self.assertEqual(profile["related_slugs"], related)
        for locale in LOCALES:
            self.assertEqual(profile["table_rows"][locale], 4)
            self.assertEqual(allowed_candidate_links(slug, locale), {
                f"/blog-assets/{locale}/{slug}/workflow-diagram.svg", "/apps/segra/",
                *profile["store_urls"], *(f"https://onnellab.com/blog/{locale.lower()}/{r}/" for r in related),
            })
            draft = json.loads((ROOT / "preview/segra-working-copy" / f"{locale}.json").read_text())
            self.assertEqual(len([line for line in draft["body"].splitlines() if line.startswith("|")]), 6)
            self.assertEqual(re.findall(r"^(\d+)\. ", draft["body"], flags=re.MULTILINE), ["1", "2", "3", "4", "5"])
            self.assertEqual(len(re.findall(r"^### ", draft["body"], flags=re.MULTILINE)), 3)


if __name__ == "__main__":
    unittest.main()
