"""Read-only, fail-closed owner upload inventory regressions.

All YouTube responses below are local fixtures. They never read credentials,
run production, make live API requests, or invoke a paid generator.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_single


CHANNEL = "UC" + "x" * 22
PLAYLIST = "UU" + "x" * 22
TARGET = "Across the Frontier Before Sunrise"


def video_id(index):
    # Exactly 11 URL-safe characters, distinct for every fixture video.
    return f"{index:011d}"


class InventoryFixture:
    profile = "aether_inn"
    channel = CHANNEL

    def __init__(self, *, ids=None, title="Other Journey", privacy="public",
                 missing_once=False, missing_always=False, bad_owner=False,
                 duplicate=False, wrong_privacy=False, count=None, cycle=False,
                 bad_video_id=False):
        self.ids = ids if ids is not None else [video_id(1)]
        self.title, self.privacy = title, privacy
        self.missing_once, self.missing_always = missing_once, missing_always
        self.bad_owner, self.duplicate = bad_owner, duplicate
        self.wrong_privacy, self.count = wrong_privacy, count
        self.cycle, self.bad_video_id = cycle, bad_video_id
        self.calls = []
        self.video_calls = 0

    def verify(self):
        return {"channel_verified": True}

    def headers(self):
        return {"Authorization": "Bearer FIXTURE_NOT_REAL"}

    def request(self, method, url, **kwargs):
        if method != "GET":
            raise AssertionError("Read-only inventory may only GET")
        self.calls.append(url)
        query = parse_qs(urlsplit(url).query)
        if "search?" in url:
            return 200, {}, {"items": []}
        if "channels?" in url:
            item = {"id": CHANNEL, "contentDetails": {"relatedPlaylists": {"uploads": PLAYLIST}}}
            if self.count is not None:
                item["statistics"] = {"videoCount": str(self.count)}
            return 200, {}, {"items": [item]}
        if "playlistItems?" in url:
            page_token = query.get("pageToken", [""])[0]
            if self.cycle:
                return 200, {}, {"items": [{"contentDetails": {"videoId": self.ids[0]}}],
                                 "nextPageToken": "repeated"}
            ids = self.ids[:50] if not page_token else self.ids[50:]
            entries = [{"contentDetails": {"videoId": x}} for x in ids]
            if self.duplicate and not page_token:
                entries += entries[:1]
            if self.bad_video_id and not page_token:
                entries[0] = {"contentDetails": {"videoId": ["unsafe"]}}
            result = {"items": entries}
            if not page_token and len(self.ids) > 50:
                result["nextPageToken"] = "page2"
            return 200, {}, result
        if "videos?" in url:
            self.video_calls += 1
            self_test = self.video_calls == 1 and self.missing_once
            requested = query.get("id", [""])[0].split(",")
            if self.missing_always or self_test:
                requested = requested[:-1]
            result = []
            for vid in requested:
                result.append({
                    "id": vid, "snippet": {
                        "channelId": "UC" + "y" * 22 if self.bad_owner else CHANNEL,
                        "title": self.title},
                    "status": {"privacyStatus": "wrong" if self.wrong_privacy else self.privacy},
                })
            return 200, {}, {"items": result}
        raise AssertionError(url)


class OwnedInventoryRegressions(unittest.TestCase):
    def test_full_67_videos_two_pages_and_minimal_fields(self):
        api = InventoryFixture(ids=[video_id(n) for n in range(67)], count=67)
        self.assertIsNone(aether_single.require_no_owned_title_match(api, TARGET))
        self.assertEqual(api.video_calls, 2)
        self.assertEqual(5, len(api.calls))
        videos = [x for x in api.calls if "/videos?" in x]
        self.assertTrue(all(parse_qs(urlsplit(x).query)["part"] == ["snippet,status"] for x in videos))
        self.assertTrue(all("processingDetails" not in x for x in videos))
        self.assertTrue(all("fields=" in x for x in api.calls))
        self.assertFalse(any("POST" in x for x in api.calls))

    def test_missing_bulk_video_recovers_with_one_bounded_read_only_lookup(self):
        api = InventoryFixture(ids=[video_id(1), video_id(2)], missing_once=True)
        self.assertIsNone(aether_single.require_no_owned_title_match(api, TARGET))
        self.assertEqual(2, api.video_calls)
        self.assertEqual(4, len(api.calls))

    def test_missing_video_after_second_get_stays_blocked_and_counts_evidence(self):
        api = InventoryFixture(ids=[video_id(1), video_id(2)], missing_always=True)
        with self.assertRaises(aether_single.RemoteInventoryUnverified) as captured:
            aether_single.require_no_owned_title_match(api, TARGET)
        self.assertEqual(str(captured.exception), "aether_single_remote_inventory_unverified")
        self.assertEqual(captured.exception.diagnostic, {
            "stage": "video_details_missing_after_second_read",
            "pages_checked": 1, "videos_seen": 2, "missing_details": 1,
        })
        self.assertEqual(2, api.video_calls)
        self.assertNotIn(video_id(2), json.dumps(captured.exception.diagnostic))

    def test_private_unlisted_and_public_title_collision_never_prove_absence(self):
        for privacy in ("private", "unlisted", "public"):
            with self.subTest(privacy=privacy):
                api = InventoryFixture(title=TARGET + " ✨", privacy=privacy)
                with self.assertRaisesRegex(aether_single.VideoError, "existing_remote_title_requires_reconcile"):
                    aether_single.require_no_owned_title_match(api, TARGET)

    def test_bad_owner_privacy_and_duplicate_ids_fail_closed_with_stage(self):
        scenarios = [
            ({"bad_owner": True}, "video_owner_or_metadata_mismatch"),
            ({"wrong_privacy": True}, "video_title_or_privacy_invalid"),
            ({"duplicate": True}, "uploads_ids_invalid_or_duplicate"),
            ({"bad_video_id": True}, "uploads_ids_invalid_or_duplicate"),
            ({"count": 99}, "uploads_less_than_public_count"),
            ({"cycle": True}, "uploads_ids_invalid_or_duplicate"),
        ]
        for kwargs, stage in scenarios:
            with self.subTest(kwargs=kwargs):
                api = InventoryFixture(**kwargs)
                with self.assertRaises(aether_single.RemoteInventoryUnverified) as caught:
                    aether_single.require_no_owned_title_match(api, TARGET)
                self.assertEqual(stage, caught.exception.diagnostic["stage"])

    def test_unhashable_privacy_fails_closed_with_safe_diagnostic(self):
        for privacy in ([], {}):
            with self.subTest(privacy=privacy):
                api = InventoryFixture(privacy=privacy)
                with self.assertRaises(aether_single.RemoteInventoryUnverified) as caught:
                    aether_single.require_no_owned_title_match(api, TARGET)
                self.assertEqual("aether_single_remote_inventory_unverified", str(caught.exception))
                self.assertEqual("video_title_or_privacy_invalid", caught.exception.diagnostic["stage"])
                self.assertNotIn(TARGET, json.dumps(caught.exception.diagnostic))

    def test_repeated_token_with_empty_pages_reaches_token_guard(self):
        api = InventoryFixture()
        original_request = api.request

        def empty_page_request(method, url, **kwargs):
            if "playlistItems?" in url:
                self.assertEqual("GET", method)
                api.calls.append(url)
                return 200, {}, {"items": [], "nextPageToken": "repeated"}
            return original_request(method, url, **kwargs)

        api.request = empty_page_request
        with self.assertRaises(aether_single.RemoteInventoryUnverified) as caught:
            aether_single.require_no_owned_title_match(api, TARGET)
        self.assertEqual("uploads_page_token_invalid_or_repeated", caught.exception.diagnostic["stage"])
        self.assertEqual(2, caught.exception.diagnostic["pages_checked"])
        self.assertEqual(0, caught.exception.diagnostic["videos_seen"])
        self.assertEqual(0, api.video_calls)
        self.assertEqual(3, len(api.calls))

    def test_cli_reports_only_safe_reason_and_counts(self):
        failure = aether_single.RemoteInventoryUnverified(
            "video_details_missing_after_second_read", pages_checked=2,
            videos_seen=67, missing_details=1)
        output = StringIO()
        with patch.object(sys, "argv", ["aether_single.py", "worker", "--execute"]), \
             patch.object(aether_single, "worker", side_effect=failure), redirect_stdout(output):
            self.assertEqual(2, aether_single.main())
        doc = json.loads(output.getvalue())
        self.assertEqual("aether_single_remote_inventory_unverified", doc["error"])
        self.assertEqual("video_details_missing_after_second_read",
                         doc["remote_inventory_diagnostic"]["stage"])
        self.assertNotIn("Authorization", output.getvalue())
        self.assertNotIn("https://", output.getvalue())

    def test_failed_preflight_persists_job_without_generating_or_uploading(self):
        api = InventoryFixture(missing_always=True)
        generation = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            root.chmod(0o700)
            with patch.object(aether_single, "publish_slot_stale", return_value=False), \
                 patch.object(aether_single.paid_guard, "require_no_unsettled_intents"), \
                 patch.object(aether_single, "read_catalog", return_value=[]), \
                 patch.object(aether_single, "inspect_candidate",
                              return_value={"metadata_gate": "accepted"}):
                with self.assertRaises(aether_single.RemoteInventoryUnverified):
                    aether_single.worker(
                        root, slot="2099-10-31", title=TARGET,
                        style="An original fictional travel melody",
                        lane="frontier_surge", execute=True, publish=True,
                        api_factory=lambda: api,
                        cover_generator=lambda *a, **k: None,
                        music_generator=lambda *a, **k: generation.append((a, k)))
            state = json.loads((root / "queue.json").read_text())
            self.assertEqual(len(state["jobs"]), 1)
            job = next(iter(state["jobs"].values()))
            self.assertEqual(job["status"], "blocked")
            self.assertIsNone(job["music"])
            self.assertIsNone(job["cover"])
            self.assertFalse(job["upload_eligible"])
            self.assertNotIn("upload", job)
            self.assertEqual("video_details_missing_after_second_read",
                             job["remote_inventory_diagnostic"]["stage"])
            self.assertEqual([], generation)
            self.assertFalse(any("/upload/" in urlsplit(x).path for x in api.calls))


if __name__ == "__main__":
    unittest.main()

