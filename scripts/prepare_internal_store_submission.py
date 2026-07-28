#!/usr/bin/env python3
"""Resolve one private-test artifact; never contact a store."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
from validate_app_releases import RELEASES_PATH,RELEASE_HEADER,app_index,read_csv,validate_release
ROOT=Path(__file__).resolve().parents[1]
def sha256_file(path: Path) -> str:
 return hashlib.sha256(path.read_bytes()).hexdigest()
def main() -> int:
 p=argparse.ArgumentParser();p.add_argument('release_id');p.add_argument('--github-output',type=Path);a=p.parse_args()
 releases=read_csv(RELEASES_PATH,RELEASE_HEADER); apps=app_index(); seen=set()
 for row in releases: validate_release(row,apps,seen)
 r=next((x for x in releases if x['release_id']==a.release_id),None)
 if not r or r['status']!='ready' or r['release_type']!='binary' or r['release_channel']!='private_test' or not r['artifact_path'] or not (ROOT/r['artifact_path']).is_file(): raise SystemExit('release must be a ready private_test binary with a verified local artifact')
 artifact=ROOT/r['artifact_path']
 if sha256_file(artifact)!=r['checksum_sha256']: raise SystemExit('private-test artifact checksum does not match release metadata')
 provider='google_play' if r['platform']=='android' else 'app_store' if r['platform']=='ios' else ''
 config=json.loads((ROOT/'data/internal_store_submission_config.json').read_text())
 app=config.get(provider,{}).get(r['app_slug'],{})
 required=('package_name',) if provider=='google_play' else ('bundle_id',)
 if not provider or any(not app.get(k) for k in required): raise SystemExit('internal store configuration is incomplete for this app')
 out=f"provider={provider}\nartifact={artifact}\nidentifier={app[required[0]]}\nchecksum_sha256={r['checksum_sha256']}\n"
 if a.github_output: a.github_output.write_text(a.github_output.read_text() + out if a.github_output.exists() else out)
 else: print(out,end='')
 return 0
if __name__=='__main__': raise SystemExit(main())
