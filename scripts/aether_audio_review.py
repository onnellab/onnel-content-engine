#!/usr/bin/env python3
"""Gemini audio quality gate for Aether Inn candidates."""
from __future__ import annotations
import base64, json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from lyria_config import access_token, load_settings
from short_video_credentials import CredentialError
from short_video_pipeline import VideoError

MODEL="gemini-2.5-flash"
LOCATION="global"
MAX_AUDIO=16*1024*1024
MAX_RESPONSE=65536
SCORES=("aether_fit","melody_memorability","repeat_listening_comfort",
        "arrangement_development","ending_resolution","technical_cleanliness")
FLAGS={"overly_ambient","aggressive_percussion","edm_or_pop_energy",
       "trailer_bombast","sharp_high_piano","unresolved_ending",
       "unexpected_vocals","technical_artifact"}
REASONS={"weak_aether_fit","forgettable_melody","fatiguing_arrangement",
         "overly_ambient","aggressive_percussion","edm_or_pop_energy",
         "trailer_bombast","sharp_high_piano","unresolved_ending",
         "unexpected_vocals","technical_artifact","insufficient_emotional_arc"}

def prompt(title,style,lane):
    allowed=", ".join(sorted(REASONS))
    return f"""Review the ACTUAL attached audio for Aether Inn, a nostalgic JRPG/MMORPG travel soundtrack archive.
Title: {title}
Intended style: {style}
Concept lane: {lane}
Calm, energetic, flight, sailing, underwater, march, triumph, frontier, night, reunion and farewell themes are all valid.
Require prompt musical movement, a memorable but non-fatiguing melody, coherent development and a satisfying later lift.
Reject combat aggression, EDM/pop drops, trailer bombast, piercing high piano, unwanted vocals, obvious artifacts or a pad-only intro.
Listen especially to the final 10-15 seconds. Major, minor and modal endings are valid, but the ending must resolve to its tonal home.
Reject a leading-tone, dominant, unresolved suspension or other clearly unfinished ending.
Calibration rule: decision="accept" is allowed ONLY when aether_fit>=7, repeat_listening_comfort>=6,
arrangement_development>=6, ending_resolution>=7, technical_cleanliness>=7, and none of
unresolved_ending, technical_artifact, edm_or_pop_energy, or trailer_bombast is true.
If any of those requirements fail, decision MUST be "reject" and reason_codes MUST explain the failure.
Do not return decision="accept" with middling default scores such as all 5s.
Return JSON only:
{{"decision":"accept|reject","scores":{{"aether_fit":0,"melody_memorability":0,"repeat_listening_comfort":0,
"arrangement_development":0,"ending_resolution":0,"technical_cleanliness":0}},
"flags":{{"overly_ambient":false,"aggressive_percussion":false,"edm_or_pop_energy":false,
"trailer_bombast":false,"sharp_high_piano":false,"unresolved_ending":false,
"unexpected_vocals":false,"technical_artifact":false}},"reason_codes":[]}}
Allowed reason_codes: {allowed}"""

def validate(data):
    if not isinstance(data,dict) or set(data)!={"decision","scores","flags","reason_codes"}:
        raise VideoError("aether_audio_review_invalid")
    if data["decision"] not in {"accept","reject"}:
        raise VideoError("aether_audio_review_invalid")
    scores=data["scores"]
    if not isinstance(scores,dict) or set(scores)!=set(SCORES):
        raise VideoError("aether_audio_review_invalid")
    clean={}
    for key in SCORES:
        value=scores[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=float(value)<=10:
            raise VideoError("aether_audio_review_invalid")
        clean[key]=round(float(value),2)
    flags=data["flags"]
    if not isinstance(flags,dict) or set(flags)!=FLAGS or any(type(v) is not bool for v in flags.values()):
        raise VideoError("aether_audio_review_invalid")
    reasons=data["reason_codes"]
    if not isinstance(reasons,list) or len(reasons)>8 or len(set(reasons))!=len(reasons) or any(r not in REASONS for r in reasons):
        raise VideoError("aether_audio_review_invalid")
    critical=flags["unresolved_ending"] or flags["technical_artifact"] or flags["edm_or_pop_energy"] or flags["trailer_bombast"]
    thresholds=(clean["aether_fit"]>=7 and clean["repeat_listening_comfort"]>=6 and
                clean["arrangement_development"]>=6 and clean["ending_resolution"]>=7 and
                clean["technical_cleanliness"]>=7)
    accepted=data["decision"]=="accept" and thresholds and not critical
    weighted=round(clean["aether_fit"]*.24+clean["melody_memorability"]*.18+
                   clean["repeat_listening_comfort"]*.16+clean["arrangement_development"]*.14+
                   clean["ending_resolution"]*.18+clean["technical_cleanliness"]*.10,3)
    return {"accepted":accepted,"decision":data["decision"],"scores":clean,
            "flags":flags,"reason_codes":reasons,"weighted_score":weighted,"review_model":MODEL}

def review_audio(path,title,style,lane,*,token=None,send=None,timeout=180):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".mp3",".wav"}:
        raise VideoError("aether_audio_review_input_invalid")
    audio=path.read_bytes()
    if not 1024<=len(audio)<=MAX_AUDIO:
        raise VideoError("aether_audio_review_input_invalid")
    settings=load_settings()
    if not settings:
        raise CredentialError("lyria_not_configured")
    mime="audio/mpeg" if path.suffix.lower()==".mp3" else "audio/wav"
    body=json.dumps({"contents":[{"role":"user","parts":[{"text":prompt(title,style,lane)},
        {"inlineData":{"mimeType":mime,"data":base64.b64encode(audio).decode()}}]}],
        "generationConfig":{"temperature":0.1,"responseMimeType":"application/json"}}).encode()
    endpoint=("https://aiplatform.googleapis.com/v1/projects/"+settings["project_id"]+
              f"/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent")
    req=Request(endpoint,data=body,method="POST",headers={"Authorization":"Bearer "+(token or access_token()),
        "Content-Type":"application/json; charset=utf-8","X-Goog-User-Project":settings["project_id"]})
    if send is None:
        def send(request): return urlopen(request,timeout=timeout)
    try:
        with send(req) as response:
            raw=response.read(MAX_RESPONSE+1)
    except HTTPError as exc:
        if exc.code in (401,403): raise CredentialError("aether_audio_review_auth_or_permission_denied") from None
        if exc.code==429: raise CredentialError("aether_audio_review_rate_limited") from None
        raise CredentialError("aether_audio_review_provider_rejected") from None
    except (URLError,OSError,TimeoutError):
        raise CredentialError("aether_audio_review_network_error") from None
    if len(raw)>MAX_RESPONSE:
        raise VideoError("aether_audio_review_response_too_large")
    try:
        response=json.loads(raw)
        parts=response["candidates"][0]["content"]["parts"]
        texts=[p["text"] for p in parts if isinstance(p,dict) and isinstance(p.get("text"),str)]
        if len(texts)!=1: raise ValueError()
        result=json.loads(texts[0])
    except (KeyError,IndexError,TypeError,ValueError,json.JSONDecodeError):
        raise VideoError("aether_audio_review_response_invalid") from None
    return validate(result)
