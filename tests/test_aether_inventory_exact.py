"""Exact-entry recovery for a repeated uploads item hiding another video.

All data are fictional. No credentials, network, production jobs or media.
"""
from collections import Counter
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from test_aether_inventory_restart import CHANNEL, PLAYLIST, TARGET, guard, vid, FixtureVideoError


class ExactFixture:
    channel = CHANNEL

    def __init__(self, fault=None, collision=None, privacy="public"):
        self.ids = [vid(n) for n in range(67)]
        self.fault, self.collision, self.privacy = fault, collision, privacy
        self.calls, self.exact_reads, self.owner_reads = [], Counter(), 0

    def headers(self):
        return {}

    def row(self, position, key=None):
        key = self.ids[position] if key is None else key
        return {"id": "fixture-item-" + key,
                "contentDetails": {"videoId": key},
                "snippet": {"position": position, "playlistId": PLAYLIST,
                            "resourceId": {"kind": "youtube#video", "videoId": key}}}

    def request(self, method, url, **kwargs):
        if method != "GET":
            raise AssertionError("Inventory recovery cannot write")
        route = urlsplit(url).path.rsplit("/", 1)[-1]
        query = parse_qs(urlsplit(url).query)
        self.calls.append((route, query))
        if route == "channels":
            self.owner_reads += 1
            count = 67 if self.privacy == "public" else 66
            if self.fault == "owner_changed" and self.owner_reads > 1:
                count += 1
            return 200, {}, {"items": [{"id": CHANNEL,
                "contentDetails": {"relatedPlaylists": {"uploads": PLAYLIST}},
                "statistics": {"videoCount": str(count)}}]}
        if route == "search":
            if query.get("forMine") != ["true"] or query.get("type") != ["video"]:
                raise AssertionError("Must discover through authenticated owner search")
            start = int(query.get("pageToken", ["0"])[0])
            candidates = list(self.ids)
            if self.fault == "search_missing":
                candidates.pop(50)
            if self.fault == "search_replaces_observed":
                candidates[0] = vid(999)
            data = {"items": [{"id": {"kind": "youtube#video", "videoId": x}}
                              for x in candidates[start:start + 50]]}
            if start + 50 < len(candidates):
                data["nextPageToken"] = str(start + 50)
            return 200, {}, data
        if route == "playlistItems":
            if query.get("playlistId") != [PLAYLIST]:
                raise AssertionError("Foreign playlist")
            if query.get("fields") == ["pageInfo(totalResults)"]:
                info = None if self.fault == "bad_final_info" else {"totalResults": 68 if self.fault == "total_changed" else 67}
                return 200, {}, {"pageInfo": info}
            if "videoId" in query:
                key = query["videoId"][0]
                self.exact_reads[key] += 1
                position = self.ids.index(key)
                row = self.row(position)
                if key == vid(50):
                    if self.fault == "exact_missing":
                        return 200, {}, {"items": []}
                    if self.fault == "exact_position_conflict":
                        row["snippet"]["position"] = 49
                    if self.fault == "exact_wrong_video":
                        row = self.row(50, vid(49))
                    if self.fault == "exact_foreign_playlist":
                        row["snippet"]["playlistId"] = "UU" + "y" * 22
                    if self.fault == "exact_second_changed" and self.exact_reads[key] == 2:
                        row["id"] += "-changed"
                    if self.fault == "exact_item_conflict":
                        row["id"] = "fixture-item-" + vid(49)
                data = {"items": [row]}
                if self.fault == "exact_has_next" and key == vid(50):
                    data["nextPageToken"] = "unexpected"
                return 200, {}, data
            size = int(query["maxResults"][0])
            start = int(query.get("pageToken", ["0"])[0])
            rows = [self.row(n, vid(49) if n == 50 else None)
                    for n in range(start, min(start + size, 67))]
            if self.fault == "missing_position" and start == 50:
                rows.pop()
            data = {"pageInfo": {"totalResults": 67}, "items": rows}
            if start + size < 67:
                data["nextPageToken"] = str(start + size)
            return 200, {}, data
        if route == "videos":
            keys = query["id"][0].split(",")
            rows = []
            for key in keys:
                if self.fault == "missing_details" and key == vid(50):
                    continue
                rows.append({"id": key, "snippet": {
                    "channelId": "UC" + "y" * 22 if self.fault == "foreign_video" and key == vid(50) else CHANNEL,
                    "title": TARGET + " ✨" if key == self.collision else "Unrelated fictional music"},
                    "status": {"privacyStatus": self.privacy if key == vid(50) else "public"}})
            return 200, {}, {"items": rows}
        raise AssertionError("Unexpected endpoint")


