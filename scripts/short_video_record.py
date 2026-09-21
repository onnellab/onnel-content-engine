#!/usr/bin/env python3
"""Create or reuse emulator/simulator recordings for short-video briefs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from short_video_recorder import (
    RecordingError,
    ensure_recording,
    load_scenarios,
    scenario_for_topic,
    status,
)


def _projects_root(value):
    if value:
        return Path(value)
    env = os.environ.get('ONNELLAB_PROJECTS_ROOT')
    if env:
        return Path(env)
    return Path.home() / 'Projects'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--projects-root', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('status')

    ensure = commands.add_parser('ensure')
    ensure.add_argument('scenario_id')
    ensure.add_argument(
        '--platform',
        choices=['android_emulator', 'ios_simulator'],
        default='android_emulator',
    )
    ensure.add_argument('--dry-run', action='store_true')
    ensure.add_argument('--android-serial')
    ensure.add_argument('--ios-udid')

    topic = commands.add_parser('ensure-topic')
    topic.add_argument('app_id')
    topic.add_argument('topic_id')
    topic.add_argument(
        '--platform',
        choices=['android_emulator', 'ios_simulator'],
        default='android_emulator',
    )
    topic.add_argument('--dry-run', action='store_true')
    topic.add_argument('--android-serial')
    topic.add_argument('--ios-udid')

    args = parser.parse_args()
    try:
        if args.command == 'list':
            scenarios = load_scenarios()
            result = [
                {
                    'scenario_id': row['scenario_id'],
                    'app_id': row['app_id'],
                    'platforms': row['platforms'],
                    'topics': row['topics'],
                }
                for row in scenarios.values()
            ]
        elif args.command == 'status':
            result = status(args.asset_root)
        else:
            scenario_id = args.scenario_id if args.command == 'ensure' else scenario_for_topic(
                args.app_id, args.topic_id, args.platform)['scenario_id']
            result = ensure_recording(
                scenario_id,
                projects_root=_projects_root(args.projects_root),
                asset_root=args.asset_root,
                platform=args.platform,
                dry_run=args.dry_run,
                android_serial=args.android_serial,
                ios_udid=args.ios_udid,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except RecordingError as exc:
        print(
            json.dumps(
                {'status': 'blocked', 'error': str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print(
            json.dumps(
                {'status': 'blocked', 'error': 'recording_interrupted'},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
