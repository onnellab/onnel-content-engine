"""Offline regression tests for the integration-only, nonpublishing gate."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_blog_review_integration as gate


def rows_fixture():
    rows = []
    for _, profile in gate.BUNDLES:
        for locale in profile.LOCALES:
            rows.append({"id": str(len(rows)), "slug": profile.SLUG,
                         "primary_language": locale, "status": "review",
                         "category": profile.CATEGORY, "related_apps": profile.RELATED_APP,
                         "canonical_path": f"generated/markdown/{locale}/{profile.CATEGORY}/{profile.SLUG}.md",
                         "scheduled_at": "", "published_at": "", "published_url": ""})
    rows.extend({"id": f"idea-{i}", "slug": f"idea-{i}", "status": "idea"} for i in range(8))
    return rows


class AggregateRegistrationTests(unittest.TestCase):
    def test_complete_review_registration(self):
        gate.validate_rows(rows_fixture())

    def test_missing_bundle_rejected(self):
        with self.assertRaises(ValueError):
            gate.validate_rows(rows_fixture()[9:])

    def test_duplicate_locale_rejected(self):
        rows = rows_fixture()
        rows[1]["primary_language"] = rows[0]["primary_language"]
        with self.assertRaises(ValueError):
            gate.validate_rows(rows)

    def test_duplicate_id_rejected(self):
        rows = rows_fixture()
        rows[-1]["id"] = rows[0]["id"]
        with self.assertRaises(ValueError):
            gate.validate_rows(rows)

    def test_registration_mutations_rejected(self):
        for field, value in (("status", "scheduled"), ("category", "other"),
                             ("related_apps", "other"), ("canonical_path", "wrong.md"),
                             ("scheduled_at", "2026-10-27"), ("published_at", "2026-10-27"),
                             ("published_url", "https://example.com/")):
            with self.subTest(field=field):
                rows = rows_fixture()
                rows[0][field] = value
                with self.assertRaises(ValueError):
                    gate.validate_rows(rows)

    def test_minimum_ideas_unchanged(self):
        with self.assertRaises(ValueError):
            gate.validate_rows(rows_fixture()[:-1])

    def test_manifest_bundle_cannot_be_absent(self):
        with self.assertRaises(ValueError):
            gate.validate_fingerprints(Path("/unused"), {"native_manifests": {}})

    def test_all_five_exact_native_commands(self):
        with patch.object(gate.subprocess, "run") as run:
            gate.run_gates(Path("/disposable"))
        self.assertEqual(len(run.call_args_list), 5)
        self.assertEqual([call.args[0][1:] for call in run.call_args_list],
                         [[str(Path("/disposable/scripts") / args[0]), *args[1:]]
                          for args in gate.vault.GATES])
        self.assertTrue(all(call.kwargs["check"] and call.kwargs["cwd"] == Path("/disposable")
                            and call.kwargs["timeout"] == 180 for call in run.call_args_list))

    def test_gate_failure_stops_later_commands(self):
        with patch.object(gate.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "gate")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                gate.run_gates(Path("/disposable"))
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
