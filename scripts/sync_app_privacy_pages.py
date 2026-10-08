#!/usr/bin/env python3
"""Copy generated policy bytes without shadowing homepage-owned Astro routes."""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import json
import subprocess
import shutil
import sys

LOCALES = {'en': 'en', 'ko': 'ko', 'ja': 'ja', 'zh-hans': 'zh-Hans', 'zh-hant': 'zh-Hant', 'pt-br': 'pt-BR', 'de': 'de', 'fr': 'fr', 'es': 'es'}


class PrivacySyncError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyCopy:
    relative: Path
    action: str


def owned_policies(homepage: Path) -> set[str]:
    if not homepage.is_dir():
        raise PrivacySyncError('Homepage directory must exist')
    documents = homepage / 'src/content/privacy-policies'
    routes = homepage / 'src/pages/privacy/[app]'
    if routes.exists() and not documents.is_dir():
        raise PrivacySyncError('Astro privacy routes exist without their policy source directory')
    owners = {p.stem for p in documents.glob('*/*.json')} if documents.is_dir() else set()
    registry = homepage / 'src/lib/privacy-policy-documents.ts'
    if registry.exists():
        match = re.search(r'export const allPrivacyAppSlugs\s*=\s*\[([^\]]+)\]\s*as const', registry.read_text())
        if not match:
            raise PrivacySyncError('Cannot read the explicit Astro policy route-owner list')
        values = re.findall(r"['\"]([a-z0-9-]+)['\"]", match.group(1))
        remainder = re.sub(r"['\"][a-z0-9-]+['\"]|[\s,]", '', match.group(1))
        if remainder or not values or len(set(values)) != len(values):
            raise PrivacySyncError('Invalid explicit Astro policy route-owner list')
        owners.update(values)
    return owners


def assert_no_canonical_shadows(homepage: Path) -> None:
    for slug in owned_policies(homepage):
        root = homepage / 'public/privacy' / slug
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or not root.resolve().is_relative_to(homepage.resolve()):
            raise PrivacySyncError(f'Unsafe owned policy path: {slug}')
        if root.exists() and any(root.rglob('index.html')):
            raise PrivacySyncError(f'Astro-owned policy has a competing public canonical file: {slug}')


def policy_route(relative: Path) -> tuple[str, str, bool]:
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == 'privacy':
        slug, tail, canonical = parts[1], parts[2:], True
    elif len(parts) >= 4 and parts[0] == 'apps' and parts[2] == 'privacy':
        slug, tail, canonical = parts[1], parts[3:], False
    elif len(parts) >= 3 and parts[1] == 'privacy':
        slug, tail, canonical = parts[0], parts[2:], False
    else:
        raise PrivacySyncError(f'Unexpected generated policy path: {relative}')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise PrivacySyncError(f'Invalid policy slug: {slug}')
    if tail == ('index.html',):
        return slug, 'en', canonical
    if len(tail) == 2 and tail[1] == 'index.html' and tail[0] in LOCALES and tail[0] != 'en':
        return slug, LOCALES[tail[0]], canonical
    raise PrivacySyncError(f'Unexpected policy locale path: {relative}')


def sync_privacy_pages(source: Path, homepage: Path, *, dry_run: bool = False) -> list[PolicyCopy]:
    source, homepage = source.resolve(), homepage.resolve()
    if not source.is_dir() or not homepage.is_dir():
        raise PrivacySyncError('Generated source and homepage directories must exist')
    assert_no_canonical_shadows(homepage)
    owned = owned_policies(homepage)
    plan: list[PolicyCopy] = []
    # Validate every target before copying any file; source bytes are never rewritten.
    for path in sorted(source.rglob('index.html')):
        relative = path.relative_to(source)
        slug, language, canonical = policy_route(relative)
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise PrivacySyncError(f'Unsafe generated source: {relative}')
        if slug in owned:
            document = homepage / 'src/content/privacy-policies' / language / f'{slug}.json'
            uses_json = any((homepage / 'src/content/privacy-policies').glob(f'*/{slug}.json'))
            if uses_json and (not document.is_file() or document.is_symlink()):
                raise PrivacySyncError(f'Missing owned policy language source: {slug}/{language}')
            if canonical:
                plan.append(PolicyCopy(relative, 'skip-astro-owned'))
                continue
            destination = homepage / 'public' / relative
            if not destination.is_file() or destination.is_symlink() or not destination.resolve().is_relative_to(homepage):
                raise PrivacySyncError(f'Missing or unsafe homepage-owned compatibility alias: {relative}')
            # The migrated homepage owns its legal copy and branding as well.
            # Never replace those bytes with the legacy generator output.
            plan.append(PolicyCopy(relative, 'preserve-homepage-owned-alias'))
            continue
        destination = homepage / 'public' / relative
        if destination.is_symlink() or not destination.resolve().is_relative_to(homepage):
            raise PrivacySyncError(f'Unsafe policy destination: {relative}')
        action = 'create' if not destination.exists() else 'unchanged' if destination.read_bytes() == path.read_bytes() else 'overwrite'
        plan.append(PolicyCopy(relative, action))
    if not dry_run:
        for item in plan:
            if item.action in {'skip-astro-owned', 'preserve-homepage-owned-alias', 'unchanged'}:
                continue
            destination = homepage / 'public' / item.relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / item.relative, destination)
    return plan


def write_staging_manifest(path: Path, homepage: Path, plan: list[PolicyCopy]) -> None:
    if path.resolve().is_relative_to(homepage.resolve()):
        raise PrivacySyncError('Staging manifest must stay outside the homepage repository')
    changed = ['public/' + item.relative.as_posix() for item in plan if item.action in {'create', 'overwrite'}]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(changed) + '\n')


def stage_synced_paths(manifest: Path, homepage: Path) -> list[str]:
    values = json.loads(manifest.read_text())
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise PrivacySyncError('Invalid policy staging manifest')
    for value in values:
        relative = Path(value)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'public':
            raise PrivacySyncError('Unsafe policy staging path')
        policy_route(Path(*relative.parts[1:]))
        target = homepage / relative
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(homepage.resolve()):
            raise PrivacySyncError('Missing or unsafe policy staging file')
    assert_no_canonical_shadows(homepage)
    if values:
        subprocess.run(['git', 'add', '--', *values], cwd=homepage, check=True)
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path)
    parser.add_argument('--homepage-repo', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--check-ownership', action='store_true')
    parser.add_argument('--staging-manifest', type=Path)
    parser.add_argument('--stage-manifest', type=Path)
    args = parser.parse_args()
    try:
        if args.stage_manifest:
            stage_synced_paths(args.stage_manifest, args.homepage_repo.resolve())
            return 0
        if args.check_ownership:
            assert_no_canonical_shadows(args.homepage_repo.resolve())
            print('No static files shadow Astro-owned policy canonical routes')
            return 0
        if args.site_dir is None:
            parser.error('--site-dir is required unless --check-ownership is selected')
        plan = sync_privacy_pages(args.site_dir, args.homepage_repo, dry_run=args.dry_run)
        if args.staging_manifest and not args.dry_run:
            write_staging_manifest(args.staging_manifest, args.homepage_repo, plan)
        for item in plan:
            print(f'{item.action}: {item.relative}')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'privacy synchronization failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
