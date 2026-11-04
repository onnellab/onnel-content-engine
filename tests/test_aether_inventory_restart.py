"""Offline regressions for the owned-inventory restart, without worker imports.

Compile the actual guard function definitions, not a second implementation.
No production module imports, credentials, live API, job queue, generator,
renderer, upload or subprocess are used. Full worker tests remain separate.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import types
import time
import unicodedata
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "aether_single.py"
CHANNEL = "UC" + "x" * 22
PLAYLIST = "UU" + "x" * 22
TARGET = "Fixture Journey"


class FixtureVideoError(Exception):
    pass


def load_guard():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    names = {"_clean", "_normalized_title", "RemoteInventoryUnverified",
             "require_no_owned_title_match", "_require_no_owned_title_match_once",
             "_recover_owned_inventory_exact"}
    nodes = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if {n.name for n in nodes} != names:
        raise AssertionError("The production inventory guard is incomplete")
    namespace = {"VideoError": FixtureVideoError, "YouTube": object,
                 "API": "https://www.googleapis.com/youtube/v3/",
                 "re": re, "unicodedata": unicodedata, "urlencode": urlencode, "time": time}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return types.SimpleNamespace(**namespace)


guard = load_guard()


def vid(number):
    return f"{number:011d}"


class ReadOnlyInventory:
    """Deterministic paged responses; unexpected writes always fail the test."""
    channel = CHANNEL

    def __init__(self, *, fault=None, persistent=False, retry_ids=None,
                 match=None, privacy="private", missing=False, count=67):
        self.ids = [vid(n) for n in range(67)]
        self.fault, self.persistent = fault, persistent
        self.retry_ids = retry_ids
        self.match, self.privacy, self.missing = match, privacy, missing
        self.count, self.scans, self.calls = count, 0, []
        self.details_seen = {1: set(), 2: set()}

    def headers(self):
        return {}  # No credential material, not even fixture bearer headers.

    def request(self, method, url, **kwargs):
        if method != "GET":
            raise AssertionError("Only GET is allowed in this fixture")
        route = urlsplit(url).path.rsplit("/", 1)[-1]
        query = parse_qs(urlsplit(url).query)
        self.calls.append((route, query))
        if route == "channels":
            self.scans += 1
            if self.fault == "transport":
                raise FixtureVideoError("network_uncertain")
            owner = CHANNEL if self.fault != "owner" else "UC" + "y" * 22
            return 200, {}, {"items": [{
                "id": owner, "contentDetails": {"relatedPlaylists": {"uploads": PLAYLIST}},
                "statistics": {"videoCount": str(self.count)}}]}
        if route == "playlistItems":
            size = int(query["maxResults"][0])
            start = int(query.get("pageToken", ["0"])[0])
            ids = self.retry_ids if self.scans == 2 and self.retry_ids is not None else self.ids
            current = list(ids[start:start + size])
            active = self.scans == 1 or self.persistent
            if active and self.fault in {"overlap", "invalid", "within"} and start == size:
                if self.fault == "overlap":
                    current.insert(0, ids[size - 1])
                elif self.fault == "within":
                    current.append(current[0])
                else:
                    current.append(["malformed"])
            data = {"items": [{"contentDetails": {"videoId": x}} for x in current]}
            if start + size < len(ids):
                data["nextPageToken"] = str(start + size)
            if self.fault == "cycle":
                data["nextPageToken"] = "50"
            return 200, {}, data
        if route == "videos":
            requested = query["id"][0].split(",")
            if self.missing:
                requested = requested[:-1]
            self.details_seen[self.scans].update(requested)
            items = []
            for key in requested:
                title = TARGET + " ✨" if key == self.match else "Another Fixture"
                owner = CHANNEL if self.fault != "details_owner" else "UC" + "y" * 22
                items.append({"id": key, "snippet": {"channelId": owner, "title": title},
                              "status": {"privacyStatus": self.privacy}})
            return 200, {}, {"items": items}
        raise AssertionError("Unexpected fixture endpoint")


class InventoryRestartTests(unittest.TestCase):
    def check(self, api):
        return guard.require_no_owned_title_match(api, TARGET)

    def failure(self, api):
        with self.assertRaises(guard.RemoteInventoryUnverified) as caught:
            self.check(api)
        self.assertEqual("aether_single_remote_inventory_unverified", str(caught.exception))
        return caught.exception.diagnostic

    def test_normal_67_videos_use_one_scan(self):
        api = ReadOnlyInventory()
        self.assertIsNone(self.check(api))
        self.assertEqual(1, api.scans)
        self.assertEqual(set(api.ids), api.details_seen[1])
        self.assertEqual(5, len(api.calls))

    def test_second_page_overlap_restarts_from_channel_with_smaller_pages(self):
        api = ReadOnlyInventory(fault="overlap")
        self.assertIsNone(self.check(api))
        self.assertEqual(2, api.scans)
        pages = [q for name, q in api.calls if name == "playlistItems"]
        self.assertEqual(["50", "50", "25", "25", "25"],
                         [q["maxResults"][0] for q in pages])
        self.assertNotIn("pageToken", pages[2])
        self.assertEqual(set(api.ids), api.details_seen[2])

    def test_transient_duplicate_within_page_recovers_only_after_full_scan(self):
        api = ReadOnlyInventory(fault="within")
        self.assertIsNone(self.check(api))
        self.assertEqual(set(api.ids), api.details_seen[2])

    def test_transient_malformed_id_recovers_only_after_full_scan(self):
        api = ReadOnlyInventory(fault="invalid")
        self.assertIsNone(self.check(api))
        self.assertEqual(2, api.scans)
        self.assertEqual(set(api.ids), api.details_seen[2])

    def test_persistent_overlap_never_deduplicates_to_success(self):
        api = ReadOnlyInventory(fault="overlap", persistent=True)
        diagnostic = self.failure(api)
        # Two failed paginated scans plus an independent exact-recovery owner read.
        # This fixture has no authoritative playlist totals, so it must still HOLD.
        self.assertEqual(3, api.scans)
        self.assertEqual("exact_inventory_total_unverified",
                         diagnostic["exact_recovery_failure"]["stage"])
        self.assertEqual("duplicate_across_pages", diagnostic["reason"])
        self.assertEqual(2, diagnostic["inventory_attempts"])
        self.assertEqual(50, diagnostic["first_failure"]["videos_seen"])
        self.assertEqual(25, diagnostic["videos_seen"])

    def test_persistent_within_page_duplicate_stays_blocked(self):
        diagnostic = self.failure(ReadOnlyInventory(fault="within", persistent=True))
        self.assertEqual("duplicate_within_page", diagnostic["reason"])

    def test_persistent_unhashable_id_is_safe_blocker_not_type_error(self):
        diagnostic = self.failure(ReadOnlyInventory(fault="invalid", persistent=True))
        self.assertEqual("invalid_video_id", diagnostic["reason"])
        self.assertEqual(2, diagnostic["inventory_attempts"])

    def test_restart_cannot_forget_previously_seen_video(self):
        api = ReadOnlyInventory(fault="overlap", retry_ids=[vid(n) for n in range(1, 68)])
        diagnostic = self.failure(api)
        self.assertEqual("uploads_missing_after_restart", diagnostic["stage"])
        self.assertEqual(1, diagnostic["missing_details"])

    def test_valid_ids_on_bad_page_must_also_be_present_after_restart(self):
        ids = [vid(n) for n in range(66)] + [vid(100)]
        diagnostic = self.failure(ReadOnlyInventory(fault="invalid", retry_ids=ids))
        self.assertEqual("uploads_missing_after_restart", diagnostic["stage"])

    def test_partial_restart_is_not_union_with_first_scan(self):
        diagnostic = self.failure(ReadOnlyInventory(fault="overlap", retry_ids=[vid(n) for n in range(50, 67)]))
        self.assertEqual("uploads_missing_after_restart", diagnostic["stage"])
        self.assertEqual(17, diagnostic["videos_seen"])

    def test_collision_on_retry_blocks_all_privacy_states(self):
        for privacy in ("public", "private", "unlisted"):
            with self.subTest(privacy=privacy):
                api = ReadOnlyInventory(fault="overlap", match=vid(66), privacy=privacy)
                with self.assertRaisesRegex(FixtureVideoError, "existing_remote_title_requires_reconcile"):
                    self.check(api)
                self.assertEqual(2, api.scans)

    def test_initial_title_collision_is_not_retried(self):
        api = ReadOnlyInventory(match=vid(0))
        with self.assertRaisesRegex(FixtureVideoError, "existing_remote_title_requires_reconcile"):
            self.check(api)
        self.assertEqual(1, api.scans)

    def test_missing_details_still_fail_after_only_one_detail_retry(self):
        api = ReadOnlyInventory(missing=True)
        diagnostic = self.failure(api)
        self.assertEqual("video_details_missing_after_second_read", diagnostic["stage"])
        self.assertEqual(1, api.scans)
        self.assertEqual(2, sum(name == "videos" for name, _ in api.calls))
        self.assertNotIn("inventory_attempts", diagnostic)

    def test_foreign_channel_is_not_retried(self):
        api = ReadOnlyInventory(fault="owner")
        self.assertEqual("owner_channel_mismatch", self.failure(api)["stage"])
        self.assertEqual(1, api.scans)

    def test_foreign_video_owner_is_not_retried(self):
        api = ReadOnlyInventory(fault="details_owner")
        self.assertEqual("video_owner_or_metadata_mismatch", self.failure(api)["stage"])
        self.assertEqual(1, api.scans)

    def test_invalid_privacy_is_not_retried(self):
        api = ReadOnlyInventory(privacy="invalid")
        self.assertEqual("video_title_or_privacy_invalid", self.failure(api)["stage"])
        self.assertEqual(1, api.scans)

    def test_transport_failure_does_not_start_another_scan(self):
        api = ReadOnlyInventory(fault="transport")
        with self.assertRaisesRegex(FixtureVideoError, "network_uncertain"):
            self.check(api)
        self.assertEqual(1, api.scans)

    def test_count_shortfall_is_still_blocked(self):
        api = ReadOnlyInventory(count=68)
        self.assertEqual("uploads_less_than_public_count", self.failure(api)["stage"])
        self.assertEqual(1, api.scans)

    def test_repeated_page_token_does_not_prove_completion(self):
        api = ReadOnlyInventory(fault="cycle")
        self.assertEqual("uploads_page_token_invalid_or_repeated", self.failure(api)["stage"])
        self.assertEqual(1, api.scans)

    def test_diagnostics_do_not_include_ids_titles_urls_or_credentials(self):
        diagnostic = self.failure(ReadOnlyInventory(fault="overlap", persistent=True))
        text = json.dumps(diagnostic)
        for excluded in (CHANNEL, PLAYLIST, TARGET, vid(0), "https://", "Authorization"):
            self.assertNotIn(excluded, text)

    def test_inventory_remains_get_only_and_uses_minimal_fields(self):
        api = ReadOnlyInventory(fault="overlap")
        self.check(api)
        self.assertTrue(all("fields" in query for _, query in api.calls))
        self.assertTrue(all("processingDetails" not in str(query) for _, query in api.calls))
        self.assertTrue(all(name in {"channels", "playlistItems", "videos"} for name, _ in api.calls))


class DeadlineSourceTests(unittest.TestCase):
    def test_each_worker_inventory_check_immediately_rechecks_exact_deadline(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        worker = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "worker")
        checks = 0
        for node in ast.walk(worker):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, [])
                if not isinstance(block, list):
                    continue
                for index, statement in enumerate(block):
                    if (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                            and isinstance(statement.value.func, ast.Name)
                            and statement.value.func.id == "require_no_owned_title_match"):
                        checks += 1
                        deadline = block[index + 1]
                        self.assertIsInstance(deadline, ast.Expr)
                        self.assertIsInstance(deadline.value, ast.Call)
                        self.assertEqual("check_publication_window", deadline.value.func.id)
                        self.assertEqual('job["slot"]', ast.unparse(deadline.value.args[1]).replace("'", '"'))
        self.assertEqual(2, checks)
        helper = next(n for n in ast.walk(worker) if isinstance(n, ast.FunctionDef)
                      and n.name == "check_publication_window")
        text = ast.unparse(helper)
        self.assertIn("publish_slot_stale(current_slot)", text)
        self.assertIn("aether_single_publish_time_stale", text)
        self.assertIn("validate(current_job", text)
        self.assertIn("expected_sha=manual['request_sha256']", text)


if __name__ == "__main__":
    unittest.main()
