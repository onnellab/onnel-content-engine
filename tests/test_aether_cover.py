from __future__ import annotations
import base64
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aether_cover


class Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.payload[:size]


class CoverTests(unittest.TestCase):
    def test_prompt_is_text_free_landscape_and_lane_specific(self):
        prompt = aether_cover.cover_prompt("Sails Above the Cloud Sea", "Buoyant flight theme", "skybound_flight")
        for expected in ["full-bleed 16:9", "upper-left", "Do not render any letters", "floating islands", "No black bands", "no letterboxing", "edge-to-edge"]:
            self.assertIn(expected, prompt)

    def test_request_uses_text_and_image_modalities(self):
        captured = {}
        raw = b"x" * 2048
        payload = json.dumps({"candidates": [{"content": {"parts": [
            {"text": "generated"},
            {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(raw).decode()}},
        ]}}]}).encode()
        def send(req):
            captured["body"] = json.loads(req.data)
            return Response(payload)
        aether_cover._request("aether-music-123", "prompt", "token", send=send)
        self.assertEqual(["TEXT", "IMAGE"], captured["body"]["generationConfig"]["responseModalities"])
        self.assertEqual("16:9", captured["body"]["generationConfig"]["imageConfig"]["aspectRatio"])

    def test_request_parses_one_inline_image(self):
        raw = b"x" * 2048
        payload = json.dumps({"candidates": [{"content": {"parts": [{
            "inlineData": {"mimeType": "image/png", "data": base64.b64encode(raw).decode()}
        }]}}]}).encode()
        image, mime = aether_cover._request("aether-music-123", "prompt", "token", send=lambda _: Response(payload))
        self.assertEqual(raw, image)
        self.assertEqual("image/png", mime)

    def test_title_wrap_is_bounded(self):
        self.assertEqual("The Airship Above\nCloudrest Harbor", aether_cover._wrap_title("The Airship Above Cloudrest Harbor"))
        with self.assertRaises(Exception):
            aether_cover._wrap_title(" ".join(["longword"] * 20))

    def test_svg_uses_larger_ivory_title_gold_brand_and_shadow(self):
        svg = aether_cover._title_svg(
            "Sails Above the Cloud Sea",
            {"x":132,"first_y":150,"shadow_opacity":.38},
        )
        self.assertIn("#F2E8D5", svg)
        self.assertIn("#C7AA6B", svg)
        self.assertIn("font-size:72px", svg)
        self.assertIn("opacity:0.38", svg)
        self.assertIn("Aether Inn", svg)
        self.assertIn("Baskerville", svg)
        self.assertIn('class="diamond"', svg)
        self.assertNotIn("<rect", svg)

    def test_layout_moves_when_upper_left_has_low_contrast(self):
        scores = {
            (132,150):(-65,.88,.90), (132,360):(-55,.82,.85),
            (1050,150):(60,.19,.22), (1050,360):(50,.25,.29),
            (600,150):(-8,.55,.59), (132,600):(63,.19,.23),
            (600,600):(65,.16,.20), (1050,600):(115,.06,.08),
        }
        def sample(_path,x,y,_lines):
            score,bright,low=scores[(x,y)]
            return {"mean_luma":150,"std_luma":35,"bright_fraction":bright,
                    "warm_fraction":.10,"low_contrast_fraction":low,
                    "mean_contrast":85,"score":score}
        with patch.object(aether_cover, "_sample_text_region", side_effect=sample):
            layout=aether_cover.choose_title_layout(Path("/tmp/fake.png"),"Sails Above the Cloud Sea")
        self.assertEqual((1050,150),(layout["x"],layout["first_y"]))
        self.assertEqual(.38,layout["shadow_opacity"])

    def test_letterbox_gate_rejects_dark_uniform_edge(self):
        with patch.object(aether_cover, "media_info", return_value={"streams":[{"codec_type":"video","width":1920,"height":1080}]}), \
             patch.object(aether_cover, "_luma_strip", side_effect=[
                 {"mean":18.0,"std":3.0,"dark_fraction":.94},
                 {"mean":170.0,"std":24.0,"dark_fraction":0.0},
                 {"mean":175.0,"std":22.0,"dark_fraction":0.0},
             ]):
            with self.assertRaisesRegex(Exception, "letterbox_detected"):
                aether_cover.validate_full_bleed_background(Path("/tmp/fake.png"))

    def test_dry_run_does_not_request_or_write(self):
        settings = {"project_id": "aether-music-123"}
        with patch.object(aether_cover, "load_settings", return_value=settings), \
             patch.object(aether_cover, "_request", side_effect=AssertionError("network")):
            result = aether_cover.generate_cover("A", "B", "quiet_road", Path("/tmp/not-used"), execute=False)
        self.assertEqual("planned", result["state"])
        self.assertEqual(0, result["generation_count"])
        self.assertEqual(3, result["max_generation_attempts"])


if __name__ == "__main__":
    unittest.main()
