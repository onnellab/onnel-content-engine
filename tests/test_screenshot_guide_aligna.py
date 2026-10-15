import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('aligna_guide', ROOT/'scripts/screenshot_guide.py')
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)


class AlignaScreenshotGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.m = guide.load(ROOT/'data/screenshot_guides/aligna-conflicts-20261016.json')
        self.hashes = {a['local_name']: a['sha256'] for a in self.m['assets']}
        for name in self.hashes:
            (self.root/name).write_bytes(b'unit-test-only, not a production screenshot')
        self.hash_mock = patch.object(guide, 'sha256', side_effect=lambda p: self.hashes[Path(p).name])
        self.hash_mock.start()
        self.addCleanup(self.hash_mock.stop)

    def reject(self, path, value):
        m = copy.deepcopy(self.m)
        target = m
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with self.assertRaises(guide.GuideError):
            guide.validate(m, self.root)

    def test_exact_contract_is_not_recording_or_upload_approval(self):
        result = guide.validate(self.m, self.root)
        self.assertFalse(result['runtime_recording_attestation'])
        self.assertFalse(result['upload_authorized_by_cli'])
        self.assertEqual(result['asset_hashes'], self.hashes)
        self.assertEqual(self.m, guide.ALIGNA_CONTRACT)

    def test_reject_changed_scope_source_copy_and_metadata(self):
        cases = []
        def leaves(value, path):
            if isinstance(value, dict):
                for key, child in value.items():
                    leaves(child, path+[key])
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    leaves(child, path+[index])
            else:
                replacement = not value if isinstance(value, bool) else value+1 if isinstance(value, int) else value+' tampered'
                cases.append((path, replacement))
        leaves(self.m, [])
        cases += [(['schema_version'], True), (['slides', 0, 'seconds'], True),
                  (['metadata', 'made_for_kids'], 0),
                  (['assets'], []),
                  (['assets', 0, 'local_name'], '../01.png')]

        for path, value in cases:
            with self.subTest(path=path):
                self.reject(path, value)

    def test_unknown_fields_and_extra_assets_fail_closed(self):
        for key, value in [('recording', 'pretend.mp4'), ('upload_authorized', True)]:
            m = copy.deepcopy(self.m)
            m[key] = value
            with self.assertRaises(guide.GuideError):
                guide.validate(m, self.root)
        self.reject(['assets'], self.m['assets']+[self.m['assets'][0]])

    def test_missing_file(self):
        (self.root/'04.png').unlink()
        with self.assertRaisesRegex(guide.GuideError, 'unsafe_asset_path'):
            guide.validate(self.m, self.root)

    def test_symlink_file(self):
        (self.root/'04.png').unlink()
        (self.root/'04.png').symlink_to(self.root/'outside.png')
        with self.assertRaisesRegex(guide.GuideError, 'unsafe_asset_path'):
            guide.validate(self.m, self.root)

    def test_actual_wrong_bytes_fail(self):
        self.hash_mock.stop()
        with self.assertRaisesRegex(guide.GuideError, 'asset_integrity'):
            guide.validate(self.m, self.root)

    def test_existing_output_is_preserved(self):
        with self.assertRaisesRegex(guide.GuideError, 'output_exists'):
            guide.render(self.m, self.root, self.root)

    def test_geometry_change_fails_before_encoder(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is an optional local render dependency')
        for name in self.hashes:
            Image.new('RGB', (1080, 1920)).save(self.root/name)
        with patch.object(guide.subprocess, 'run') as encoder:
            with self.assertRaisesRegex(guide.GuideError, 'source_geometry_changed'):
                guide.render(self.m, self.root, self.root/'render')
            encoder.assert_not_called()

    def test_exact_timing_encoder_and_probe_contract(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is an optional local render dependency')
        for name in self.hashes:
            Image.new('RGB', (1080, 2160)).save(self.root/name)
        self.hash_mock.stop()
        def digest(path):
            path = Path(path)
            return self.hashes.get(path.name) or hashlib.sha256(path.read_bytes()).hexdigest()
        def encode(args, **kwargs):
            self.assertEqual(args[args.index('-vf')+1], 'fps=30')
            self.assertEqual(args[args.index('-frames:v')+1], '450')
            self.assertEqual(args[args.index('-threads')+1], '2')
            self.assertIn('-an', args)
            self.assertIn('-nostdin', args)
            self.assertEqual(kwargs['timeout'], 180)
            Path(args[-1]).write_bytes(b'unit-test fake MP4; never upload')
        valid = {'streams': [{'codec_name': 'h264', 'width': 1080, 'height': 1920,
                             'r_frame_rate': '30/1', 'pix_fmt': 'yuv420p',
                             'nb_frames': '450'}], 'format': {'duration': '15.000000'}}
        with patch.object(guide, 'sha256', side_effect=digest), \
             patch.object(guide.subprocess, 'run', side_effect=encode), \
             patch.object(guide.subprocess, 'check_output', return_value=json.dumps(valid).encode()):
            result = guide.render(self.m, self.root, self.root/'exact')
            self.assertEqual(result['seconds'], 15)
            self.assertFalse(result['audio'])
            self.assertEqual(len(result['text_bounds']), 18)
            for item in result['text_bounds']:
                x0, y0, x1, y1 = item['bbox']
                self.assertTrue(60 <= x0 < x1 <= 1020)
                self.assertTrue(64 <= y0 < y1 <= 1880)
        bad_cases = []
        for label, field, value in [('short', 'nb_frames', '449'),
                                    ('long', 'nb_frames', '451'),
                                    ('pixel', 'pix_fmt', 'yuv444p'),
                                    ('fps', 'r_frame_rate', '25/1')]:
            bad = copy.deepcopy(valid)
            bad['streams'][0][field] = value
            bad_cases.append((label, bad))
        bad = copy.deepcopy(valid)
        bad['streams'].append({'codec_type': 'audio'})
        bad_cases.append(('audio', bad))
        bad = copy.deepcopy(valid)
        bad['format']['duration'] = '14.900000'
        bad_cases.append(('duration', bad))
        for label, bad in bad_cases:
            with self.subTest(label=label), \
                 patch.object(guide, 'sha256', side_effect=digest), \
                 patch.object(guide.subprocess, 'run', side_effect=encode), \
                 patch.object(guide.subprocess, 'check_output', return_value=json.dumps(bad).encode()):
                with self.assertRaises(guide.GuideError):
                    guide.render(self.m, self.root, self.root/label)

    def test_real_reviewed_source(self):
        self.hash_mock.stop()
        assets = ROOT/'assets/aligna'
        if not (assets/'04.png').is_file():
            self.skipTest('Optional materialized production screenshot not present')
        result = guide.validate(self.m, assets)
        self.assertEqual(result['asset_hashes'], self.hashes)

if __name__ == '__main__':
    unittest.main()
