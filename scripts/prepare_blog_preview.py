"""Overlay reviewed blog content in a disposable homepage checkout; never publish."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

LOCALES = ('en', 'ko', 'ja', 'zh-Hans', 'zh-Hant', 'pt-BR', 'de', 'fr', 'es')
MAX_BUNDLE = 2_000_000

# Closed candidate profiles: incoming bundle metadata cannot grant new links.
def candidate_profile(slug):
    if slug == 'turn-repeated-text-into-reusable-snippets':
        return {
            'app_path': '/apps/clipnest/',
            'store_urls': ['https://apps.apple.com/us/app/clipnest-clipboard-tool/id6779928552'],
            'related_slugs': ['reuse-copied-text-snippets-iphone'],
            'table_rows': {locale: 3 for locale in LOCALES},
        }
    if slug == 'design-consistent-file-naming-system':
        return {
            'app_path': '/apps/aligna/',
            'store_urls': [
                'https://apps.apple.com/us/app/aligna-file-renamer/id6783642658',
                'https://play.google.com/store/apps/details?id=com.onnellab.aligna',
            ],
            'related_slugs': [
                'rename-files-safely-preview-workflow',
                'organize-downloads-small-folder-system',
            ],
            'table_rows': {locale: (5 if locale == 'en' else 6) for locale in LOCALES},
        }
    raise ValueError('Unknown preview candidate')

def allowed_candidate_links(slug, locale):
    if locale not in LOCALES:
        raise ValueError('Unknown preview locale')
    profile = candidate_profile(slug)
    return {
        f'/blog-assets/{locale}/{slug}/workflow-diagram.svg',
        profile['app_path'],
        *profile['store_urls'],
        *(f'https://onnellab.com/blog/{locale.lower()}/{related}/'
          for related in profile['related_slugs']),
    }

def sha(data):
    return hashlib.sha256(data).hexdigest()

def metadata(source):
    if not source.startswith('---\n') or '\n---\n' not in source[4:]:
        raise ValueError('Missing front matter')
    header, body = source[4:].split('\n---\n', 1)
    values = {}
    for line in header.splitlines():
        key, separator, value = line.partition(':')
        if not separator or key in values:
            raise ValueError('Invalid or duplicate metadata key')
        values[key] = json.loads(value.strip())
    return values, body

def validate_bundle(bundle_path):
    raw = bundle_path.read_bytes()
    if len(raw) > MAX_BUNDLE:
        raise ValueError('Bundle exceeds size limit')
    expected = bundle_path.with_suffix('.sha256').read_text().split()[0]
    if not re.fullmatch(r'[0-9a-f]{64}', expected) or sha(raw) != expected:
        raise ValueError('Bundle checksum mismatch')
    bundle = json.loads(raw)
    if bundle.get('schema') != 1 or bundle.get('state') != 'UNSCHEDULED_PREVIEW_ONLY':
        raise ValueError('Unknown preview schema/state')
    if bundle.get('locales') != list(LOCALES):
        raise ValueError('Exactly nine canonical locales required')
    slug = bundle.get('slug', '')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+){1,15}', slug):
        raise ValueError('Invalid slug')
    candidate_profile(slug)
    expected_paths = {f'generated/markdown/{locale}/productivity/{slug}.md' for locale in LOCALES}
    expected_paths |= {f'generated/assets/blog/{locale}/{slug}/{kind}.svg' for locale in LOCALES for kind in ('workflow-diagram', 'social-card')}
    files = bundle.get('files', [])
    if len(files) != 27 or {item.get('path') for item in files} != expected_paths:
        raise ValueError('Only nine exact Markdown and eighteen exact SVG paths allowed')
    for item in files:
        content = item.get('content')
        if not isinstance(content, str) or len(content.encode()) > 100_000 or sha(content.encode()) != item.get('sha256'):
            raise ValueError('Invalid source size/checksum')
        if item['path'].endswith('.md'):
            locale = item['path'].split('/')[2]
            if re.search(r'<\s*/?\s*[A-Za-z!]', content) or re.search(r'^\s*\[[^\]]+\]:', content, re.M):
                raise ValueError('HTML and reference-style resources are forbidden')
            allowed_image = f'/blog-assets/{locale}/{slug}/workflow-diagram.svg'
            if re.findall(r'!\[[^\]]*\]\(([^\s)]+)', content) != [allowed_image]:
                raise ValueError('Only the exact reviewed workflow image is allowed')
            allowed_links = allowed_candidate_links(slug, locale)
            if any(link not in allowed_links for link in re.findall(r'\]\(([^\s)]+)', content)):
                raise ValueError('Unexpected Markdown link/resource')
            values, body = metadata(content)
            if values.get('language') != locale or values.get('slug') != slug or values.get('status') != 'review':
                raise ValueError('Metadata identity/status mismatch')
            if values.get('canonical_url') != f'https://onnellab.com/blog/{locale.lower()}/{slug}/':
                raise ValueError('Canonical URL mismatch')
            if values.get('title') != values.get('card_title') or not body.lstrip().startswith('# ' + values['title'] + '\n'):
                raise ValueError('Title/H1 mismatch')
            if any(key in values for key in ('published_at', 'updated_at', 'scheduled_at')):
                raise ValueError('Preview must not fabricate publication dates')
        else:
            if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():
                raise ValueError('SVG declarations forbidden')
            root = ET.fromstring(content)
            for element in root.iter():
                if element.tag not in {'{http://www.w3.org/2000/svg}' + name for name in ('svg','g','path','rect','text','title','desc','tspan')}:
                    raise ValueError('Active or unknown SVG element')
                for key, value in element.attrib.items():
                    if key.lower().startswith('on') or 'href' in key.lower() or 'url(' in value.lower() or key == 'style':
                        raise ValueError('Active or external SVG attribute')
    return bundle, sha(raw)

def safe_destination(homepage, relative):
    destination = homepage / relative
    if destination.exists() or destination.is_symlink():
        raise ValueError(f'Preview collision: {relative}')
    for parent in destination.parents:
        if parent == homepage:
            break
        if parent.is_symlink():
            raise ValueError('Symlink destination forbidden')
    if not destination.resolve().is_relative_to(homepage):
        raise ValueError('Destination escapes checkout')
    return destination

def prepare(bundle_path, homepage, evidence):
    bundle, digest = validate_bundle(bundle_path)
    homepage = homepage.resolve()
    if not (homepage / '.git').exists() or not (homepage / 'astro.config.mjs').is_file():
        raise ValueError('Expected disposable Astro checkout')
    manifest_destination = safe_destination(homepage, 'preview-candidate.json')
    safe_destination(homepage, 'tests/blog-preview.spec.ts')
    # Reuse the canonical publisher's exact brand transformation. No deploy,
    # queue, privacy export, git-write or social-distribution entrypoint is used.
    from publishing import homepage_approved_blog_mark, branded_export_bytes
    mark = homepage_approved_blog_mark(homepage)
    if not mark:
        raise ValueError('Approved homepage mark is required')
    pending = {}
    for item in bundle['files']:
        source = item['path']
        if source.endswith('.md'):
            locale = source.split('/')[2]
            target = f'src/content/blog/{locale}/{bundle["slug"]}.md'
            content = item['content'].encode()
        else:
            target = 'public/blog-assets/' + source.removeprefix('generated/assets/blog/')
            content = branded_export_bytes(item['content'].encode(), 'workflow' if source.endswith('workflow-diagram.svg') else 'social', mark)
        pending[safe_destination(homepage, target)] = content
    for locale in LOCALES:
        safe_destination(homepage, f'public/blog-assets/{locale}/{bundle["slug"]}/social-card.png')
    for target, content in pending.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    for locale in LOCALES:
        assets = homepage / 'public/blog-assets' / locale / bundle['slug']
        # Exact existing exporter contract: branded workflow image is also the
        # homepage's 1200x675 social PNG. Source SVGs remain retained for audit.
        subprocess.run(['rsvg-convert','-w','1200','-h','675',str(assets/'workflow-diagram.svg'),'-o',str(assets/'social-card.png')], check=True)
    evidence.mkdir(parents=True, exist_ok=True)
    record = {'state':'NONPUBLISHING_PREVIEW','bundle_sha256':digest,'homepage_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=homepage,text=True).strip(),'content_engine_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],text=True).strip(),'slug':bundle['slug'],'locales':list(LOCALES),'publication_dates_added':False,'overlay_sha256':{str(p.relative_to(homepage)):sha(p.read_bytes()) for p in pending}}
    for locale in LOCALES:
        p=homepage/'public/blog-assets'/locale/bundle['slug']/'social-card.png'
        record['overlay_sha256'][str(p.relative_to(homepage))]=sha(p.read_bytes())
    (evidence/'provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    manifest_destination.write_text(json.dumps({'slug':bundle['slug'],'locales':list(LOCALES), 'store_urls':candidate_profile(bundle['slug'])['store_urls'], 'table_rows':candidate_profile(bundle['slug'])['table_rows']},indent=2)+'\n')
    return record

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--homepage',type=Path)
    parser.add_argument('--evidence',type=Path)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    if args.validate_only:
        print(validate_bundle(args.bundle)[1])
    else:
        if not args.homepage or not args.evidence:parser.error('--homepage and --evidence required')
        print(json.dumps(prepare(args.bundle,args.homepage,args.evidence),ensure_ascii=False))
