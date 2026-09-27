#!/usr/bin/env python3
"""Retitle an owner-approved Aether cover for compilation use."""
from __future__ import annotations

from pathlib import Path
import os
import shutil
from xml.sax.saxutils import escape as xml_escape

from aether_compose import media_info
from short_video_pipeline import VideoError, file_hash, run_process

TITLE_COLOR = "#F2E8D5"
BRAND_GOLD = "#C7AA6B"
PANEL = "#1B2C3C"


def wrap_title(title: str) -> list[str]:
    words = title.split()
    if not words or len(title) > 100:
        raise VideoError("aether_compilation_cover_title_invalid")
    options = []
    for cut in range(1, len(words)):
        lines = [" ".join(words[:cut]), " ".join(words[cut:])]
        lengths = [len(line) for line in lines]
        if max(lengths) <= 26:
            options.append((max(lengths) - min(lengths), max(lengths), lines))
    if options:
        return min(options, key=lambda row: row[:2])[2]
    if len(title) <= 26:
        return [title]
    raise VideoError("aether_compilation_cover_title_too_long")


def overlay_svg(title: str) -> str:
    lines = wrap_title(title)
    first_y = 125
    line_height = 82
    text = []
    for index, line in enumerate(lines):
        y = first_y + index * line_height
        value = xml_escape(line)
        text.append(f'<text x="78" y="{y}" class="title">{value}</text>')
    brand_y = first_y + len(lines) * line_height + 34
    sub_y = brand_y + 48
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
<style>
.title {{ font-family:Baskerville,Georgia,serif; font-size:76px; fill:{TITLE_COLOR}; }}
.brand {{ font-family:Baskerville,Georgia,serif; font-size:27px; letter-spacing:3px; fill:{BRAND_GOLD}; }}
.sub {{ font-family:Georgia,serif; font-size:17px; letter-spacing:5px; fill:{BRAND_GOLD}; }}
</style>
<rect x="30" y="28" width="930" height="350" rx="24" fill="{PANEL}" opacity="1"/>
<rect x="44" y="42" width="902" height="322" rx="18" fill="none" stroke="{BRAND_GOLD}" stroke-width="1" opacity=".55"/>
{''.join(text)}
<text x="78" y="{brand_y}" class="brand">Aether Inn</text>
<text x="78" y="{sub_y}" class="sub">30 MINUTE JOURNEY</text>
</svg>"""
def build(source: Path, output: Path, title: str) -> dict:
    source = Path(source)
    output = Path(output)
    if source.is_symlink() or not source.is_file():
        raise VideoError("aether_compilation_cover_source_invalid")
    info = media_info(source)
    image = next((row for row in info.get("streams", []) if row.get("codec_type") == "video"), {})
    width, height = int(image.get("width", 0)), int(image.get("height", 0))
    if width < 1280 or height < 720 or abs(width / max(1, height) - 16 / 9) > .02:
        raise VideoError("aether_landscape_cover_required")
    converter = shutil.which("rsvg-convert")
    if not converter:
        raise VideoError("aether_cover_svg_renderer_missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    svg = output.parent / "compilation-overlay.svg"
    overlay = output.parent / "compilation-overlay.png"
    svg.write_text(overlay_svg(title), encoding="utf-8")
    os.chmod(svg, 0o600)
    run_process([converter, "-w", "1920", "-h", "1080", "-o", str(overlay), str(svg)], timeout=60)
    partial = output.with_suffix(".partial.png")
    partial.unlink(missing_ok=True)
    run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-y",
        "-i", str(source), "-i", str(overlay),
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];[bg][1:v]overlay=0:0",
        "-frames:v", "1", str(partial),
    ], timeout=120)
    partial.replace(output)
    os.chmod(output, 0o600)
    return {
        "path": str(output),
        "sha256": file_hash(output),
        "title": title,
        "base_sha256": file_hash(source),
        "layout": "opaque_aether_compilation_card_v1",
    }
