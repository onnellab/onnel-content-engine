"""Deterministic contract checks for source-authored public release notes."""

import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_note_source import LOCALES, localized_content, validate_note


def fixture(version="1.2.3+45"):
    return {
        "version": version,
        "locales": {
            code: "- User-visible change in " + code
            for code in LOCALES
        },
    }


class ReleaseNoteSourceTest(unittest.TestCase):
    def test_requires_real_text_in_all_nine_languages(self):
        note = validate_note("sample", fixture())
        self.assertEqual(set(note["locales"]), set(LOCALES))
        missing = fixture()
        missing["locales"].pop("fr")
        with self.assertRaises(ValueError):
            validate_note("sample", missing)

    def test_rejects_untranslated_copies(self):
        copy = fixture()
        copy["locales"]["ja"] = copy["locales"]["en"]
        with self.assertRaisesRegex(ValueError, "copied"):
            validate_note("sample", copy)

    def test_rejects_generic_version_announcements(self):
        copy = fixture()
        copy["locales"]["en"] = "Sample 1.2.3 is now available on iOS."
        with self.assertRaisesRegex(ValueError, "generic"):
            validate_note("sample", copy)

    def test_localized_content_matches_only_public_binary_version(self):
        notes = {"sample": validate_note("sample", fixture())}
        self.assertIsNone(localized_content("sample", "Sample", "1.2.2", notes))
        result = localized_content("sample", "Sample", "1.2.3", notes)
        self.assertEqual(result["changesKo"], ["User-visible change in ko"])
        self.assertEqual(len(result["localizations"]), 9)
        self.assertEqual(result["localizations"]["ja"]["changes"], ["User-visible change in ja"])

    def test_plain_text_is_allowed_for_existing_aligna_source(self):
        sample = fixture()
        sample["locales"] = {code: f"Improved layout: {code}" for code in LOCALES}
        self.assertEqual(validate_note("aligna", sample), sample)


if __name__ == "__main__":
    unittest.main()
