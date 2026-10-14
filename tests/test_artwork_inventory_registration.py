"""Offline data-only registration contracts. No app code, network, or rendering."""
import ast
from contextlib import redirect_stdout, redirect_stderr
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import register_artwork_inventory as registration


def png(width=3, height=4, color=1):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    pixels = (b"\0" + bytes([color, 0, 0]) * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project, self.site = self.base / "app", self.base / "site"
        self.project.mkdir()
        self.site.mkdir()
        self.shared = "assets/store_promo/shared"
        self.renderer = "assets/store_promo/render_selected.py"
        self.write("pubspec.yaml", "name: example\nversion: 1.2.3+4\n")
        # These deliberately fail if anyone tries to execute/import an input.
        for name in (*registration.SHARED_FILES, "header_template.svg", "search_template.svg"):
            self.write(f"{self.shared}/{name}", "raise RuntimeError('DO NOT EXECUTE APP CODE')\n")
        self.write(self.renderer, "raise RuntimeError('DO NOT EXECUTE SELECTED RENDERER')\n")
        self.write("release/store_upload.json", {"ios": {"bundle_id": "com.example.app"},
                                                "android": {"package_name": "com.example.app"}})
        self.write("assets/onnellab_release_identity.json", {"version": "1.2.3+4", "source_commit": "a" * 40})
        self.site_locale("en")
        self.android_locale("en")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, value, data, *, site=False):
        path = (self.site if site else self.project) / value
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict):
            data = json.dumps(data)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data)
        return path

    def site_locale(self, loc):
        for i in range(1, 7):
            self.write(f"src/content/apps/example/assets/screenshots/{loc}/{i}.png", png(color=i), site=True)

    def fingerprint(self, kind):
        return registration.sha(b"".join((self.project / self.shared / name).read_bytes()
                                        for name in registration.FINGERPRINT_FILES[kind]))

    def capture(self, source, loc, kind):
        return self.write(str(Path(source).with_suffix(".capture.json")), {
            "version": "1.2.3+4", "source_commit": "a" * 40,
            "package_name" if kind == "android" else "bundle_id": "com.example.app",
            "locale": loc, "kind": kind, "method": "adb" if kind == "android" else "simctl",
            "device_id": "existing-device", "screen_confirmed": True,
            "installed_binary_sha256": "b" * 64, "installed_identity_sha256": "c" * 64,
            "raw_path": source, "raw_sha256": registration.sha((self.project / source).read_bytes())})

    def android_locale(self, loc, count=6, *, size=(3, 4), receipts=False):
        for index in range(1, count + 1):
            path = f"assets/store_promo/generated/{loc}/android/{index:02d}.png"
            source = f"assets/store_promo/raw/{loc}/android/{index:02d}.png"
            self.write(source, png(color=index))
            output = self.write(path, png(*size, color=index))
            svg = self.write(str(Path(path).with_suffix(".svg")), f"<svg>actual source {index}</svg>")
            self.write(str(Path(path).with_suffix(".provenance.json")), {
                "schema_version": 1, "renderer_sha256": self.fingerprint("android"), "source": source,
                "source_sha256": registration.sha((self.project / source).read_bytes()),
                "source_size": [3, 4], "output": path, "canvas": list(size),
                "png_sha256": registration.sha(output.read_bytes()), "svg_sha256": registration.sha(svg.read_bytes())})
            if receipts:
                self.capture(source, loc, "android")

    def native_locale(self, loc, slot="iphone_medium", count=6, *, size=(3, 4), receipts=False):
        records, specs = [], []
        for index in range(1, count + 1):
            raw_slot = {"duo_inner": "duo/inner", "duo_outer": "duo/outer"}.get(slot, slot)
            source = f"assets/store_promo/raw/{loc}/{raw_slot}/{index:02d}.png"
            self.write(source, png(*size, color=index))
            path = f"assets/store_promo/ios_devices/{slot}/{loc}/{index:02d}.png"
            output = self.write(path, png(*size, color=index))
            svg = self.write(str(Path(path).with_suffix(".svg")), f"<svg>actual source {index}</svg>")
            spec = {"raw": source, "title": "Existing title", "subtitle": "Existing subtitle", "layout": "hero"}
            specs.append(spec)
            records.append({"screen": index, "slot": slot, "locale": loc, "source": source,
                            "source_sha256": registration.sha((self.project / source).read_bytes()),
                            "size": list(size), "spec_sha256": registration.sha(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()),
                            "output_sha256": registration.sha(output.read_bytes()), "svg_sha256": registration.sha(svg.read_bytes())})
            if receipts:
                self.capture(source, loc, slot)
        self.write(f"assets/store_promo/ios_devices/{slot}/{loc}/render_manifest.json",
                   {"schema_version": 1, "renderer_sha256": self.fingerprint("ios"), "screens": records})
        return specs

    def build(self, **kwargs):
        args = dict(project=self.project, site=self.site, slug="example", ipad_supported=False,
                    android_renderer=self.renderer, shared_renderer_dir=self.shared)
        args.update(kwargs)
        return registration.build_inventory(**args)

    def codes(self, report):
        return {item["code"] for item in report["blockers"]}

    def test_partial_draft_uses_only_actual_paths_and_never_creates_evidence(self):
        inventory, report = self.build()
        self.assertEqual(inventory["screenshot_counts"]["android"], 6)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["structural_checks"], "BLOCKED")
        self.assertEqual(report["current_source_and_capture_checks"], "UNVERIFIED")
        self.assertEqual(report["review_checks"], "NOT_PERFORMED")
        self.assertEqual(report["android_presence"], "present")
        self.assertEqual(report["gallery_preference"], "android")
        self.assertIn("missing_group_manifest", self.codes(report))
        self.assertIn("capture_evidence_missing", self.codes(report))
        self.assertIn("missing_required_gallery", self.codes(report))
        self.assertEqual(inventory["assets"][0]["site_path"], "en/1.png")
        for item in inventory["assets"]:
            self.assertTrue((self.project / item["path"]).is_file())
            self.assertNotIn("capture_receipt", item)
            self.assertTrue(all((self.project / name).is_file() for name in item["dependencies"]))
        self.assertFalse((self.project / "release/artwork.json").exists())
        self.assertFalse((self.project / "release/artwork-candidate.json").exists())
        self.assertFalse((self.project / "release/artwork-review.json").exists())

    def test_stale_1080_by_2168_android_is_preserved_and_blocks_instead_of_fallback(self):
        self.android_locale("en", count=1, size=(1080, 2168))
        inventory, report = self.build()
        self.assertEqual(inventory["screenshot_counts"]["android"], 6)
        self.assertEqual(report["assets"][0]["size"], [1080, 2168])
        self.assertTrue(report["assets"][0]["png_valid"])
        self.assertIn("wrong_output_dimensions_or_format", self.codes(report))
        self.assertEqual(report["gallery_preference"], "android")

    def test_corrupt_android_keeps_count_hash_and_actual_header_dimensions(self):
        path = self.project / "assets/store_promo/generated/en/android/01.png"
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        path.write_bytes(raw)
        inventory, report = self.build()
        self.assertEqual(inventory["screenshot_counts"]["android"], 6)
        first = report["assets"][0]
        self.assertEqual(first["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(first["size"], [3, 4])
        self.assertFalse(first["png_valid"])
        self.assertIn("invalid_png", self.codes(report))
        self.assertIn("stale_or_inconsistent_evidence", self.codes(report))

    def test_truncated_header_is_not_a_valid_png(self):
        data = png(1080, 2160)
        result = registration.png_details(data[:33])
        self.assertFalse(result["png_valid"])
        self.assertEqual(result["size"], [1080, 2160])

    def test_oversized_deflate_output_is_rejected_with_bounded_decompression(self):
        original = png()
        compressed = zlib.compress(b"\0" * 1000000)
        body = b"IDAT" + compressed
        chunk = struct.pack(">I", len(compressed)) + body + struct.pack(">I", zlib.crc32(body))
        forged = original[:33] + chunk + original[-12:]
        decompressor = zlib.decompressobj()
        wrapped = unittest.mock.Mock(wraps=decompressor)
        # The length mismatch short-circuits before decoder attributes matter.
        with patch.object(registration.zlib, "decompressobj", return_value=wrapped):
            result = registration.png_details(forged)
        self.assertFalse(result["png_valid"])
        self.assertEqual(wrapped.decompress.call_args.args[1], (3 * 3 + 1) * 4 + 1)

    def test_excessive_png_dimensions_are_rejected_before_decompression(self):
        with patch.object(registration.zlib, "decompressobj") as decode:
            result = registration.png_details(png(10001, 2))
        decode.assert_not_called()
        self.assertFalse(result["png_valid"])
        self.assertEqual(result["size"], [10001, 2])

    def test_only_actual_native_outputs_are_registered_not_legacy_general_ios(self):
        self.native_locale("en", count=1, size=(1206, 2622), receipts=True)
        self.write("assets/store_promo/generated/en/ios/01.png", png(1242, 2688))
        inventory, report = self.build()
        native = [item for item in report["assets"] if item["kind"] == "iphone_medium"]
        self.assertEqual(len(native), 1)
        self.assertEqual(native[0]["size"], [1206, 2622])
        self.assertIn("capture_receipt", native[0])
        self.assertEqual(report["excluded_legacy_ios"][0]["size"], [1242, 2688])
        self.assertTrue(all("generated/en/ios" not in item["path"] for item in inventory["assets"]))
        self.assertIn("missing_group_manifest", self.codes(report))
        self.assertIn("native_spec_coverage", self.codes(report))
        self.assertIn("missing_native_capture_pair", self.codes(report))

    def test_existing_native_capture_pair_is_hashed_and_size_checked(self):
        self.native_locale("en", count=1, size=(1206, 2622), receipts=True)
        ready = "assets/store_promo/captures/iphone_medium/en/01.png"
        self.write(ready, png(1206, 2622))
        inventory, report = self.build()
        asset = next(item for item in inventory["assets"] if item["kind"] == "iphone_medium")
        self.assertIn(ready, asset["dependencies"])
        self.assertTrue(any(file["path"] == ready and file["size"] == [1206, 2622] for file in report["files"]))
        self.assertFalse(any(item["code"] in {"missing_native_capture_pair", "invalid_native_capture_pair"}
                             and item["subject"] == "en/iphone_medium/1" for item in report["blockers"]))
        self.write(ready, png(1242, 2688))
        _, report = self.build()
        self.assertIn("invalid_native_capture_pair", self.codes(report))

    def test_duo_normalized_capture_paths_use_actual_pose_directories(self):
        self.native_locale("en", slot="duo_outer", count=1)
        ready = "assets/store_promo/duo/outer/en/01.png"
        self.write(ready, png())
        inventory, _ = self.build()
        asset = next(item for item in inventory["assets"] if item["kind"] == "duo_outer")
        self.assertIn(ready, asset["dependencies"])
        self.assertNotIn("assets/store_promo/captures/duo_outer/en/01.png", asset["dependencies"])

    def test_stale_capture_version_and_source_hash_are_reported(self):
        self.android_locale("en", receipts=True)
        file = self.project / "assets/store_promo/raw/en/android/01.capture.json"
        data = json.loads(file.read_text())
        data.update(version="1.0.0+1", raw_sha256="0" * 64)
        file.write_text(json.dumps(data))
        inventory, report = self.build()
        self.assertIn("capture_receipt", inventory["assets"][0])
        errors = [item["detail"] for item in report["blockers"] if item["subject"].endswith("01.capture.json")]
        self.assertTrue(any("version" in error for error in errors))
        self.assertTrue(any("raw_sha256" in error for error in errors))
        capture_files = [item for item in report["files"] if item["path"].endswith(".capture.json")]
        self.assertEqual(len(capture_files), 6)

    def test_capture_screen_confirmation_requires_actual_boolean_true(self):
        self.android_locale("en", receipts=True)
        file = self.project / "assets/store_promo/raw/en/android/01.capture.json"
        data = json.loads(file.read_text())
        data["screen_confirmed"] = 1
        file.write_text(json.dumps(data))
        _, report = self.build()
        self.assertIn("invalid_capture_evidence", self.codes(report))

    def test_source_missing_does_not_invent_a_raw_path(self):
        (self.project / "assets/store_promo/raw/en/android/01.png").unlink()
        inventory, report = self.build()
        self.assertNotIn("raw_path", inventory["assets"][0])
        self.assertIn("missing_file", self.codes(report))

    def test_missing_and_malformed_provenance_do_not_drop_present_android(self):
        directory = self.project / "assets/store_promo/generated/en/android"
        (directory / "01.provenance.json").unlink()
        (directory / "02.provenance.json").write_text("{")
        inventory, report = self.build()
        self.assertEqual(inventory["screenshot_counts"]["android"], 6)
        self.assertEqual(len([item for item in inventory["assets"] if item["kind"] == "android"]), 6)
        self.assertIn("invalid_json", self.codes(report))
        self.assertIn("missing_render_provenance", self.codes(report))
        self.assertEqual(report["gallery_preference"], "android")

    def test_source_locales_not_in_site_are_not_silently_dropped(self):
        self.android_locale("ko", count=2)
        inventory, report = self.build()
        self.assertEqual(inventory["locales"], ["en", "ko"])
        self.assertEqual(report["observed_counts_by_locale"]["ko"]["android"], 2)
        self.assertEqual(inventory["screenshot_counts"]["android"], 6)
        self.assertIn("locale_coverage_mismatch", self.codes(report))
        self.assertIn("gallery_count_mismatch", self.codes(report))

    def test_manifest_only_locale_is_included_and_blocks(self):
        self.write(registration.GROUPS["ios-screens"], {
            "schema_version": 1, "ipad_supported": False, "locales": {"en": {}, "ko": {}}})
        inventory, report = self.build()
        self.assertEqual(inventory["locales"], ["en", "ko"])
        self.assertIn("locale_coverage_mismatch", self.codes(report))

    def test_nested_or_non_png_android_prevents_absence_declaration(self):
        for path in (self.project / "assets/store_promo/generated/en/android").glob("*.png"):
            path.unlink()
        self.write("assets/store_promo/generated/en/android/nested/01.png", png())
        self.write("assets/store_promo/generated/en/android/02.jpg", b"existing non-PNG image")
        inventory, report = self.build()
        self.assertEqual(inventory["screenshot_counts"]["android"], 2)
        self.assertEqual(report["android_presence"], "present")
        self.assertEqual(report["gallery_preference"], "android")
        self.assertIn("unexpected_android_images", self.codes(report))

    def test_actual_android_absence_is_explicit_without_claiming_fallback_ready(self):
        for path in (self.project / "assets/store_promo/generated/en/android").glob("*.png"):
            path.unlink()
        self.native_locale("en")
        inventory, report = self.build()
        self.assertEqual(inventory["screenshot_counts"]["android"], 0)
        self.assertEqual(report["android_presence"], "absent")
        self.assertEqual(report["status"], "BLOCKED")
        iphone = [asset for asset in inventory["assets"] if asset["kind"] == "iphone_medium"]
        self.assertEqual(iphone[-1]["site_path"], "en/6.png")

    def test_android_image_appearing_after_scan_invalidates_absence(self):
        for path in (self.project / "assets/store_promo/generated/en/android").glob("*.png"):
            path.unlink()
        real_block = registration.Builder.block
        changed = []

        def add_after_scan(builder, code, subject, detail):
            if code == "missing_play_source" and not changed:
                self.write("assets/store_promo/generated/en/android/01.png", png())
                changed.append(True)
            return real_block(builder, code, subject, detail)

        with patch.object(registration.Builder, "block", new=add_after_scan):
            with self.assertRaisesRegex(registration.RegistrationError, "directory changed"):
                self.build()
        self.assertEqual(changed, [True])

    def test_locale_directory_appearing_after_scan_invalidates_coverage(self):
        real_block = registration.Builder.block
        changed = []

        def add_after_scan(builder, code, subject, detail):
            if code == "missing_play_source" and not changed:
                self.write("assets/store_promo/generated/ko/android/01.png", png())
                changed.append(True)
            return real_block(builder, code, subject, detail)

        with patch.object(registration.Builder, "block", new=add_after_scan):
            with self.assertRaisesRegex(registration.RegistrationError, "directory changed"):
                self.build()

    def test_duplicate_numeric_destination_and_source_indices_are_refused(self):
        for site in (True, False):
            value = ("src/content/apps/example/assets/screenshots/en/01.png" if site else
                     "assets/store_promo/generated/en/android/1.png")
            path = self.write(value, png(), site=site)
            with self.subTest(site=site), self.assertRaisesRegex(registration.RegistrationError, "Duplicate gallery"):
                self.build()
            path.unlink()

    def test_incomplete_numeric_destination_mapping_never_guesses_filename(self):
        (self.site / "src/content/apps/example/assets/screenshots/en/6.png").unlink()
        inventory, report = self.build()
        self.assertIn("site_mapping_incomplete", self.codes(report))
        self.assertTrue(all("site_path" not in item for item in inventory["assets"]))

    def test_noncontiguous_android_indices_are_blocked(self):
        directory = self.project / "assets/store_promo/generated/en/android"
        (directory / "06.png").rename(directory / "07.png")
        _, report = self.build()
        self.assertIn("noncontiguous_android_gallery", self.codes(report))
        self.assertIn("source_site_mapping_mismatch", self.codes(report))

    def test_unsafe_references_are_refused_even_if_missing(self):
        path = self.project / "assets/store_promo/generated/en/android/01.provenance.json"
        original = json.loads(path.read_text())
        for source in ("../outside.png", "/tmp/outside.png", "assets/../outside.png", "assets\\outside.png"):
            path.write_text(json.dumps({**original, "source": source}))
            with self.subTest(source=source), self.assertRaises(registration.RegistrationError):
                self.build()

    def test_symlinked_asset_parent_and_input_root_are_refused(self):
        path = self.project / "assets/store_promo/generated/en/android/01.png"
        path.unlink()
        outside = self.base / "outside.png"
        outside.write_bytes(png())
        path.symlink_to(outside)
        with self.assertRaisesRegex(registration.RegistrationError, "Symlinks"):
            self.build()
        path.unlink()
        path.write_bytes(png())
        link = self.base / "linked-app"
        link.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(registration.RegistrationError, "Symlinks"):
            self.build(project=link)

    def test_nonregular_asset_refused_without_reading_fifo(self):
        path = self.project / "assets/store_promo/generated/en/android/01.png"
        path.unlink()
        os.mkfifo(path)
        with self.assertRaisesRegex(registration.RegistrationError, "Nonregular"):
            self.build()

    def test_replaced_fifo_cannot_block_read_between_lstat_and_open(self):
        path = self.project / "assets/store_promo/generated/en/android/01.png"
        real_open = os.open
        replaced = []

        def replace_before_open(name, flags, *args, **kwargs):
            if name == "01.png" and not replaced:
                self.assertTrue(flags & os.O_NONBLOCK)
                self.assertTrue(flags & os.O_CLOEXEC)
                path.unlink()
                os.mkfifo(path)
                replaced.append(True)
            return real_open(name, flags, *args, **kwargs)

        with patch.object(registration.os, "open", side_effect=replace_before_open):
            with self.assertRaisesRegex(registration.RegistrationError, "changed"):
                registration.read_bytes(self.project, str(path.relative_to(self.project)))
        self.assertEqual(replaced, [True])

    def test_renderer_must_be_existing_regular_explicit_python_file(self):
        for name in ("missing.py", "../outside.py", self.renderer + "; touch marker"):
            with self.subTest(name=name), self.assertRaises(registration.RegistrationError):
                self.build(android_renderer=name)
        self.write("wrong.sh", "exit 0")
        with self.assertRaises(registration.RegistrationError):
            self.build(android_renderer="wrong.sh")

    def test_explicit_renderer_args_are_preserved_without_execution(self):
        inventory, _ = self.build(android_render_args=("--locale", "all", "literal; never execute"))
        self.assertEqual(inventory["android_render_command"],
                         [self.renderer, "--locale", "all", "literal; never execute"])
        source = Path(registration.__file__).read_text()
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        names = {name.name for node in imports if isinstance(node, ast.Import) for name in node.names}
        self.assertNotIn("subprocess", names)
        self.assertNotIn("importlib", names)

    def test_ipad_support_must_be_explicit_boolean(self):
        with self.assertRaises(registration.RegistrationError):
            self.build(ipad_supported="false")
        _, report = self.build(ipad_supported=True)
        self.assertTrue(any(item["subject"] == "ipad_13" for item in report["blockers"]))

    def test_invalid_duplicate_native_manifest_screen_is_refused(self):
        self.native_locale("en", count=1)
        path = self.project / "assets/store_promo/ios_devices/iphone_medium/en/render_manifest.json"
        data = json.loads(path.read_text())
        data["screens"].append(data["screens"][0])
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(registration.RegistrationError, "duplicate render manifest"):
            self.build()

    def test_header_search_are_registered_with_existing_source_dependencies(self):
        source = "assets/store_promo/raw/en/iphone_medium/01.png"
        self.write(source, png())
        for kind in ("header", "search"):
            output = self.write(f"assets/store_promo/{kind}/en.png", png())
            svg = self.write(f"assets/store_promo/{kind}/en.svg", "<svg/>")
            self.write(f"assets/store_promo/{kind}/en.provenance.json", {
                "schema_version": 1, "kind": kind, "locale": "en", "source": source,
                "source_sha256": registration.sha((self.project / source).read_bytes()),
                "png_sha256": registration.sha(output.read_bytes()), "svg_sha256": registration.sha(svg.read_bytes())})
        self.write(registration.GROUPS["ios-header-search"], {"schema_version": 1, "app_name": "Example", "accent": "lilac",
            "locales": {"en": {kind: {"media": source, "headline": ["Actual copy"]} for kind in ("header", "search")}}})
        inventory, report = self.build()
        placements = [asset for asset in inventory["assets"] if asset["kind"] in {"header", "search"}]
        self.assertEqual(len(placements), 2)
        for asset in placements:
            self.assertIn(source, asset["dependencies"])
            self.assertIn(f"{self.shared}/{asset['kind']}_template.svg", asset["dependencies"])
        self.assertIn("placement_capture_binding_unverified", self.codes(report))
        self.assertTrue(any(item["code"] == "stale_or_inconsistent_evidence" and "config_sha256" in item["detail"]
                            for item in report["blockers"]))

    def test_writes_only_new_external_output_and_refuses_reuse_or_input_locations(self):
        inventory, report = self.build()
        output = self.base / "registration-output"
        before = {str(path.relative_to(self.project)): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        registration.write_registration(output, inventory, report, project=self.project, site=self.site)
        self.assertEqual(json.loads((output / "release/artwork.json").read_text()), inventory)
        self.assertEqual(json.loads((output / "readiness.json").read_text()), report)
        self.assertEqual(sorted(str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()),
                         ["readiness.json", "release/artwork.json"])
        after = {str(path.relative_to(self.project)): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        for target in (output, self.project / "output", self.site / "output", self.base):
            with self.subTest(target=target), self.assertRaises(registration.RegistrationError):
                registration.write_registration(target, inventory, report, project=self.project, site=self.site)

    def test_output_symlink_and_unowned_parent_are_refused(self):
        inventory, report = self.build()
        link = self.base / "linked"
        link.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(registration.RegistrationError, "Symlinks"):
            registration.write_registration(link / "output", inventory, report, project=self.project, site=self.site)
        with patch.object(registration.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(registration.RegistrationError, "owned"):
                registration.write_registration(self.base / "output", inventory, report, project=self.project, site=self.site)

    def test_output_replaced_with_symlink_before_open_cannot_write_into_app(self):
        inventory, report = self.build()
        output = self.base / "new-output"
        real_open = os.open
        replaced = []

        def replace_before_open(name, flags, *args, **kwargs):
            if name == output.name and not replaced:
                output.rmdir()
                output.symlink_to(self.project, target_is_directory=True)
                replaced.append(True)
            return real_open(name, flags, *args, **kwargs)

        with patch.object(registration.os, "open", side_effect=replace_before_open):
            with self.assertRaises((OSError, registration.RegistrationError)):
                registration.write_registration(output, inventory, report, project=self.project, site=self.site)
        self.assertFalse((self.project / "release/artwork.json").exists())
        self.assertFalse((self.project / "readiness.json").exists())

    def test_replaced_output_parent_cannot_redirect_descriptor_relative_writes(self):
        inventory, report = self.build()
        parent = self.base / "staging"
        parent.mkdir()
        parked = self.base / "original-staging"
        output = parent / "new-output"
        real_mkdir = os.mkdir
        replaced = []

        def replace_parent(name, *args, **kwargs):
            if name == output.name and not replaced:
                parent.rename(parked)
                parent.symlink_to(self.project, target_is_directory=True)
                replaced.append(True)
            return real_mkdir(name, *args, **kwargs)

        with patch.object(registration.os, "mkdir", side_effect=replace_parent):
            with self.assertRaises(registration.RegistrationError):
                registration.write_registration(output, inventory, report, project=self.project, site=self.site)
        self.assertFalse((self.project / "new-output").exists())
        self.assertTrue((parked / "new-output/release/artwork.json").is_file())

    def test_cli_writes_blocked_draft_exit_two_without_approval(self):
        output = self.base / "cli-output"
        args = ["--project", str(self.project), "--site", str(self.site), "--slug", "example",
                "--ipad-supported", "false", "--android-renderer", self.renderer,
                "--shared-renderer-dir", self.shared, "--android-render-arg=--all", "--output-dir", str(output)]
        with redirect_stdout(StringIO()) as stdout:
            code = registration.main(args)
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", stdout.getvalue())
        self.assertEqual(json.loads((output / "release/artwork.json").read_text())["android_render_command"][-1], "--all")
        with redirect_stderr(StringIO()):
            self.assertEqual(registration.main(args), 1)


if __name__ == "__main__":
    unittest.main()
