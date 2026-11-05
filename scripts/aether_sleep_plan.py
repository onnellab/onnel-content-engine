"""Offline sleep-series brief and repeat timeline; no execution or paid adapter."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "data/aether_sleep_pilot.json"
MODEL = "lyria-3-pro-preview"
ALL_IN_CAP_USD = "0.50"


def amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("aether_sleep_invalid_amount")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("aether_sleep_invalid_amount") from None
    if not number.is_finite():
        raise ValueError("aether_sleep_invalid_amount")
    return number


def repeat_timeline(source_seconds, *, crossfade_seconds=8):
    """Geometry only. Actual seam quality and rendered length remain unverified."""
    source, fade, target = amount(source_seconds), amount(crossfade_seconds), Decimal(1800)
    if not Decimal(30) <= source <= Decimal(184) or not 0 < fade < source / 2:
        raise ValueError("aether_sleep_invalid_loop_source")
    count = int(((target - source) / (source - fade)).to_integral_value(
        rounding=ROUND_CEILING)) + 1
    starts = [float(index * (source - fade)) for index in range(count)]
    assembled = source + (count - 1) * (source - fade)
    return {"target_seconds": 1800, "source_seconds": float(source),
            "crossfade_seconds": float(fade), "repeat_count": count,
            "segment_starts_seconds": starts, "trim_tail_seconds": float(assembled - target),
            "final_fade_out_seconds": 20, "seam_reviewed": False, "rendered": False}


def prompt_for(concept):
    return (
        "Create one original instrumental fantasy sleep composition, about 180 seconds. "
        "This is a dedicated Aether Inn Sleep source, not an adventure single or medley. "
        + concept["direction"] + " "
        "Use very slow harmonic change, soft attacks, stable quiet dynamics and spacious "
        "textures. Keep the opening and ending sparse and compatible for a gentle crossfade. "
        "Keep one coherent tonal center; a quiet stable home harmony should settle naturally "
        "without a dramatic final cadence or a surprise ending. Use understated development. "
        "Instrumental throughout: no singing, speech, percussion, strong beat, abrupt swells, "
        "bright high-register attacks, recognizable existing melodies, or artist imitation. "
        "Return one source composition, not a claim of 30 minutes of unique generated music."
    )


def build_plan(path=PLAN):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    fixed = {"profile": "aether_inn", "series": "aether_inn_sleep", "model": MODEL,
             "request_limit_total": 3, "request_limit_per_composition": 1,
             "paid_retry_limit": 0, "target_duration_minutes": 30}
    if any(type(plan.get(key)) is not type(value) or plan.get(key) != value
           for key, value in fixed.items()):
        raise ValueError("aether_sleep_contract_changed")
    if (plan.get("production_enabled") is not False
            or plan.get("paid_generation_authorized") is not False
            or plan.get("publication_authorized") is not False
            or plan.get("existing_track_ids") != []
            or amount(plan.get("all_in_budget_cap_usd")) != Decimal(ALL_IN_CAP_USD)):
        raise ValueError("aether_sleep_execution_not_supported")
    concepts = plan.get("concepts", [])
    if len(concepts) != 3 or len({row["id"] for row in concepts}) != 3:
        raise ValueError("aether_sleep_three_new_concepts_required")
    base = amount(plan["provider_base_unit_price_usd_observed"])
    if not 0 < base <= Decimal("0.08"):
        raise ValueError("aether_sleep_provider_price_changed")
    return {
        "state": "prepared_not_executable", "profile": plan["profile"], "model": MODEL,
        "paid_authorized": False, "publication_authorized": False,
        "request_count_planned": 3, "paid_retries": 0,
        "base_total_usd_estimate": str(base * 3), "all_in_cap_usd": ALL_IN_CAP_USD,
        "all_in_total_verified": False, "publish_slots": None,
        "blockers": ["account_all_in_cost_unverified", "sleep_worker_extension_not_enabled",
                     "new_audio_and_cover_not_created_or_reviewed", "publication_slots_unspecified"],
        "drafts": [{"id": row["id"], "title": row["working_title"],
                    "prompt": prompt_for(row), "art_brief": row["art"]} for row in concepts],
        "consumer_disclosure": "A newly composed short sleep track repeated and gently joined into a 30-minute video.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-seconds", type=float)
    args = parser.parse_args()
    result = build_plan()
    if args.source_seconds is not None:
        result["illustrative_timeline"] = repeat_timeline(args.source_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
