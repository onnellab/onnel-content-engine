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
import statistics
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
        "Create one full-bleed 16:9 fantasy landscape illustration for Aether Inn, a nostalgic JRPG/MMORPG "
        "soundtrack archive. The environment must fill the entire frame edge-to-edge with visible scenic detail "
        "at the top and bottom edges. No black bands, no letterboxing, no cinematic frame, no border, no empty "
        "black sky or black sea strip, and no heavy vignette that becomes a dark bar. Environment-first, wide "
        "scenic view, painterly fantasy game background, warm natural color palette, dreamy atmospheric light, "
        "rich depth, and an inviting sense of travel. "
        f"Song concept: {title}. Music direction: {style}. Scene direction: {direction}. "
        "Keep the upper-left area visually calm through composition, sky, mist, or lighting so later title "
        "typography remains readable; never create a blank, black, smoky, or boxed title panel. "
        "Do not render any letters, words, logo, UI, watermark, subtitle, metallic game-logo effect, modern city, "
        "combat, weapons, battle scene, or action pose. Even for night or underwater scenes, preserve color, "
        "texture, and environmental information all the way to every edge. The scenery is the protagonist. "
        "Elegant, comfortable, nostalgic, adventurous, and believable as a classic fantasy RPG location."
    )


def _request(project: str, prompt: str, token: str, *, send=None, timeout: int = 180) -> tuple[bytes, str]:
    endpoint = (
        "https://aiplatform.googleapis.com/v1/projects/"
        f"{project}/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"
    )
    body = json.dumps({
        "contents": {"role": "USER", "parts": [{"text": prompt}]},
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
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
        if current and len(candidate) > 26:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    if len(lines) > 3:
        raise VideoError("aether_title_too_long_for_cover")
    return "\n".join(lines)


TITLE_COLOR = "#F2E8D5"
BRAND_GOLD = "#C7AA6B"
TITLE_FONT_SIZE = 72
TITLE_LINE_HEIGHT = 80
TITLE_REGION_WIDTH = 720
TITLE_CANDIDATES = (
    (132, 150, 0),
    (132, 360, 0),
    (1050, 150, 0),
    (1050, 360, 0),
    (600, 150, 0),
    (132, 600, 1),
    (600, 600, 1),
    (1050, 600, 1),
)


def _sample_text_region(path: Path, x: int, first_y: int, line_count: int) -> dict:
    top = max(0, first_y - TITLE_FONT_SIZE)
    height = min(430, line_count * TITLE_LINE_HEIGHT + 118)
    raw = run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
        "-vf",
        (
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
            f"crop={TITLE_REGION_WIDTH}:{height}:{x}:{top},scale=48:16,format=rgb24"
        ),
        "-frames:v", "1", "-f", "rawvideo", "-"
    ], timeout=60)
    if len(raw) != 48 * 16 * 3:
        raise VideoError("aether_cover_text_region_probe_failed")
    lumas = []
    warm_bright = 0
    low_contrast = 0
    title_luma = 0.2126 * 242 + 0.7152 * 232 + 0.0722 * 213
    for index in range(0, len(raw), 3):
        red, green, blue = raw[index:index + 3]
        luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        lumas.append(luma)
        if red >= 150 and green >= 105 and blue + 28 < min(red, green):
            warm_bright += 1
        if abs(title_luma - luma) < 58:
            low_contrast += 1
    count = len(lumas)
    mean = statistics.fmean(lumas)
    std = statistics.pstdev(lumas)
    bright_fraction = sum(value >= 180 for value in lumas) / count
    warm_fraction = warm_bright / count
    low_contrast_fraction = low_contrast / count
    mean_contrast = statistics.fmean(abs(title_luma - value) for value in lumas)
    score = (
        mean_contrast
        - std * .22
        - bright_fraction * 34
        - warm_fraction * 18
        - low_contrast_fraction * 46
    )
    return {
        "mean_luma": round(mean, 2),
        "std_luma": round(std, 2),
        "bright_fraction": round(bright_fraction, 4),
        "warm_fraction": round(warm_fraction, 4),
        "low_contrast_fraction": round(low_contrast_fraction, 4),
        "mean_contrast": round(mean_contrast, 2),
        "score": round(score, 3),
    }


