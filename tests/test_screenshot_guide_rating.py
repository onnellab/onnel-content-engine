import copy, json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import screenshot_guide as g
class RatingContractTest(unittest.TestCase):
    def test_exact_contract(self):
        m = json.loads((Path(__file__).resolve().parents[1] / 'data/screenshot_guides/melivra-player-rating-location-20261109.json').read_text())
        self.assertEqual(g.canonical(m), g.canonical(g.MELIVRA_RATING_CONTRACT))
    def test_every_leaf_rejected_when_changed(self):
        def paths(v, p=()):
            if isinstance(v, dict):
                for k,x in v.items(): yield from paths(x,p+(k,))
            elif isinstance(v,list):
                for k,x in enumerate(v): yield from paths(x,p+(k,))
            else: yield p
        for p in paths(g.MELIVRA_RATING_CONTRACT):
            m=copy.deepcopy(g.MELIVRA_RATING_CONTRACT); v=m
            for k in p[:-1]: v=v[k]
            v[p[-1]]=None
            with self.subTest(path=p), self.assertRaises(g.GuideError):g.validate(m, '.')
if __name__ == '__main__':unittest.main()
