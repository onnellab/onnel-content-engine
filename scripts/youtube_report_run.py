#!/usr/bin/env python3
"""One-shot private YouTube reporting CLI. Standard output contains status only."""
import argparse
import json
from pathlib import Path
import re
import youtube_report_store as store
from short_video_pipeline import VideoError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['onnellab','aether_inn'], required=True)
    parser.add_argument('--root', type=Path, default=store.ROOT)
    parser.add_argument('command', choices=['sync','status','clear'])
    args=parser.parse_args()
    try:
        if args.command=='clear':
            store.clear(args.profile,args.root); report=None
        else: report=store.sync(args.profile,args.root) if args.command=='sync' else store.read(args.profile,args.root)
        entry=report['profiles'][args.profile] if report else {'state':'not_collected'}
        print(json.dumps({'profile':args.profile,'state':entry['state'],'warnings':entry.get('warnings',[]),'report_present':bool(report)},ensure_ascii=False))
        return 0
    except Exception as exc:
        reason=str(exc) if isinstance(exc,VideoError) and re.fullmatch(r'[a-z_]{1,90}',str(exc)) else 'private_reporting_failed'
        print(json.dumps({'profile':args.profile,'state':'blocked','error':reason}));return 2

if __name__=='__main__':raise SystemExit(main())
