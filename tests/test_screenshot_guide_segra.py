import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('next_two_guide', ROOT/'scripts/screenshot_guide.py')
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)

def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, path+(key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, path+(index,))
    else:
        yield path, value

class SegraGuide(unittest.TestCase):
    def cases(self):
        for name, constant in [('segra-file-order-20261030', 'SEGRA_CONTRACT')]:
            yield name, constant, json.loads((ROOT/'data/screenshot_guides'/f'{name}.json').read_text())

    def test_manifests_exact_contracts(self):
        for name, constant, manifest in self.cases():
            self.assertEqual(guide.canonical(manifest), guide.canonical(getattr(guide, constant)))
            self.assertEqual(manifest['channel_id'], guide.CHANNEL)
            self.assertEqual(sum(s['seconds'] for s in manifest['slides']), 15)
            self.assertEqual(manifest['metadata']['audio'], 'none')
            self.assertFalse(manifest['source']['signed_release_capture_attested'])

    def test_every_leaf_change_rejected_before_assets(self):
        for name, constant, manifest in self.cases():
            for path, value in leaves(manifest):
                altered = copy.deepcopy(manifest)
                node = altered
                for key in path[:-1]: node = node[key]
                node[path[-1]] = not value if isinstance(value, bool) else value+1 if isinstance(value, int) else value+' altered'
                with self.subTest(guide=name, path=path), self.assertRaises(guide.GuideError):
                    guide.validate(altered, '/nonexistent')

    def test_extra_and_missing_fields_rejected(self):
        for name, constant, manifest in self.cases():
            altered = copy.deepcopy(manifest); altered['unreviewed'] = True
            with self.assertRaises(guide.GuideError): guide.validate(altered, '/nonexistent')
            for key in manifest:
                altered = copy.deepcopy(manifest); del altered[key]
                with self.subTest(guide=name, missing=key), self.assertRaises((guide.GuideError, KeyError, TypeError)):
                    guide.validate(altered, '/nonexistent')

    def test_missing_asset_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, constant, manifest in self.cases():
                with self.assertRaisesRegex(guide.GuideError, 'unsafe_asset_path'): guide.validate(manifest, tmp)

    def test_changed_asset_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, constant, manifest in self.cases():
                (Path(tmp)/manifest['assets'][0]['local_name']).write_bytes(b'not approved source')
                with self.assertRaisesRegex(guide.GuideError, 'asset_integrity'): guide.validate(manifest, tmp)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'outside'; target.write_bytes(b'data')
            for name, constant, manifest in self.cases():
                path = Path(tmp)/manifest['assets'][0]['local_name']; path.symlink_to(target)
                with self.assertRaisesRegex(guide.GuideError, 'unsafe_asset_path'): guide.validate(manifest, tmp)

    def test_valid_assets_never_authorize_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, constant, manifest in self.cases():
                raw = b'offline test fixture'; digest = hashlib.sha256(raw).hexdigest()
                altered = copy.deepcopy(manifest); altered['assets'][0]['sha256'] = digest
                (Path(tmp)/altered['assets'][0]['local_name']).write_bytes(raw)
                with patch.object(guide, constant, altered): result = guide.validate(altered, tmp)
                self.assertFalse(result['runtime_recording_attestation'])
                self.assertFalse(result['upload_authorized_by_cli'])

    def test_wrong_geometry_rejected_before_encoder(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            for name, constant, manifest in self.cases():
                path = Path(tmp)/manifest['assets'][0]['local_name']; Image.new('RGB', (1080, 1920)).save(path)
                altered = copy.deepcopy(manifest); altered['assets'][0]['sha256'] = guide.sha256(path)
                with patch.object(guide, constant, altered), patch.object(guide.subprocess, 'run') as encode:
                    with self.assertRaisesRegex(guide.GuideError, 'source_geometry_changed'):
                        guide.render(altered, tmp, Path(tmp)/name)
                    encode.assert_not_called()

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, constant, manifest in self.cases():
                raw = b'fixture'; altered = copy.deepcopy(manifest); altered['assets'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
                (Path(tmp)/altered['assets'][0]['local_name']).write_bytes(raw)
                output = Path(tmp)/name; output.mkdir(); keep = output/'keep'; keep.write_text('original')
                with patch.object(guide, constant, altered), self.assertRaisesRegex(guide.GuideError, 'output_exists'):
                    guide.render(altered, tmp, output)
                self.assertEqual(keep.read_text(), 'original')

if __name__ == '__main__': unittest.main()
