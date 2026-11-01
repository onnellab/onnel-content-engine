import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('november_guide',ROOT/'scripts/screenshot_guide.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

class NovemberContracts(unittest.TestCase):
    def cases(self):
        return [(g.CLIPNEST_LANGUAGE_CONTRACT,'clipnest'),(g.ALIGNA_OPTIONS_CONTRACT,'aligna')]

    def test_exact_real_assets(self):
        for m,app in self.cases():
            result=g.validate(m,ROOT/'assets'/app)
            self.assertFalse(result['runtime_recording_attestation'])
            self.assertFalse(result['upload_authorized_by_cli'])
            self.assertEqual(m,g.load(ROOT/'data/screenshot_guides'/f"{m['guide_id']}.json"))

    def test_every_leaf_rejected_on_mutation(self):
        def paths(v,p=()):
            if isinstance(v,dict):
                for k,x in v.items(): yield from paths(x,p+(k,))
            elif isinstance(v,list):
                for k,x in enumerate(v): yield from paths(x,p+(k,))
            else: yield p,v
        for m,app in self.cases():
            for p,v in paths(m):
                altered=copy.deepcopy(m);target=altered
                for k in p[:-1]: target=target[k]
                target[p[-1]]=not v if isinstance(v,bool) else v+1 if isinstance(v,int) else v+' tampered'
                with self.subTest(guide=m['guide_id'],path=p),self.assertRaises(g.GuideError):
                    g.validate(altered,ROOT/'assets'/app)

    def test_extra_missing_fields_and_type_confusion(self):
        for m,app in self.cases():
            edits=[lambda x:x.update(extra=True),lambda x:x.pop('authorization'),lambda x:x.update(schema_version=True),lambda x:x['slides'][0].update(seconds=True),lambda x:x['metadata'].update(made_for_kids=0),lambda x:x['assets'].append(x['assets'][0])]
            for edit in edits:
                n=copy.deepcopy(m);edit(n)
                with self.assertRaises(g.GuideError):g.validate(n,ROOT/'assets'/app)

    def test_wrong_missing_and_symlink_assets(self):
        for m,app in self.cases():
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)
                with self.assertRaisesRegex(g.GuideError,'unsafe_asset_path'):g.validate(m,root)
                for a in m['assets']:(root/a['local_name']).write_bytes(b'wrong')
                with self.assertRaisesRegex(g.GuideError,'asset_integrity'):g.validate(m,root)
                first=root/m['assets'][0]['local_name'];first.unlink();first.symlink_to(ROOT/'assets'/app/m['assets'][0]['local_name'])
                with self.assertRaisesRegex(g.GuideError,'unsafe_asset_path'):g.validate(m,root)

    def test_existing_output_preserved(self):
        for m,app in self.cases():
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(g.GuideError,'output_exists'):g.render(m,ROOT/'assets'/app,Path(d))

    def test_geometry_change_before_encoder(self):
        from PIL import Image
        for m,app in self.cases():
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)
                for a in m['assets']:Image.new('RGB',(100,100)).save(root/a['local_name'])
                hashes={a['local_name']:a['sha256'] for a in m['assets']}
                with patch.object(g,'sha256',side_effect=lambda p:hashes[Path(p).name]),patch.object(g.subprocess,'run') as encoder:
                    with self.assertRaisesRegex(g.GuideError,'source_geometry_changed'):g.render(m,root,root/'output')
                    encoder.assert_not_called()

if __name__=='__main__':unittest.main()
