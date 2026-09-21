#!/usr/bin/env python3
"""Private local short-video queue, explicit YouTube approval and resumable uploads."""
import argparse
import json
from pathlib import Path
import sys
from short_video_pipeline import Queue, ROOT, VideoError, load_json
from short_video_runtime import INBOX, enqueue_dir, graceful_signals, readiness, worker
from short_video_youtube import Uploader, YouTube, check_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, default=ROOT / '.runtime/short-video')
    parser.add_argument('--browser', help='Installed headless Chromium executable')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ['validate', 'enqueue']:
        p = commands.add_parser(command)
        p.add_argument('brief', type=Path)
        p.add_argument('--dry-run', action='store_true')
    commands.add_parser('list')
    commands.add_parser('readiness')
    commands.add_parser('status').add_argument('job_id')
    p = commands.add_parser('render')
    p.add_argument('job_id')
    p.add_argument('--dry-run', action='store_true')
    for command in ['upload', 'reconcile', 'approve']:
        p = commands.add_parser(command)
        p.add_argument('job_id')
        p.add_argument('--execute', action='store_true')
        p.add_argument('--dry-run', action='store_true')
        if command == 'approve':
            p.add_argument('--made-for-kids', choices=['true', 'false'], required=True)
            p.add_argument('--synthetic-media', choices=['true', 'false'], required=True)
            p.add_argument('--privacy', choices=['private', 'unlisted', 'public'], default='private')
            p.add_argument('--publish-at', help='UTC YYYY-MM-DDTHH:MM:SSZ')
            p.add_argument('--approve-publish', action='store_true')
    p = commands.add_parser('youtube-check')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p = commands.add_parser('enqueue-dir')
    p.add_argument('directory', type=Path, nargs='?', default=INBOX)
    p.add_argument('--dry-run', action='store_true')
    p = commands.add_parser('worker')
    p.add_argument('--once', required=True, action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--upload', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--inbox', type=Path, nargs='?', const=INBOX)
    args = parser.parse_args()
    try:
        queue = Queue(args.state_root, args.asset_root, browser=args.browser)
        execute = getattr(args, 'execute', False) and not getattr(args, 'dry_run', False)
        with graceful_signals():
            if args.command in {'validate', 'enqueue'}:
                brief = load_json(args.brief)
                result = queue.enqueue(brief) if args.command == 'enqueue' and not args.dry_run else {'valid': True, 'assets': queue.validate(brief)}
            elif args.command == 'worker':
                result = worker(queue, upload=args.upload, execute=execute, dry_run=args.dry_run, inbox=args.inbox)
            elif args.command == 'render':
                result = {'dry_run': True, 'job_id': args.job_id} if args.dry_run else queue.render(args.job_id)
            elif args.command == 'enqueue-dir':
                result = enqueue_dir(queue, args.directory, dry_run=args.dry_run)
            elif args.command == 'readiness':
                result = readiness(queue)
            elif args.command == 'youtube-check':
                result = YouTube().verify() if execute else check_config()
            elif args.command == 'approve':
                result = Uploader(queue).approve(args.job_id, {
                    'made_for_kids': args.made_for_kids == 'true', 'synthetic_media': args.synthetic_media == 'true',
                    'privacy': args.privacy, 'publish_at': args.publish_at, 'publish_approved': args.approve_publish}, execute=execute)
            elif args.command in {'upload', 'reconcile'}:
                result = Uploader(queue).run(args.job_id, execute=execute, reconcile=args.command == 'reconcile')
            else:
                result = queue.status(args.job_id if args.command == 'status' else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if isinstance(result, dict) and result.get('status') in {'blocked', 'failed', 'reconcile_required', 'rejected'} else 0
    except KeyboardInterrupt:
        print(json.dumps({'status': 'blocked', 'error': 'interrupted_retry_or_reconcile'}), file=sys.stderr)
        return 130
    except VideoError as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({'status': 'blocked', 'error': 'local_operation_failed'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
