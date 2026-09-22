from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_playlists


class PlaylistTests(unittest.TestCase):
    def test_airship_routes_to_travel_and_uplifting(self):
        result = aether_playlists.classify(
            "Airship Over the Cloud Sea",
            "Skybound fantasy flight theme with hopeful travel energy",
            "skybound_flight",
        )
        self.assertEqual(
            ["all", "roads", "uplifting"],
            result,
        )

    def test_cozy_inn_routes_to_town_and_rest(self):
        result = aether_playlists.classify(
            "The Inn Beneath Golden Lanterns",
            "Cozy fantasy inn and tavern theme",
            "",
        )
        self.assertEqual(
            ["all", "towns", "rest"],
            result,
        )
    def test_ruins_routes_to_exploration(self):
        result = aether_playlists.classify(
            "Through the Ruins of Celestia",
            "Ancient JRPG ruins exploration theme",
            "",
        )
        self.assertIn("all", result)
        self.assertIn("nature", result)
        self.assertNotIn("towns", result)

    def test_unknown_track_is_not_forced_into_wrong_theme(self):
        self.assertEqual(
            ["all"],
            aether_playlists.classify("A Story That Never Ends", "", ""),
        )

    def test_catalog_title_alias_trims_malformed_style_suffix(self):
        catalog = [{
            "title": "The Last Light Over Seren Fields Style:",
            "style": "Warm sunset field theme",
        }]
        title, style = aether_playlists._style_for_title(
            "The Last Light Over Seren Fields 🌾 Fantasy RPG Music",
            catalog,
        )
        self.assertEqual("The Last Light Over Seren Fields", title)
        self.assertEqual("Warm sunset field theme", style)

    def test_queue_jobs_excludes_nonpublication_states(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = {"jobs": {
                "a": {"status": "published", "upload": {"video_id": "published123"}},
                "b": {"status": "scheduled", "upload": {"video_id": "scheduled123"}},
                "c": {"status": "forced_private", "upload": {"video_id": "hidden123"}},
                "d": {"status": "reconcile_required", "upload": {"video_id": "uncertain123"}},
            }}
            (root / "queue.json").write_text(json.dumps(data), encoding="utf-8")
            jobs = aether_playlists._queue_jobs(root)
        self.assertEqual({"published123", "scheduled123"}, set(jobs))

    def test_dry_run_has_no_provider_calls(self):
        with patch.object(aether_playlists, "YouTube", side_effect=AssertionError("network")):
            result = aether_playlists.sync(Path("/tmp/not-used"), execute=False)
        self.assertEqual("planned", result["state"])
        self.assertEqual(list(aether_playlists.PLAYLISTS), result["playlists"])


if __name__ == "__main__":
    unittest.main()
