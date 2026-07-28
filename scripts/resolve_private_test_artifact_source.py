#!/usr/bin/env python3
"""Select the approved artifact transport for one private-test release."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from validate_app_releases import RELEASE_HEADER,RELEASES_PATH,read_csv
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 p=argparse.ArgumentParser();p.add_argument('release_id');p.add_argument('--github-output',type=Path,required=True);a=p.parse_args()
 r=next((x for x in read_csv(RELEASES_PATH,RELEASE_HEADER) if x['release_id']==a.release_id),None)
 if not r or r['release_channel']!='private_test': raise SystemExit('release must be private_test')
 if r['platform']=='ios': out='source=codemagic\n'
 elif r['platform']=='android':
  rows=json.loads((ROOT/'data/private_test_build_requests.json').read_text()).get('requests',[]); q=next((x for x in rows if x.get('release_id')==a.release_id and x.get('source')=='github_actions' and x.get('status')=='artifact_ready'),None)
  if not q: raise SystemExit('Android release requires a recorded GitHub Actions AAB')
  out=f"source=github_actions\ngithub_run_id={q['github_run_id']}\nartifact_name={q['artifact_name']}\nartifact_dir=generated/releases/{r['app_slug']}/{r['version']}/android\n"
 else: raise SystemExit('private-test artifact source is unsupported for this platform')
 a.github_output.write_text(out)
if __name__=='__main__': main()
