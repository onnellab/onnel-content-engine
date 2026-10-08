import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('guide',ROOT/'scripts/screenshot_guide.py')
guide=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)

class ScreenshotGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.m=guide.load(ROOT/'data/screenshot_guides/quivra-file-list-20261009.json')
        self.hashes={}
        for name in ('01.png','02.png'):
            data=('offline test asset '+name).encode()
            (self.root/name).write_bytes(data)
            self.hashes[name]=hashlib.sha256(data).hexdigest()
        for asset in self.m['assets']:
            asset['sha256']=self.hashes[asset['local_name']]
        self.patch=patch.object(guide,'APPROVED_ASSETS',self.hashes)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_valid_is_not_recording_or_upload_authorization(self):
        result=guide.validate(self.m,self.root)
        self.assertFalse(result['runtime_recording_attestation'])
        self.assertFalse(result['upload_authorized_by_cli'])

    def reject(self,field,value,error):
        m=copy.deepcopy(self.m)
        target=m
        for key in field[:-1]: target=target[key]
        target[field[-1]]=value
        with self.assertRaisesRegex(guide.GuideError,error): guide.validate(m,self.root)

    def test_wrong_channel(self): self.reject(['channel_id'],'UCNRRsPiv6KDJmcFtDbZvq2w','guide_scope')
    def test_wrong_app(self): self.reject(['app_id'],'APP-0002','guide_scope')
    def test_other_language(self): self.reject(['locale'],'ko','guide_scope')
    def test_source_changed(self): self.reject(['source','commit'],'0'*40,'unapproved_source')
    def test_false_conversion_proof(self): self.reject(['source','runtime_conversion_verified'],True,'not_a_runtime')
    def test_asset03_forbidden(self): self.reject(['assets',0,'local_name'],'03.png','asset_not_allowlisted')
    def test_traversal(self): self.reject(['assets',0,'local_name'],'../01.png','asset_not_allowlisted')
    def test_source_path_changed(self): self.reject(['assets',0,'source_path'],'assets/other.png','source_path')
    def test_corrupt_bytes(self):
        (self.root/'01.png').write_bytes(b'changed')
        with self.assertRaisesRegex(guide.GuideError,'asset_integrity'): guide.validate(self.m,self.root)
    def test_symlink(self):
        (self.root/'01.png').unlink()
        (self.root/'01.png').symlink_to(self.root/'02.png')
        with self.assertRaisesRegex(guide.GuideError,'unsafe_asset_path'): guide.validate(self.m,self.root)
    def test_duplicate_asset(self): self.reject(['assets',1],self.m['assets'][0],'asset_not_allowlisted')
    def test_no_disclosure(self): self.reject(['metadata','format_disclosure'],'','disclosure_required')
    def test_audio_forbidden(self): self.reject(['metadata','audio'],'music','disclosure_required')
    def test_unreviewed_copy(self): self.reject(['slides',0,'heading'],'Watch it convert instantly','copy_requires_review')
    def test_unreviewed_duration(self): self.reject(['slides',0,'seconds'],30,'copy_requires_review')
    def test_no_rights(self): self.reject(['authorization','rights_basis'],'unknown','authorization_missing')
    def test_description_disclosure_required(self): self.reject(['metadata','description'],'To prepare files in Quivra, enjoy.','description_disclosure')
    def test_unapproved_link(self): self.reject(['metadata','description'],self.m['metadata']['description'].replace('6759565093','1111111111'),'unapproved_links')
    def test_hype(self): self.reject(['metadata','description'],self.m['metadata']['description']+' Guaranteed results.','unsupported_claim')
    def test_unknown_schema_field(self):
        self.m['recording']='pretend.mp4'
        with self.assertRaisesRegex(guide.GuideError,'manifest_schema'): guide.validate(self.m,self.root)
    def test_duplicate_json_keys(self):
        p=self.root/'bad.json'; p.write_text('{"x":1,"x":2}')
        with self.assertRaisesRegex(guide.GuideError,'duplicate_json_key'): guide.load(p)
    def test_nan(self):
        p=self.root/'bad.json'; p.write_text('{"x":NaN}')
        with self.assertRaisesRegex(guide.GuideError,'nonfinite_json'): guide.load(p)
    def test_existing_output_preserved(self):
        with self.assertRaisesRegex(guide.GuideError,'output_exists'): guide.render(self.m,self.root,self.root)

if __name__=='__main__': unittest.main()
