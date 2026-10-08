"""Preserve the homepage-owned approved blog mark; never invent replacement icons."""
from pathlib import Path
import html
from xml.etree import ElementTree

MARKER = '<!-- ONNELLAB approved monogram -->'


class BlogBrandError(ValueError):
    pass


def approved_blog_mark(homepage: Path) -> str | None:
    root = homepage.resolve()
    source = root / 'public/brand/mark-charcoal.svg'
    if source.is_symlink() or not source.resolve().is_relative_to(root):
        raise BlogBrandError('Unsafe homepage-owned brand source')
    if not source.exists():
        return None
    try:
        svg = ElementTree.fromstring(source.read_text())
    except ElementTree.ParseError as error:
        raise BlogBrandError('Invalid approved blog brand SVG') from error
    paths = list(svg.iter('{http://www.w3.org/2000/svg}path'))
    if svg.attrib.get('viewBox') != '0 0 1254 1254' or len(paths) != 1 or not paths[0].attrib.get('d'):
        raise BlogBrandError('Unknown approved blog mark geometry contract')
    return paths[0].attrib['d']


def branded_blog_svg(svg: str, kind: str, mark: str) -> str:
    if MARKER in svg:
        if html.escape(mark, quote=True) not in svg and mark not in svg:
            raise BlogBrandError('Existing blog asset uses a different approved mark')
        return svg
    if kind == 'workflow':
        old, new, x, y, size = '<text x="92" y="588"', '<text x="148" y="588"', 85, 548, 64
        if old not in svg:
            old, new, x, y, size = '<text x="96" y="584"', '<text x="149" y="584"', 91, 548, 62
        if old not in svg:
            old, new, x, y, size = '<text x="78" y="586"', '<text x="128" y="586"', 76, 562, 42
    elif kind == 'social':
        old, new, x, y, size = '<text x="1048" y="552"', '<text x="1080" y="552"', 908, 512, 66
    else:
        raise BlogBrandError('Unsupported blog asset kind')
    if old not in svg:
        raise BlogBrandError('Unknown blog footer layout; editorial layout review required')
    # These positions mirror the approved homepage apply-blog-brand.mjs contract.
    logo = f'{MARKER}\n  <svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 1254 1254"><path fill="#282723" d="{html.escape(mark, quote=True)}"/></svg>\n  '
    return svg.replace(old, logo + new, 1)
