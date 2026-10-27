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
import aether_paid_guard as paid_guard
from aether_cost_policy import ALLOWED_LYRIA_PURPOSE, require_paid_api_allowed
from short_video_pipeline import atomic_json
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
    return f"""Instrumental fantasy JRPG / MMORPG journey soundtrack for Aether Inn.
Title concept: {title}
Style direction: {style}

Follow the requested travel theme and energy level instead of defaulting every song to a calm field cue. Aether Inn may be quiet, heart-racing, processional, triumphant, airborne, maritime, subterranean or underwater as long as it still feels like melodic fantasy travel rather than combat music or a film trailer.

Choose a tonal center and mode that fit the concept; major, minor, and modal colors are all allowed. Keep that tonal center coherent unless the concept explicitly calls for a modulation. The melody must be memorable but comfortable for repeated listening. Begin with real musical movement immediately; do not use an empty pad-only or atmospheric intro.

Energy and orchestration must follow the style direction:
- Quiet road, town, rain, night or rest themes may use warm guitar, midrange piano, mellow strings, cello, harp, flute or accordion with a gentle pulse.
- Flight and skybound themes may use buoyant 6/8 or flowing 4/4 motion, rhythmic strings or guitar, rising melodic contours and light percussion that suggest lift and speed without cinematic bombast.
- Sailing and open-sea themes may use a rolling pulse, warm strings, guitar, accordion, flute, bass movement and restrained nautical percussion; adventurous, never pirate-battle music.
- Diving, underwater ruins and deepwater themes may use lower-register cello/bass, harp, piano, guitar or soft choir textures with fluid rhythmic motion; mysterious but clearly melodic, never pad-only ambience.
- March, caravan, festival-procession and homecoming themes may use a clear walking pulse, light snare or frame drum, rhythmic guitar/bass, strings and optional warm horns or brass. Proud, exciting and uplifting without military aggression.
- Frontier-surge or high-adventure travel themes may use stronger rhythmic guitar/bass and string ostinati, faster forward motion and a more heart-racing lift, but no EDM drop, battle groove or trailer percussion.

[00:00 - 00:25] State a distinctive motif immediately with instrumentation appropriate to the concept. Establish the travel motion from the first bars.
[00:25 - 01:10] Develop the main melody and rhythmic identity. Add bass and ensemble layers according to the requested energy rather than automatically becoming quieter.
[01:10 - 02:05] Broaden the arrangement while preserving the main motif. Add one or two complementary colors such as strings, cello, flute, accordion, harp, choir texture or warm brass when appropriate.
[02:05 - 02:40] Create the emotional lift of entering a wider world. Scale the intensity to the concept: calm tracks can bloom gently; flight, voyage, march, triumph or frontier tracks may become genuinely exhilarating, but never explode into combat music or cinematic trailer excess.
[02:40 - 03:04] Resolve the journey clearly back to the established tonal center and mode. The final melody must arrive on the tonic/home note in a natural register, often the same or a higher octave, and the final harmony must land on the tonic/home chord appropriate to that mode. In ordinary major or minor tonality, prefer a clear authentic cadence such as V-I or V-i; for a genuinely modal piece, use an equally stable cadential motion back to the modal tonic. Let the final tonic/home harmony ring naturally for several seconds.

The ending must sound complete and settled rather than suspended one step away from home. Do not end the melody on the leading tone or on a note one semitone below the tonic (for example, B instead of C in C major), on the dominant, or on another obviously unresolved tendency tone. Do not force every song into major. Do not introduce an abrupt major/minor/modal shift only at the ending unless the concept explicitly requires it. Avoid deceptive cadences, unresolved suspensions, or an ambiguous fade as the default ending.

No vocals unless the style explicitly requests only a very soft wordless choir texture. No aggressive percussion. No EDM energy. No battle-music drive. No explosive cinematic trailer climax. No sharp high-register piano. No empty dark ambient opening. No excessive orchestral drama. Keep the mix warm, melodic, clear and non-fatiguing even when the track is energetic."""
    

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


