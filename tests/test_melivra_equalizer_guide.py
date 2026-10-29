import unittest, copy, importlib.util, json, pathlib, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('g',ROOT/'scripts/screenshot_guide.py'); g=importlib.util.module_from_spec(s); s.loader.exec_module(g)
class ContractTests(unittest.TestCase):
 def setUp(self): self.m=json.loads((ROOT/'data/screenshot_guides/melivra-equalizer-location-20261102.json').read_text())
 def test_valid_actual_asset(self): self.assertFalse(g.validate(self.m,ROOT/'assets')['runtime_recording_attestation'])
 def test_every_leaf_mutation_rejected(self):
  def walk(v,p=()):
   if isinstance(v,dict):
    for k,x in v.items(): yield from walk(x,p+(k,))
   elif isinstance(v,list):
    for k,x in enumerate(v): yield from walk(x,p+(k,))
   else: yield p,v
  for path,value in walk(self.m):
   with self.subTest(path=path):
    m=copy.deepcopy(self.m); dest=m
    for key in path[:-1]: dest=dest[key]
    dest[path[-1]]= not value if isinstance(value,bool) else value+1 if isinstance(value,int) else str(value)+' altered'
    with self.assertRaises(g.GuideError): g.validate(m,ROOT/'assets')
 def test_missing_asset(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(g.GuideError): g.validate(self.m,d)
 def test_changed_asset(self):
  with tempfile.TemporaryDirectory() as d:
   pathlib.Path(d,'05.png').write_bytes(b'changed')
   with self.assertRaises(g.GuideError): g.validate(self.m,d)
 def test_symlink_asset(self):
  with tempfile.TemporaryDirectory() as d:
   pathlib.Path(d,'05.png').symlink_to(ROOT/'assets/05.png')
   with self.assertRaises(g.GuideError): g.validate(self.m,d)
 def test_existing_output(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(g.GuideError): g.render(self.m,ROOT/'assets',d)
if __name__=='__main__': unittest.main()
