"""Official Lyria 3 Pro adapter for Aether Inn. Paid calls require --execute."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from short_video_credentials import CredentialError
from lyria_config import (
    CONFIG_PATH,
    MODEL,
    UNIT_PRICE_USD,
    access_token,
    load_settings,
)

API = "https://aiplatform.googleapis.com/v1beta1/projects/{project}/locations/global/interactions"
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
PRIVATE_OUTPUT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/lyria"
SAFE_TEXT = re.compile(r"[\x20-\x7e\u00a0-\uffff]+")


def clean_text(value: str, *, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise CredentialError(f"lyria_{field}_invalid")
    value = " ".join(value.strip().split())
    if not value or len(value) > limit or not SAFE_TEXT.fullmatch(value):
        raise CredentialError(f"lyria_{field}_invalid")
    return value


def build_aether_prompt(title: str, style: str) -> str:
    title = clean_text(title, field="title", limit=160)
    style = clean_text(style, field="style", limit=1800)
    return f"""Instrumental fantasy JRPG field theme for Aether Inn.
Title concept: {title}
Style direction: {style}

Use a warm major key and keep the harmonic center stable. The melody must be memorable but comfortable for repeated listening. Begin with real musical movement immediately; do not use an empty pad-only or atmospheric intro.

[00:00 - 00:25] Begin immediately with warm electric or acoustic guitar carrying a gentle midrange melody. Add restrained piano harmony and soft strings. The feeling is the first steps of a long fantasy journey.
[00:25 - 01:10] Develop the main melody naturally. Add subtle bass and light ensemble support without heavy drums.
[01:10 - 02:05] Expand the emotional space with mellow strings, cello or flute while preserving the original melodic identity and relaxed JRPG field-music character.
[02:05 - 02:40] Gradually lift the harmony and instrumentation. Feel nostalgic, hopeful and quietly exciting, like an old MMORPG journey opening into a wider landscape.
[02:40 - 03:04] Resolve the journey warmly. Remain in the original major key. Use a clear authentic dominant-to-tonic cadence, V-I, and finish firmly on the tonic major chord. The final melody note must resolve clearly to the tonic, then let the final tonic chord ring naturally for several seconds.

The final cadence must sound complete, warm and satisfying. Do not flatten the final melody note. Do not switch to a minor tonic. In the ending, avoid borrowed-minor harmony, modal mixture, bVII endings, deceptive cadences, unresolved suspensions or an ambiguous fade.

No vocals. No aggressive percussion. No EDM energy. No explosive cinematic trailer climax. No sharp high-register piano. No dark ambient opening. No excessive orchestral drama. Clean high-quality stereo production, warm midrange, restrained dynamics."""
    

def estimate_cost(count: int) -> float:
    if type(count) is not int or not 1 <= count <= 5:
        raise CredentialError("lyria_candidate_count_invalid")
    return round(count * UNIT_PRICE_USD, 2)


def parse_audio_response(payload: bytes) -> tuple[bytes, str, dict]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise CredentialError("lyria_response_invalid") from None
    if data.get("status") != "completed" or data.get("model") != MODEL:
        raise CredentialError("lyria_generation_not_completed")
    audio = None
    mime = None
    description = ""
    for item in data.get("outputs") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "audio" and isinstance(item.get("data"), str):
            audio = item["data"]
            mime = item.get("mime_type")
        elif item.get("type") == "text" and isinstance(item.get("text"), str) and not description:
            description = item["text"][:2000]
    if not audio or mime not in {"audio/mpeg", "audio/wav"}:
        raise CredentialError("lyria_audio_missing")
    try:
        raw = base64.b64decode(audio, validate=True)
    except Exception:
        raise CredentialError("lyria_audio_invalid") from None
    if not 1024 <= len(raw) <= MAX_RESPONSE_BYTES:
        raise CredentialError("lyria_audio_invalid")
    return raw, mime, {"description": description}


def request_song(project_id: str, prompt: str, *, token: str | None = None, timeout: int = 240) -> tuple[bytes, str, dict]:
    token = token or access_token()
    body = json.dumps({"model": MODEL, "input": [{"type": "text", "text": prompt}]}, ensure_ascii=False).encode("utf-8")
    request = Request(
        API.format(project=project_id),
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json; charset=utf-8",
            "X-Goog-User-Project": project_id,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
                raise CredentialError("lyria_response_too_large")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        code = exc.code
        if code in (401, 403):
            raise CredentialError("lyria_auth_or_permission_denied") from None
        if code == 429:
            raise CredentialError("lyria_rate_limited") from None
        raise CredentialError("lyria_api_error") from None
    except (URLError, TimeoutError, OSError):
        raise CredentialError("lyria_network_error") from None
    if len(payload) > MAX_RESPONSE_BYTES:
        raise CredentialError("lyria_response_too_large")
    return parse_audio_response(payload)


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value[:72] or "aether-track"


def generate(title: str, style: str, *, count: int | None = None, execute: bool = False, output_root: Path = PRIVATE_OUTPUT) -> dict:
    settings = load_settings(CONFIG_PATH)
    if not settings:
        raise CredentialError("lyria_not_configured")
    if not settings["enabled"]:
        raise CredentialError("lyria_generation_disabled")
    requested = settings["candidate_count"] if count is None else count
    if type(requested) is not int or not 1 <= requested <= settings["candidate_count"]:
        raise CredentialError("lyria_candidate_count_exceeds_config")
    cost = estimate_cost(requested)
    if cost > settings["max_usd_per_run"] + 1e-9:
        raise CredentialError("lyria_spend_cap_exceeded")
    prompt = build_aether_prompt(title, style)
    plan = {
        "model": MODEL,
        "project_id": settings["project_id"],
        "candidate_count": requested,
        "estimated_cost_usd": cost,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "execute": execute,
    }
    if not execute:
        return {**plan, "state": "planned", "prompt": prompt}
    token = access_token()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_root).expanduser() / (timestamp + "-" + slug(title))
    run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(run_dir, 0o700)
    candidates = []
    try:
        for index in range(1, requested + 1):
            audio, mime, meta = request_song(settings["project_id"], prompt, token=token)
            ext = ".mp3" if mime == "audio/mpeg" else ".wav"
            path = run_dir / f"candidate-{index:02d}{ext}"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(audio)
            candidates.append({
                "index": index,
                "file": str(path),
                "mime_type": mime,
                "bytes": len(audio),
                "sha256": hashlib.sha256(audio).hexdigest(),
                "description": meta.get("description", ""),
            })
        manifest = {
            **plan,
            "state": "generated",
            "title": clean_text(title, field="title", limit=160),
            "style": clean_text(style, field="style", limit=1800),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candidates": candidates,
        }
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(manifest_path, 0o600)
        return {**manifest, "manifest": str(manifest_path)}
    except Exception:
        # Keep successfully returned paid candidates for diagnosis/recovery; never silently regenerate.
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--style", required=True)
    parser.add_argument("--candidate-count", type=int)
    parser.add_argument("--output-root", type=Path, default=PRIVATE_OUTPUT)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        result = generate(
            args.title,
            args.style,
            count=args.candidate_count,
            execute=args.execute,
            output_root=args.output_root,
        )
        safe = dict(result)
        if args.execute:
            safe.pop("prompt", None)
        print(json.dumps(safe, ensure_ascii=False, indent=2))
        return 0
    except CredentialError as exc:
        print(json.dumps({"state": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