def request_song(project_id: str, prompt: str, *, token: str | None = None, timeout: int = 240,
                 slot: str | None = None, intent_path: Path | None = None,
                 intent_sha256: str | None = None, proof_sha256: str | None = None) -> tuple[bytes, str, dict]:
    require_paid_api_allowed(purpose=ALLOWED_LYRIA_PURPOSE, model=MODEL,
                             candidate_count=1, estimated_cost_usd=UNIT_PRICE_USD)
    settings = load_settings(CONFIG_PATH)
    if not settings or not settings["enabled"]:
        raise CredentialError("lyria_generation_disabled")
    if settings["project_id"] != project_id:
        raise CredentialError("lyria_project_mismatch")
    if (settings["candidate_count"] != 1
            or settings["max_usd_per_run"] < UNIT_PRICE_USD - 1e-9
            or settings["max_usd_per_run"] > UNIT_PRICE_USD + 1e-9):
        raise CredentialError("lyria_owner_spend_limit")
    paid_guard.require_generation_window(slot)
    paid_guard.load_paid_proof(project_id, expected_sha256=proof_sha256)
    if intent_path is None or not intent_sha256 or not proof_sha256:
        raise CredentialError("aether_lyria_charge_intent_required")
    raw = paid_guard._read(intent_path)
    intent = paid_guard._json(raw)
    if (hashlib.sha256(raw).hexdigest() != intent_sha256 or intent.get("state") != "prepared"
            or intent.get("model") != MODEL or intent.get("project_id") != project_id
            or intent.get("slot") != slot or intent.get("candidate_count") != 1
            or not isinstance(intent.get("cost_proof"), dict)
            or intent["cost_proof"].get("proof_sha256") != proof_sha256
            or intent.get("prompt_sha256") != hashlib.sha256(prompt.encode("utf-8")).hexdigest()):
        raise CredentialError("aether_lyria_charge_intent_invalid")
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
    # A second caller cannot dispatch the same prepared intent, even after an
    # exception or lost response. The claim is retained, never automatically reset.
    try:
        fd = os.open(Path(intent_path).with_name("dispatch.claim"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise CredentialError("aether_lyria_generation_uncertain") from None
    os.close(fd)
    dispatched = False
    try:
        # Persist BEFORE POST; then repeat all time/evidence checks after fsync.
        intent.update(state="request_started", dispatch_started=True,
                      request_started_at=paid_guard.utc_now().isoformat())
        atomic_json(intent_path, intent)
        paid_guard.require_no_unsettled_intents(extra_roots=(Path(intent_path).parent.parent,), current_intent=intent_path)
        require_paid_api_allowed(purpose=ALLOWED_LYRIA_PURPOSE, model=MODEL,
                                 candidate_count=1, estimated_cost_usd=UNIT_PRICE_USD)
        current_settings = load_settings(CONFIG_PATH)
        if (not current_settings or current_settings.get("enabled") is not True
                or current_settings.get("project_id") != project_id
                or current_settings.get("candidate_count") != 1
                or current_settings.get("max_usd_per_run") != 0.08):
            raise CredentialError("lyria_owner_spend_limit")
        if paid_guard._json(paid_guard._read(intent_path)) != intent:
            raise CredentialError("aether_lyria_charge_intent_invalid")
        final_proof = paid_guard.load_paid_proof(project_id, expected_sha256=proof_sha256)
        final_now = paid_guard.utc_now()
        if not paid_guard._time(final_proof["checked_at"]) <= final_now < paid_guard._time(final_proof["expires_at"]):
            raise CredentialError("aether_lyria_cost_proof_expired")
        paid_guard.require_generation_window(slot, now=final_now)
        dispatched = True
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
    finally:
        if not dispatched:
            # This process knows it never entered transport. Preserve evidence;
            # do not use this state for any exception after urlopen was entered.
            try:
                unchanged = paid_guard._json(paid_guard._read(intent_path)) == intent
            except (CredentialError, OSError):
                unchanged = False
            if unchanged:
                atomic_json(intent_path, {**intent, "state": "not_sent", "dispatch_started": False})
    if len(payload) > MAX_RESPONSE_BYTES:
        raise CredentialError("lyria_response_too_large")
    return parse_audio_response(payload)


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value[:72] or "aether-track"


def generate(title: str, style: str, *, count: int | None = None, execute: bool = False,
             output_root: Path = PRIVATE_OUTPUT, slot: str | None = None) -> dict:
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
    if execute:
        require_paid_api_allowed(purpose=ALLOWED_LYRIA_PURPOSE, model=MODEL,
                                 candidate_count=requested, estimated_cost_usd=cost)
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
        return {**plan, "state": "planned", "prompt": prompt, "paid_authorized": False,
                "cost_basis": "static_base_estimate_not_gross_cost_proof"}
    paid_guard.require_generation_window(slot)
    proof = paid_guard.load_paid_proof(settings["project_id"])
    with paid_guard.paid_request_lock():
        paid_guard.require_no_unsettled_intents(extra_roots=(output_root,))
        return _execute_generation(title, style, output_root, slot, settings, plan, prompt, proof)


def _execute_generation(title, style, output_root, slot, settings, plan, prompt, proof):
    token = access_token()
    paid_guard.load_paid_proof(settings["project_id"], expected_sha256=proof["proof_sha256"])
    paid_guard.require_generation_window(slot)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_root).expanduser() / (timestamp + "-" + slug(title))
    run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(run_dir, 0o700)
    # Durable charge intent is recorded before contacting the provider. On an
    # ambiguous API failure, the existing job must not pay for a second attempt.
    manifest_path = run_dir / "manifest.json"
    manifest = {
        **plan,
        "state": "prepared",
        "slot": slot,
        "cost_proof": proof,
        "dispatch_started": False,
        "title": clean_text(title, field="title", limit=160),
        "style": clean_text(style, field="style", limit=1800),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "candidates": [],
    }
    atomic_json(manifest_path, manifest)
    os.chmod(manifest_path, 0o600)
    # This owner's authorization permits precisely one provider request per
    # single; it does not authorize retries or multi-candidate generation.
    audio, mime, meta = request_song(settings["project_id"], prompt, token=token, slot=slot,
                                   intent_path=manifest_path,
                                   intent_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                                   proof_sha256=proof["proof_sha256"])
    manifest = paid_guard._json(paid_guard._read(manifest_path))
    ext = ".mp3" if mime == "audio/mpeg" else ".wav"
    path = run_dir / f"candidate-01{ext}"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(audio)
        stream.flush()
        os.fsync(stream.fileno())
    manifest.update(
        state="generated",
        generated_at=datetime.now(timezone.utc).isoformat(),
        candidates=[{
            "index": 1,
            "file": str(path),
            "mime_type": mime,
            "bytes": len(audio),
            "sha256": hashlib.sha256(audio).hexdigest(),
            "description": meta.get("description", ""),
        }],
    )
    atomic_json(manifest_path, manifest)
    return {**manifest, "manifest": str(manifest_path)}


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
