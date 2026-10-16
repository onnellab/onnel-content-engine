"""Closed allowlists for both supported nonpublishing preview candidates."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_blog_preview import candidate_profile, allowed_candidate_links, LOCALES

class PreviewCandidateProfiles(unittest.TestCase):
    def test_unknown_candidate_and_locale_fail_closed(self):
        for slug in ("", "../aligna", "other-product", "design-consistent-file-naming-system-extra"):
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
        for locale in LOCALES:
            self.assertEqual(profile["table_rows"][locale], 3)
            self.assertEqual(allowed_candidate_links(slug, locale), {
                f"/blog-assets/{locale}/{slug}/workflow-diagram.svg",
                "/apps/clipnest/",
                "https://apps.apple.com/us/app/clipnest-clipboard-tool/id6779928552",
                f"https://onnellab.com/blog/{locale.lower()}/reuse-copied-text-snippets-iphone/",
            })

    def test_profiles_do_not_share_mutable_state(self):
        slug = "design-consistent-file-naming-system"
        profile = candidate_profile(slug)
        profile["store_urls"].append("https://example.invalid/")
        self.assertNotIn("https://example.invalid/", allowed_candidate_links(slug, "en"))

if __name__ == "__main__":
    unittest.main()
