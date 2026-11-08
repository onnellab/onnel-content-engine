import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guide_copy_quality', ROOT / 'scripts/screenshot_guide.py')
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)


class CopyQualityTests(unittest.TestCase):
    def test_word_wrap_preserves_words_and_does_not_truncate(self):
        text = 'Find the playlist button'
        lines = guide.prepare_caption_lines(text, len, 15)
        self.assertEqual(lines, ['Find the', 'playlist button'])
        self.assertEqual(' '.join(lines), text)

    def test_wrap_exact_boundary(self):
        self.assertEqual(guide.prepare_caption_lines('One two', len, 7), ['One two'])

    def test_reject_long_word_instead_of_shrinking(self):
        with self.assertRaisesRegex(guide.GuideError, 'unbreakable'):
            guide.prepare_caption_lines('indivisible', len, 4)

    def test_reject_excess_lines(self):
        with self.assertRaisesRegex(guide.GuideError, 'too_many_lines'):
            guide.prepare_caption_lines('one two six', len, 3, 2)

    def test_reject_controls_empty_and_bad_dimensions(self):
        for text, width, lines in [('', 10, 2), ('a\nb', 10, 2), ('a\tb', 10, 2),
                                   ('a', float('nan'), 2), ('a', True, 2),
                                   ('a', -1, 2), ('a', 10, True), ('a', 10, 4)]:
            with self.subTest(text=text, width=width, lines=lines):
                with self.assertRaises(guide.GuideError):
                    guide.prepare_caption_lines(text, len, width, lines)

    def test_bad_measurements_fail_closed(self):
        for value in [float('nan'), float('inf'), -1, True, '10']:
            with self.subTest(value=value), self.assertRaisesRegex(guide.GuideError, 'measure_invalid'):
                guide.prepare_caption_lines('hello', lambda _: value)

    def test_all_historical_approved_manifests_pass_timing_without_mutation(self):
        manifests = []
        for path in (ROOT / 'data/screenshot_guides').glob('*.json'):
            data = json.loads(path.read_text())
            if isinstance(data, dict) and data.get('kind') == 'screenshot_guide' and 'slides' in data:
                manifests.append((path, data))
        self.assertGreaterEqual(len(manifests), 13)
        for path, data in manifests:
            with self.subTest(path=path.name):
                before = copy.deepcopy(data)
                result = guide.audit_copy_timing(data)
                self.assertEqual(data, before)
                self.assertFalse(result['human_comprehension_verified'])
                self.assertEqual(len(result['slides']), len(data['slides']))

    def test_timing_boundary_and_overload(self):
        m = {'locale': 'en', 'slides': [{'heading': 'a' * 19, 'caption': 'b' * 20, 'seconds': 2}]}
        self.assertEqual(guide.audit_copy_timing(m)['slides'][0]['characters_per_second'], 20)
        m['slides'][0]['caption'] += 'b'
        with self.assertRaisesRegex(guide.GuideError, 'reading_time'):
            guide.audit_copy_timing(m)

    def test_timing_rejects_invalid_inputs(self):
        good = {'locale': 'en', 'slides': [{'heading': 'Find', 'caption': 'Playlists', 'seconds': 5}]}
        for seconds in [True, 0, 1.99, float('nan'), float('inf'), '5']:
            m = copy.deepcopy(good)
            m['slides'][0]['seconds'] = seconds
            with self.subTest(seconds=seconds), self.assertRaises(guide.GuideError):
                guide.audit_copy_timing(m)
        for key, value in [('locale', 'ko'), ('slides', []), ('slides', [None])]:
            m = copy.deepcopy(good)
            m[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(guide.GuideError):
                guide.audit_copy_timing(m)
        for value in ['', None, 'line\nbreak']:
            m = copy.deepcopy(good)
            m['slides'][0]['caption'] = value
            with self.subTest(value=value), self.assertRaises(guide.GuideError):
                guide.audit_copy_timing(m)

    def test_glyph_bounds_and_separation(self):
        image = (229, 300, 850, 1680)
        guide.audit_text_box((60, 64, 1020, 100), [], image)
        guide.audit_text_box((60, 108, 1020, 150), [(60, 64, 1020, 100)], image)
        for bounds in [(59, 64, 100, 100), (60, 63, 100, 100),
                       (60, 64, 1021, 100), (60, 1840, 100, 1881),
                       (60, 64, 60, 100), (60, 64, float('nan'), 100)]:
            with self.subTest(bounds=bounds), self.assertRaises(guide.GuideError):
                guide.audit_text_box(bounds, [], image)

    def test_rejects_label_or_screenshot_overlap_including_gap(self):
        image = (229, 300, 850, 1680)
        for bounds, occupied in [((60, 107, 300, 150), [(60, 64, 300, 100)]),
                                 ((230, 280, 500, 295), []),
                                 ((230, 400, 500, 450), []),
                                 ((230, 1687, 500, 1700), [])]:
            with self.subTest(bounds=bounds), self.assertRaisesRegex(guide.GuideError, 'overlaps'):
                guide.audit_text_box(bounds, occupied, image)

    def test_timing_failure_precedes_output_creation_or_encoder(self):
        m = {'locale': 'en', 'slides': [{'heading': 'a' * 300, 'caption': 'b', 'seconds': 5}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(guide, 'validate', return_value={}), patch.object(guide.subprocess, 'run') as encoder:
            output = Path(tmp) / 'must-not-exist'
            with self.assertRaisesRegex(guide.GuideError, 'reading_time'):
                guide.render(m, 'unused', output)
            self.assertFalse(output.exists())
            encoder.assert_not_called()


if __name__ == '__main__':
    unittest.main()
