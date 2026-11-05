from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_playlists as playlists


class FakeApi:
    profile = "aether_inn"
    channel = "UC_AETHER"

    def __init__(self):
        self.items = []
        self.calls = []
        self.verified = False

    def verify(self):
        self.verified = True

    def headers(self, **kwargs):
        return kwargs

    def request(self, method, url, body=None, *args, **kwargs):
        assert self.verified
        self.calls.append((method, url))
        assert urlsplit(url).path.endswith("/playlists")
        if method == "POST":
            data = json.loads(body)
            assert data["snippet"]["title"] == "Aether Inn Sleep"
            data["snippet"]["channelId"] = self.channel
            data["id"] = "PL_SLEEP"
            self.items.append(data)
            return 200, {}, data
        params = parse_qs(urlsplit(url).query)
        items = self.items
        if "id" in params:
            items = [i for i in items if i["id"] == params["id"][0]]
        return 200, {}, {"items": items}


class SleepTests(unittest.TestCase):
    def test_sleep_requires_explicit_series(self):
        self.assertNotIn("sleep", playlists.classify("Moonlit Sleep Inn", "calm sleep music"))
        self.assertEqual(["sleep"], playlists.classify(
            "Moonlit Sleep Inn", "calm", series=playlists.SLEEP_SERIES))

    def test_all_legacy_catalog_rows_stay_out_of_sleep(self):
        for row in playlists._catalog():
            self.assertNotIn("sleep", playlists.classify(row["title"], row.get("style", "")))

    def test_create_only_sleep_and_reuse_exact_id(self):
        api = FakeApi()
        first = playlists.ensure_playlist("sleep", execute=True, api_factory=lambda: api)
        second = playlists.ensure_playlist("sleep", execute=True, api_factory=lambda: api)
        self.assertEqual(first, second)
        self.assertEqual("verified", first["state"])
        self.assertEqual(0, first["videos_added"])
        self.assertEqual(1, sum(method == "POST" for method, _ in api.calls))

    def test_duplicate_titles_fail_without_post(self):
        api = FakeApi()
        api.items = [
            {"id": "PL_ONE", "snippet": {"title": "Aether Inn Sleep"}},
            {"id": "PL_TWO", "snippet": {"title": "Aether Inn Sleep"}},
        ]
        with self.assertRaisesRegex(playlists.UploadError, "duplicate_playlist"):
            playlists.ensure_playlist("sleep", execute=True, api_factory=lambda: api)
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_foreign_profile_has_no_provider_calls(self):
        api = FakeApi()
        api.profile = "onnellab"
        with self.assertRaisesRegex(playlists.UploadError, "aether_profile_required"):
            playlists.ensure_playlist("sleep", execute=True, api_factory=lambda: api)
        self.assertFalse(api.verified)
        self.assertEqual([], api.calls)

    def test_foreign_readback_fails(self):
        api = FakeApi()
        api.items = [{"id": "PL_SLEEP", "snippet": {
            "title": "Aether Inn Sleep", "channelId": "UC_FOREIGN"},
            "status": {"privacyStatus": "public"}}]
        with self.assertRaisesRegex(playlists.UploadError, "verification_failed"):
            playlists.ensure_playlist("sleep", execute=True, api_factory=lambda: api)
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_dry_ensure_has_no_provider_calls(self):
        with patch.object(playlists, "YouTube", side_effect=AssertionError("network")):
            result = playlists.ensure_playlist("sleep")
        self.assertEqual("planned", result["state"])

    def test_unknown_key_has_no_provider_calls(self):
        with patch.object(playlists, "YouTube", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(playlists.UploadError, "key_invalid"):
                playlists.ensure_playlist("unknown", execute=True)

    def _records(self, job, catalog):
        class VideoApi:
            channel = "UC_AETHER"
            def headers(self, **kwargs):
                return {}
            def request(self, *args, **kwargs):
                return 200, {}, {"items": [{"id": "VIDEO", "snippet": {
                    "channelId": self.channel, "title": "Moonlit Rest"},
                    "status": {"privacyStatus": "public"}}]}
        with patch.object(playlists, "_uploaded_video_ids", return_value=["VIDEO"]), \
             patch.object(playlists, "_queue_jobs", return_value={"VIDEO": job}), \
             patch.object(playlists, "_catalog", return_value=catalog):
            return playlists._video_records(VideoApi(), Path("/unused"))

    def test_sleep_record_requires_new_source(self):
        with self.assertRaisesRegex(playlists.UploadError, "sleep_source_required"):
            self._records({"series": playlists.SLEEP_SERIES, "source_kind": "backlog_wav"}, [])

    def test_catalog_cannot_be_reclassified_as_sleep(self):
        with self.assertRaisesRegex(playlists.UploadError, "sleep_source_required"):
            self._records({"series": playlists.SLEEP_SERIES, "source_kind": "purpose_composed_sleep"},
                          [{"title": "Moonlit Rest", "style": "legacy"}])

    def test_new_sleep_record_routes_only_to_sleep(self):
        result = self._records({"series": playlists.SLEEP_SERIES,
                                "source_kind": "purpose_composed_sleep"}, [])
        self.assertEqual(["sleep"], result[0]["playlists"])

    def test_plan_is_not_production_authorization(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / "data/aether_sleep_pilot.json").read_text())
        self.assertFalse(plan["production_enabled"])
        self.assertFalse(plan["paid_generation_authorized"])
        self.assertIsNone(plan["publish_slots"])
        self.assertEqual(3, len(plan["concepts"]))
        self.assertEqual([], plan["existing_track_ids"])


if __name__ == "__main__":
    unittest.main()
