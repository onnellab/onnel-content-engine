import unittest,copy,json,importlib.util,tempfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('guide',Path(__file__).parents[1]/'scripts/screenshot_guide.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
ROOT=Path(__file__).parents[1]
class CoverTest(unittest.TestCase):
 def test_exact(self):
  j=json.loads((ROOT/'data/screenshot_guides/papira-cover-styles-20261116.json').read_text());self.assertEqual(j,g.PAPIRA_COVER_CONTRACT);self.assertFalse(g.validate(j,ROOT/'assets')['upload_authorized_by_cli']);g.audit_copy_timing(j)
 def test_all_leaves_fail_closed(self):
  def leaves(x,p=()):
   if isinstance(x,dict):
    for k,v in x.items():yield from leaves(v,p+(k,))
   elif isinstance(x,list):
    for i,v in enumerate(x):yield from leaves(v,p+(i,))
   else:yield p
  for path in leaves(g.PAPIRA_COVER_CONTRACT):
   j=copy.deepcopy(g.PAPIRA_COVER_CONTRACT);x=j
   for k in path[:-1]:x=x[k]
   x[path[-1]]=None
   with self.subTest(path=path),self.assertRaises(g.GuideError):g.validate(j,ROOT/'assets')
 def test_invalid_bytes_and_missing(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(g.GuideError):g.validate(g.PAPIRA_COVER_CONTRACT,d)
   (Path(d)/'02.png').write_bytes(b'wrong')
   with self.assertRaises(g.GuideError):g.validate(g.PAPIRA_COVER_CONTRACT,d)
 def test_existing_output_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(g.GuideError):g.render(g.PAPIRA_COVER_CONTRACT,ROOT/'assets',d)
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'02.png').symlink_to((ROOT/'assets/02.png').resolve())
   with self.assertRaises(g.GuideError):g.validate(g.PAPIRA_COVER_CONTRACT,d)
if __name__=='__main__':unittest.main()
