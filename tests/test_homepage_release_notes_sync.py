from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_homepage_release_notes import sync_homepage_release_notes


HEADER = [
    "app_id", "app_slug", "app_name", "platform", "store_url",
    "store_app_id", "store_package", "version", "last_updated",
    "release_notes", "checked_at", "status", "notes",
]


def write_store_versions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class HomepageReleaseNotesSyncTest(unittest.TestCase):
    def test_unknown_public_version_does_not_invent_release_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "store.csv"
            homepage = root / "homepage"
            write_store_versions(store, [{
                "app_id": "APP-0007", "app_slug": "melivra",
                "app_name": "Melivra", "platform": "android",
                "version": "9.9.9", "status": "unchanged",
                "last_updated": "2026-10-21",
            }])
            output = sync_homepage_release_notes(store, homepage, {})
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [])

    def test_unknown_state_does_not_publish_a_matching_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = root / "store.csv"
            site = root / "site"
            write_store_versions(rows, [{
                "app_id": "APP-0002", "app_slug": "tagweaver",
                "app_name": "TagWeaver", "platform": "android",
                "version": "2.5.5", "status": "staged",
                "last_updated": "2026-10-22",
            }])
            source = {"tagweaver": {
                "version": "2.5.5+99",
                "locales": {lang: f"- Test user-visible {lang}" for lang in
                    ("ko", "en", "ja", "zh-Hans", "zh-Hant",
                     "pt-BR", "de", "fr", "es")},
            }}
            output = sync_homepage_release_notes(rows, site, source)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [])

    def test_sync_preserves_history_and_builds_public_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store_versions = root / "store_versions.csv"
            homepage = root / "homepage"
            output = homepage / "src" / "data" / "store-release-notes.json"
            output.parent.mkdir(parents=True)
            output.write_text(
                json.dumps([
                    {
                        "appSlug": "melivra",
                        "appName": "Melivra",
                        "version": "1.0.3",
                        "tag": "v1.0.3",
                        "platform": "Android",
                        "releasedDate": "2026-09-20",
                        "title": "Melivra v1.0.3 (Android)",
                        "summary": "old",
                        "summaryKo": "old",
                        "changes": ["old"],
                        "changesKo": ["old"],
                        "internalGitHubUrl": "",
                    }
                ]),
                encoding="utf-8",
            )
            write_store_versions(
                store_versions,
                [
                    {
                        "app_id": "APP-0007",
                        "app_slug": "melivra",
                        "app_name": "Melivra",
                        "platform": "android",
                        "version": "1.0.4",
                        "last_updated": "2026. 9. 29.",
                        "checked_at": "2026-10-01T08:18:23+09:00",
                        "status": "unchanged",
                    },
                    {
                        "app_id": "APP-0008",
                        "app_slug": "papira",
                        "app_name": "Papira",
                        "platform": "ios",
                        "version": "1.0",
                        "last_updated": "2026-09-24T07:51:43Z",
                        "checked_at": "2026-10-01T08:18:23+09:00",
                        "status": "unchanged",
                    },
                    {
                        "app_id": "APP-0002",
                        "app_slug": "tagweaver",
                        "app_name": "TagWeaver",
                        "platform": "ios",
                        "version": "2.5.2",
                        "last_updated": "2026-09-28T16:41:42Z",
                        "release_notes": "Melivra에서 보낸 음악 파일을 열어 태그를 편집하는 흐름을 개선했어요.",
                        "checked_at": "2026-10-01T08:18:23+09:00",
                        "status": "unchanged",
                    },
                    {
                        "app_id": "APP-0008",
                        "app_slug": "papira",
                        "app_name": "Papira",
                        "platform": "android",
                        "version": "",
                        "checked_at": "2026-10-01T08:18:23+09:00",
                        "status": "manual_check",
                    },
                ],
            )

            localized = {
                slug: {
                    "version": version + "+10",
                    "locales": {
                        locale: "- " + (
                            "Melivra에서 보낸 음악 파일을 더 쉽게 열 수 있어요."
                            if slug == "tagweaver" and locale == "ko"
                            else f"{slug} user-visible improvement ({locale})"
                        )
                        for locale in ("ko", "en", "ja", "zh-Hans", "zh-Hant",
                                       "pt-BR", "de", "fr", "es")
                    },
                }
                for slug, version in (
                    ("melivra", "1.0.4"), ("papira", "1.0"), ("tagweaver", "2.5.2")
                )
            }
            result = sync_homepage_release_notes(store_versions, homepage, localized)
            self.assertEqual(result, output)
            payload = json.loads(output.read_text(encoding="utf-8"))
            by_key = {(item["appSlug"], item["version"]): item for item in payload}

            self.assertIn(("melivra", "1.0.3"), by_key)
            self.assertIn(("melivra", "1.0.4"), by_key)
            self.assertIn(("papira", "1.0"), by_key)
            self.assertIn(("tagweaver", "2.5.2"), by_key)
            self.assertEqual(by_key[("melivra", "1.0.4")]["releasedDate"], "2026-09-29")
            self.assertEqual(by_key[("papira", "1.0")]["platform"], "iOS")
            self.assertIn("Melivra에서 보낸", by_key[("tagweaver", "2.5.2")]["changesKo"][0])
            self.assertIn("user-visible improvement", by_key[("tagweaver", "2.5.2")]["changes"][0])
            self.assertEqual(len(by_key[("tagweaver", "2.5.2")]["localizations"]), 9)
            self.assertNotIn("now available", by_key[("melivra", "1.0.4")]["changes"][0])


if __name__ == "__main__":
    unittest.main()
