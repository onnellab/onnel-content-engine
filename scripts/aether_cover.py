#!/usr/bin/env python3
"""Generate and brand a 16:9 Aether Inn cover with Google Gemini image generation."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from xml.sax.saxutils import escape as xml_escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aether_compose import media_info
from lyria_config import access_token, load_settings
from short_video_credentials import CredentialError
from short_video_pipeline import VideoError, file_hash, run_process

MODEL = "gemini-2.5-flash-image"
LOCATION = "global"
MAX_RESPONSE = 32 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
LANES = ROOT / "data" / "aether_single_lanes.json"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/NewYork.ttf"),
    Path("/System/Library/Fonts/Supplemental/Georgia.ttf"),
    Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
)


def lane_direction(lane: str) -> str:
    data = json.loads(LANES.read_text(encoding="utf-8"))
    for row in data.get("lanes", []):
        if row.get("id") == lane:
            return str(row.get("direction", "")).strip()
    raise VideoError("aether_single_lane_invalid")


def cover_prompt(title: str, style: str, lane: str) -> str:
    direction = lane_direction(lane)
    return (
        "Create one landscape background illustration for Aether Inn, a nostalgic fantasy JRPG/MMORPG "
        "soundtrack archive. 16:9 composition, environment-first, wide scenic view, painterly fantasy game "
        "background, warm natural color palette, dreamy atmospheric light, rich depth, inviting sense of travel. "
        f"Song concept: {title}. Music direction: {style}. Scene direction: {direction}. "
        "Keep the upper-left area visually calm with usable negative space for later title typography. "
        "Do not render any letters, words, logo, UI, watermark, border, frame, subtitle, black title cloud, "
        "metallic game-logo effect, modern city, combat, weapons, battle scene, or action pose. "
        "The scenery is the protagonist. Elegant, comfortable, nostalgic, adventurous, and believable as a "
        "classic fantasy RPG location."
    )


def _request(project: str, prompt: str, token: str, *, send=None, timeout: int = 180) -> tuple[bytes, str]:
    endpoint = (
        "https://aiplatform.googleapis.com/v1/projects/"
        f"{project}/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"
    )
    body = json.dumps({
        "contents": {"role": "USER", "parts": [{"text": prompt}]},
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "16:9"},
            "candidateCount": 1,
        },
    }).encode("utf-8")
    if send is None:
        def send(req):
            return urlopen(req, timeout=timeout)
    req = Request(endpoint, data=body, method="POST", headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=utf-8",
        "X-Goog-User-Project": project,
    })
    try:
        with send(req) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise CredentialError("aether_cover_auth_or_permission_denied") from None
        if exc.code == 429:
            raise CredentialError("aether_cover_rate_limited") from None
        raise CredentialError("aether_cover_provider_rejected") from None
    except (URLError, OSError, TimeoutError):
        raise CredentialError("aether_cover_network_error") from None
    if len(raw) > MAX_RESPONSE:
        raise CredentialError("aether_cover_response_too_large")
    try:
        data = json.loads(raw)
        candidates = data.get("candidates") or []
        parts = candidates[0]["content"]["parts"] if candidates else []
        images = [p.get("inlineData") for p in parts if isinstance(p, dict) and isinstance(p.get("inlineData"), dict)]
        if len(images) != 1:
            raise ValueError()
        mime = images[0].get("mimeType")
        encoded = images[0].get("data")
        if mime not in {"image/png", "image/jpeg", "image/webp"} or not isinstance(encoded, str):
            raise ValueError()
        image = base64.b64decode(encoded, validate=True)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise CredentialError("aether_cover_response_invalid") from None
    if not 1024 <= len(image) <= 24 * 1024 * 1024:
        raise CredentialError("aether_cover_image_invalid")
    return image, mime


def _wrap_title(title: str) -> str:
    words = title.split()
    if not words or len(title) > 100:
        raise VideoError("aether_title_invalid")
    lines, current = [], []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > 27:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    if len(lines) > 3:
        raise VideoError("aether_title_too_long_for_cover")
    return "\n".join(lines)


def _title_svg(title: str) -> str:
    lines = _wrap_title(title).splitlines()
    shadow = []
    gold = []
    for index, line in enumerate(lines):
        y = 142 + index * 82
        value = xml_escape(line)
        shadow.append(f'<text x="114" y="{y+2}" class="title shadow">{value}</text>')
        gold.append(f'<text x="112" y="{y}" class="title">{value}</text>')
    brand_y = 142 + len(lines) * 82 + 18
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<style>
.title {{ font-family: Georgia, "Times New Roman", serif; font-size:72px; font-weight:600; fill:#C8AA6A; }}
.shadow {{ fill:#000; opacity:.38; }}
.brand {{ font-family: Georgia, "Times New Roman", serif; font-size:29px; letter-spacing:1.5px; fill:#C8AA6A; }}
.line {{ stroke:#C8AA6A; stroke-width:1; opacity:.75; }}
</style>
{''.join(shadow)}
{''.join(gold)}
<line x1="112" y1="{brand_y-18}" x2="392" y2="{brand_y-18}" class="line"/>
<text x="112" y="{brand_y+22}" class="brand">Aether Inn</text>
<line x1="112" y1="{brand_y+48}" x2="392" y2="{brand_y+48}" class="line"/>
</svg>"""


def brand_background(background: Path, output: Path, title: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    converter = shutil.which("rsvg-convert")
    if not converter:
        raise VideoError("aether_cover_svg_renderer_missing")
    svg = output.parent / "cover-overlay.svg"
    overlay = output.parent / "cover-overlay.png"
    svg.write_text(_title_svg(title), encoding="utf-8")
    os.chmod(svg, 0o600)
    run_process([converter, "-w", "1920", "-h", "1080", "-o", str(overlay), str(svg)], timeout=60)
    run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(background), "-i", str(overlay),
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];[bg][1:v]overlay=0:0",
        "-frames:v", "1", str(output),
    ], timeout=120)
    info = media_info(output)
    image = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    if (image.get("width"), image.get("height")) != (1920, 1080) or not output.is_file():
        raise VideoError("aether_cover_branding_failed")
    return {
        "path": str(output),
        "sha256": file_hash(output),
        "width": 1920,
        "height": 1080,
        "layout": "upper_left_matte_gold_serif",
    }


def generate_cover(title: str, style: str, lane: str, output_dir: Path, *, execute=False, send=None, token=None) -> dict:
    settings = load_settings()
    if not settings:
        raise CredentialError("lyria_not_configured")
    plan = {
        "model": MODEL,
        "location": LOCATION,
        "project_id": settings["project_id"],
        "lane": lane,
        "prompt_sha256": hashlib.sha256(cover_prompt(title, style, lane).encode()).hexdigest(),
        "generation_count": 1,
    }
    if not execute:
        return {**plan, "state": "planned"}
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    image, mime = _request(settings["project_id"], cover_prompt(title, style, lane), token or access_token(), send=send)
    ext = { "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp" }[mime]
    background = output_dir / ("background" + ext)
    fd = os.open(background, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(image)
    result = brand_background(background, output_dir / "cover.png", title)
    return {**plan, "state": "generated", "background_sha256": file_hash(background), **result}
