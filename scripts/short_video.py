#!/usr/bin/env python3
"""Validate, durably queue, inspect and render local educational short videos."""
import argparse
import json
from pathlib import Path
import sys
from short_video_pipeline import Queue, ROOT, VideoError, load_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, default=ROOT / '.runtime/short-video')
    parser.add_argument('--browser', help='Installed headless Chromium executable; no download at runtime')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ['validate', 'enqueue']:
        commands.add_parser(command).add_argument('brief', type=Path)
    commands.add_parser('list')
    commands.add_parser('status').add_argument('job_id')
    commands.add_parser('render').add_argument('job_id')
    worker = commands.add_parser('worker')
    worker.add_argument('--once', required=True, action='store_true')
    worker.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        queue = Queue(args.state_root, args.asset_root, browser=args.browser)
        if args.command in {'validate', 'enqueue'}:
            brief = load_json(args.brief)
            result = queue.enqueue(brief) if args.command == 'enqueue' else {'valid': True, 'assets': queue.validate(brief)}
        elif args.command == 'worker':
            result = queue.worker(dry_run=args.dry_run)
        elif args.command == 'render':
            result = queue.render(args.job_id)
        else:
            result = queue.status(args.job_id if args.command == 'status' else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (VideoError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