class ExactInventoryTests(unittest.TestCase):
    def test_time_budget_exhaustion_stops_before_another_request(self):
        api = ExactFixture()
        with patch.object(guard.time, "monotonic", side_effect=[0.0, 120.0]):
            with self.assertRaises(guard.RemoteInventoryUnverified) as caught:
                guard._recover_owned_inventory_exact(api, TARGET, set())
        self.assertEqual("exact_inventory_time_limit", caught.exception.diagnostic["stage"])
        self.assertEqual([], api.calls)

    def test_recovers_all_67_positions_not_only_66_distinct_page_videos(self):
        api = ExactFixture()
        result = guard._recover_owned_inventory_exact(api, TARGET, {vid(n) for n in range(50)})
        self.assertEqual({"state": "verified", "method": "owner_search_exact_playlist_crosscheck",
                          "videos_verified": 67, "positions_verified": 67,
                          "identical_exact_passes": 2}, result)
        self.assertEqual({2}, set(api.exact_reads.values()))
        self.assertEqual(67, len(api.exact_reads))

    def test_real_wrapper_reaches_exact_recovery_after_both_sizes_fail(self):
        api = ExactFixture()
        result = guard.require_no_owned_title_match(api, TARGET)
        self.assertEqual(67, result["videos_verified"])
        self.assertEqual(134, sum(api.exact_reads.values()))

    def test_incomplete_inconsistent_and_changed_evidence_never_passes(self):
        faults = {"search_missing", "search_replaces_observed", "exact_missing",
                  "exact_position_conflict", "exact_wrong_video", "exact_foreign_playlist",
                  "exact_second_changed", "exact_item_conflict", "exact_has_next",
                  "missing_details", "foreign_video", "owner_changed", "total_changed",
                  "missing_position", "bad_final_info"}
        for fault in sorted(faults):
            with self.subTest(fault=fault):
                with self.assertRaises(guard.RemoteInventoryUnverified):
                    guard._recover_owned_inventory_exact(ExactFixture(fault), TARGET, {vid(0)})

    def test_missing_target_collision_blocks_even_if_private_or_unlisted(self):
        for privacy in ("public", "private", "unlisted"):
            with self.subTest(privacy=privacy):
                api = ExactFixture(collision=vid(50), privacy=privacy)
                with self.assertRaisesRegex(FixtureVideoError, "existing_remote_title_requires_reconcile"):
                    guard.require_no_owned_title_match(api, TARGET)

    def test_private_and_unlisted_entries_are_checked_not_assumed_absent(self):
        for privacy in ("private", "unlisted"):
            with self.subTest(privacy=privacy):
                result = guard._recover_owned_inventory_exact(ExactFixture(privacy=privacy), TARGET, set())
                self.assertEqual(67, result["videos_verified"])

    def test_failure_keeps_original_blocker_and_safe_recovery_reason(self):
        with self.assertRaises(guard.RemoteInventoryUnverified) as caught:
            guard.require_no_owned_title_match(ExactFixture("exact_missing"), TARGET)
        diagnostic = caught.exception.diagnostic
        self.assertEqual("uploads_ids_invalid_or_duplicate", diagnostic["stage"])
        self.assertEqual("exact_inventory_entry_unresolved", diagnostic["exact_recovery_failure"]["stage"])
        for forbidden in (CHANNEL, PLAYLIST, TARGET, vid(0), "https://", "Authorization"):
            self.assertNotIn(forbidden, str(diagnostic))


if __name__ == "__main__":
    unittest.main()
