#!/usr/bin/env python3
"""Generate and brand a 16:9 Aether Inn cover with Google Gemini image generation."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
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


def _font() -> Path:
    for path in FONT_CANDIDATES:
        if path.is_file():
            return path
    raise VideoError("aether_cover_serif_font_missing")


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


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def brand_background(background: Path, output: Path, title: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    title_file = output.parent / "cover-title.txt"
    brand_file = output.parent / "cover-brand.txt"
    title_text = _wrap_title(title)
    title_file.write_text(title_text, encoding="utf-8")
    brand_file.write_text("Aether Inn", encoding="utf-8")
    os.chmod(title_file, 0o600)
    os.chmod(brand_file, 0o600)
    line_count = title_text.count("\n") + 1
    brand_y = 94 + line_count * 82 + 28
    font = _filter_path(_font())
    title_path = _filter_path(title_file)
    brand_path = _filter_path(brand_file)
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
        f"drawtext=fontfile='{font}':textfile='{title_path}':fontcolor=0xC8AA6A:"
        "fontsize=72:line_spacing=8:x=112:y=86:shadowcolor=black@0.42:shadowx=2:shadowy=2,"
        f"drawbox=x=112:y={brand_y-15}:w=280:h=1:color=0xC8AA6A@0.72:t=fill,"
        f"drawtext=fontfile='{font}':textfile='{brand_path}':fontcolor=0xC8AA6A:"
        f"fontsize=29:x=112:y={brand_y}:shadowcolor=black@0.34:shadowx=1:shadowy=1,"
        f"drawbox=x=112:y={brand_y+48}:w=280:h=1:color=0xC8AA6A@0.72:t=fill"
    )
    run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(background),
        "-vf", vf, "-frames:v", "1", str(output),
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
