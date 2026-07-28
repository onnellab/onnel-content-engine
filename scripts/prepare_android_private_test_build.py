#!/usr/bin/env python3
"""Resolve one merged Android task into an immutable private-test Git tag."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from dispatch_codemagic_private_test_build import create_immutable_tag
from validate_app_releases import RELEASE_HEADER, RELEASES_PATH, read_csv
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('task_id'); p.add_argument('--release-id',required=True); p.add_argument('--github-output',type=Path,required=True); a=p.parse_args()
 release=next((x for x in read_csv(RELEASES_PATH,RELEASE_HEADER) if x['release_id']==a.release_id),None)
 tasks=json.loads((ROOT/'data/ai_coder_tasks.json').read_text()).get('tasks',[]); task=next((x for x in tasks if x.get('task_id')==a.task_id),None)
 if not release or release['platform']!='android' or release['release_type']!='binary' or release['release_channel']!='private_test' or release['status']!='planned': raise SystemExit('release must be a planned Android private_test binary')
 if not task or task.get('status')!='merged' or task.get('app_slug')!=release['app_slug'] or task.get('repository')!=release['repository'] or not re.fullmatch(r'[0-9a-f]{40}',task.get('merge_commit','')): raise SystemExit('merged Coder task must match the Android release and include a merge SHA')
 tag=create_immutable_tag(release['repository'],a.release_id,task['merge_commit'])
 artifact_dir=f"generated/releases/{release['app_slug']}/{release['version']}/android"
 a.github_output.write_text(f"repository={release['repository']}\ntag={tag}\nartifact_name=android-aab-{a.release_id}\nartifact_dir={artifact_dir}\n",encoding='utf-8')
 return 0
if __name__=='__main__': raise SystemExit(main())