def choose_title_layout(background: Path, title: str) -> dict:
    line_count = len(_wrap_title(title).splitlines())
    choices = []
    for order, (x, first_y, tier) in enumerate(TITLE_CANDIDATES):
        stats = _sample_text_region(background, x, first_y, line_count)
        choices.append({"x": x, "first_y": first_y, "tier": tier, "order": order, **stats})
    preferred = [row for row in choices if row["tier"] == 0 and row["score"] >= 45]
    pool = preferred or choices
    selected = max(pool, key=lambda row: (row["score"] - row["tier"] * 12, -row["order"]))
    shadow_opacity = .34
    if selected["bright_fraction"] >= .30 or selected["low_contrast_fraction"] >= .28:
        shadow_opacity = .42
    elif selected["bright_fraction"] >= .16 or selected["low_contrast_fraction"] >= .16:
        shadow_opacity = .38
    return {
        "x": selected["x"],
        "first_y": selected["first_y"],
        "shadow_opacity": shadow_opacity,
        "selected_metrics": selected,
        "candidate_metrics": choices,
    }


def _title_svg(title: str, layout: dict | None = None) -> str:
    lines = _wrap_title(title).splitlines()
    layout = layout or {"x": 132, "first_y": 150, "shadow_opacity": .34}
    x = int(layout["x"])
    first_y = int(layout["first_y"])
    shadow_opacity = float(layout["shadow_opacity"])
    shadow = []
    ivory = []
    for index, line in enumerate(lines):
        y = first_y + index * TITLE_LINE_HEIGHT
        value = xml_escape(line)
        shadow.append(f'<text x="{x+2}" y="{y+2}" class="title shadow">{value}</text>')
        ivory.append(f'<text x="{x}" y="{y}" class="title">{value}</text>')
    brand_y = first_y + len(lines) * TITLE_LINE_HEIGHT + 25
    ornament_y = brand_y + 35
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<style>
.title {{ font-family: Baskerville, Georgia, serif; font-size:{TITLE_FONT_SIZE}px; font-weight:400; letter-spacing:.35px; fill:{TITLE_COLOR}; }}
.shadow {{ fill:#211A17; opacity:{shadow_opacity:.2f}; }}
.brand {{ font-family: Baskerville, Georgia, serif; font-size:24px; font-weight:400; letter-spacing:3.2px; fill:{BRAND_GOLD}; }}
.ornament {{ stroke:{BRAND_GOLD}; stroke-width:1; opacity:.78; fill:none; }}
.diamond {{ fill:{BRAND_GOLD}; opacity:.86; }}
</style>
{''.join(shadow)}
{''.join(ivory)}
<text x="{x}" y="{brand_y}" class="brand">Aether Inn</text>
<line x1="{x}" y1="{ornament_y}" x2="{x+86}" y2="{ornament_y}" class="ornament"/>
<path d="M {x+98} {ornament_y-4} L {x+102} {ornament_y} L {x+98} {ornament_y+4} L {x+94} {ornament_y} Z" class="diamond"/>
<line x1="{x+110}" y1="{ornament_y}" x2="{x+196}" y2="{ornament_y}" class="ornament"/>
</svg>"""


def _luma_strip(path: Path, y: int, height: int) -> dict:
    raw = run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
        "-vf", f"crop=iw:{height}:0:{y},scale=64:8,format=gray",
        "-frames:v", "1", "-f", "rawvideo", "-"
    ], timeout=60)
    values = list(raw)
    if len(values) != 512:
        raise VideoError("aether_cover_luma_probe_failed")
    return {
        "mean": statistics.fmean(values),
        "std": statistics.pstdev(values),
        "dark_fraction": sum(value < 24 for value in values) / len(values),
    }


def validate_full_bleed_background(path: Path) -> dict:
    path = Path(path)
    info = media_info(path)
    image = next((row for row in info.get("streams", []) if row.get("codec_type") == "video"), {})
    width, height = int(image.get("width", 0)), int(image.get("height", 0))
    if width < 1024 or height < 576:
        raise VideoError("aether_cover_background_too_small")
    edge_h = max(24, round(height * .06))
    center_h = max(48, round(height * .20))
    top = _luma_strip(path, 0, edge_h)
    bottom = _luma_strip(path, height - edge_h, edge_h)
    center = _luma_strip(path, (height - center_h) // 2, center_h)
    def band(stats):
        return (
            stats["mean"] < 42
            and stats["dark_fraction"] >= .80
            and center["mean"] - stats["mean"] >= 45
        )
    if band(top) or band(bottom):
        raise VideoError("aether_cover_letterbox_detected")
    return {"top": top, "bottom": bottom, "center": center}


def brand_background(background: Path, output: Path, title: str) -> dict:
    validate_full_bleed_background(background)
    layout = choose_title_layout(background, title)
    output.parent.mkdir(parents=True, exist_ok=True)
    converter = shutil.which("rsvg-convert")
    if not converter:
        raise VideoError("aether_cover_svg_renderer_missing")
    svg = output.parent / "cover-overlay.svg"
    overlay = output.parent / "cover-overlay.png"
    svg.write_text(_title_svg(title, layout), encoding="utf-8")
    os.chmod(svg, 0o600)
    run_process([converter, "-w", "1920", "-h", "1080", "-o", str(overlay), str(svg)], timeout=60)
    run_process([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(background), "-i", str(overlay),
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];[bg][1:v]overlay=0:0",
        "-frames:v", "1", str(output),
    ], timeout=120)
    info = media_info(output)
    image = next((row for row in info.get("streams", []) if row.get("codec_type") == "video"), {})
    if (image.get("width"), image.get("height")) != (1920, 1080) or not output.is_file():
        raise VideoError("aether_cover_branding_failed")
    return {
        "path": str(output),
        "sha256": file_hash(output),
        "width": 1920,
        "height": 1080,
        "layout": "adaptive_contrast_ivory_baskerville",
        "title_layout": layout,
    }


def generate_cover(title: str, style: str, lane: str, output_dir: Path, *, execute=False, send=None, token=None) -> dict:
    settings = load_settings()
    if not settings:
        raise CredentialError("lyria_not_configured")
    base_prompt = cover_prompt(title, style, lane)
    plan = {
        "model": MODEL,
        "location": LOCATION,
        "project_id": settings["project_id"],
        "lane": lane,
        "prompt_sha256": hashlib.sha256(base_prompt.encode()).hexdigest(),
        "max_generation_attempts": 3,
    }
    if not execute:
        return {**plan, "state": "planned", "generation_count": 0}
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    existing = len(list(output_dir.glob("background-attempt-*.*")))
    last_error = None
    auth_token = token or access_token()
    for offset in range(1, 4):
        attempt = existing + offset
        prompt = base_prompt
        if offset > 1:
            prompt += " Previous output was rejected for dark edge bands. Fill every pixel edge-to-edge with visible scenery."
        image, mime = _request(settings["project_id"], prompt, auth_token, send=send)
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[mime]
        background = output_dir / f"background-attempt-{attempt:02d}{ext}"
        fd = os.open(background, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(image)
        try:
            bleed = validate_full_bleed_background(background)
            result = brand_background(background, output_dir / "cover.png", title)
            return {
                **plan, "state": "generated", "generation_count": offset,
                "background_attempt": attempt, "background_sha256": file_hash(background),
                "full_bleed_validation": bleed, **result,
            }
        except VideoError as error:
            if str(error) != "aether_cover_letterbox_detected":
                raise
            last_error = str(error)
    raise VideoError("aether_cover_retry_exhausted") from None
