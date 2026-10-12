from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_blog_preview import validate_bundle, safe_destination, metadata

class BlogPreviewBoundaries(unittest.TestCase):
    def setUp(self):
        self.original=json.loads((ROOT/'preview/clipnest/candidate.json').read_text())

    def validate(self,bundle,corrupt=False):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'candidate.json';raw=json.dumps(bundle,ensure_ascii=False).encode();p.write_bytes(raw)
            p.with_suffix('.sha256').write_text(('0'*64 if corrupt else hashlib.sha256(raw).hexdigest())+'  candidate.json\n')
            return validate_bundle(p)

    def update_content(self,bundle,index,content):
        bundle['files'][index]['content']=content
        bundle['files'][index]['sha256']=hashlib.sha256(content.encode()).hexdigest()

    def test_exact_nine_locale_bundle(self):
        result,_=self.validate(self.original)
        self.assertEqual(len(result['files']),27)

    def test_root_checksum_is_required(self):
        with self.assertRaisesRegex(ValueError,'checksum'):self.validate(self.original,True)

    def test_only_exact_content_asset_paths(self):
        for invalid in ('../secret','.github/workflows/deploy.yml','generated/markdown/en/../../config.md'):
            b=copy.deepcopy(self.original);b['files'][0]['path']=invalid
            with self.subTest(path=invalid),self.assertRaises(ValueError):self.validate(b)

    def test_duplicate_and_missing_locale_fail(self):
        b=copy.deepcopy(self.original);b['locales'][0]='ko'
        with self.assertRaises(ValueError):self.validate(b)
        b=copy.deepcopy(self.original);b['files'][-1]=b['files'][0]
        with self.assertRaises(ValueError):self.validate(b)

    def test_source_tampering_fails(self):
        b=copy.deepcopy(self.original);b['files'][0]['content']+='tamper'
        with self.assertRaisesRegex(ValueError,'checksum'):self.validate(b)

    def test_fake_dates_and_identity_fail(self):
        for extra in ('published_at: "2026-10-18"\n','scheduled_at: "2026-10-18"\n','language: "xx"\n'):
            b=copy.deepcopy(self.original);self.update_content(b,0,b['files'][0]['content'].replace('---\n','---\n'+extra,1))
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.validate(b)

    def test_active_svg_fails(self):
        index=next(i for i,f in enumerate(self.original['files']) if f['path'].endswith('.svg'))
        for svg in ('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>','<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>','<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>'):
            b=copy.deepcopy(self.original);self.update_content(b,index,svg)
            with self.subTest(svg=svg),self.assertRaises(ValueError):self.validate(b)

    def test_markdown_cannot_inject_html_or_external_resources(self):
        for payload in ('<script>alert(1)</script>', '<iframe src="https://example.com"></iframe>', '![image](https://example.com/tracker.png)', '[link](javascript:alert)', '[external](https://example.com/)', '[reference]: https://example.com/image'):
            b=copy.deepcopy(self.original);self.update_content(b,0,b['files'][0]['content']+'\n'+payload+'\n')
            with self.subTest(payload=payload),self.assertRaises(ValueError):self.validate(b)

    def test_existing_file_and_symlink_parent_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory).resolve();(r/'existing.md').write_text('keep')
            with self.assertRaises(ValueError):safe_destination(r,'existing.md')
            (r/'linked').symlink_to(r,target_is_directory=True)
            with self.assertRaises(ValueError):safe_destination(r,'linked/new.md')
            with self.assertRaises(ValueError):safe_destination(r,'../escape.md')
            for name in ('preview-candidate.json','tests/blog-preview.spec.ts'):
                p=r/name;p.parent.mkdir(exist_ok=True);p.write_text('preserve')
                with self.assertRaises(ValueError):safe_destination(r,name)

    def test_workflow_cannot_publish(self):
        text=(ROOT/'.github/workflows/blog-preview.yml').read_text()
        for forbidden in ('pages: write','contents: write','id-token: write','secrets.','deploy-pages','git push','run_pipeline','publish_due','schedule_ready','generate_social_posts'):
            self.assertNotIn(forbidden,text)
        self.assertIn('contents: read',text)
        self.assertEqual(text.count('persist-credentials: false'),2)
        self.assertIn('retention-days: 1',text)

if __name__=='__main__':unittest.main()
