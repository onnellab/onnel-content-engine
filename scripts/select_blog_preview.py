"""Choose only an eligible registered review bundle for automatic nonpublishing preview."""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = {"en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"}
PROFILES = {
    "research-source-notes": ("research", "separate-source-notes-from-conclusions"),
    "vaultxt-text-navigation": ("reading", "make-long-plain-text-easier-to-navigate"),
    "tagweaver-album-artists": ("music", "consistent-album-artist-names"),
    "segra-working-copy": ("media", "choose-safe-audio-working-copy"),
}
# Only adapters with a persisted, read-only registration path can be selected automatically.
AUTO_PROFILES = ("segra-working-copy", "research-source-notes")
REFS = {
    "refs/heads/verify/vaultxt-text-navigation-20261024": "vaultxt-text-navigation",
    "refs/heads/verify/tagweaver-caption-20261024": "tagweaver-album-artists",
    "refs/heads/verify/segra-working-copy-20261028": "segra-working-copy",
}

def select_candidate(rows, requested="auto", ref=""):
    if requested != "auto":
        if requested not in PROFILES:
            raise ValueError("Unknown explicit candidate")
        return requested
    if ref in REFS:
        return REFS[ref]
    for name in AUTO_PROFILES:
        category, slug = PROFILES[name]
        bundle = [row for row in rows if row.get("slug") == slug]
        if (len(bundle) == 9 and {r.get("primary_language") for r in bundle} == LOCALES
                and len({r.get("id") for r in bundle}) == 9
                and all(r.get("category") == category and r.get("status") == "review"
                        and r.get("review_required") == "true"
                        and not any(r.get(k) for k in ("scheduled_at", "published_at", "published_url"))
                        for r in bundle)):
            return name
    raise ValueError("No eligible registered unscheduled nine-language review candidate")

def environment_lines(name):
    if name not in PROFILES:
        raise ValueError("Unknown candidate")
    return "\n".join(f"{key}={'true' if name == value else 'false'}" for key, value in (
        ("SEGRA_PREVIEW", "segra-working-copy"),
        ("VAULTXT_PREVIEW", "vaultxt-text-navigation"),
        ("TAGWEAVER_PREVIEW", "tagweaver-album-artists")))

# Registered identities are immutable; an absent bundle is not a no-work result.
REGISTERED_IDS = {
    "segra-working-copy": dict(zip(
        ("en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"),
        ("TOPIC-0041", "TOPIC-0115", "TOPIC-0116", "TOPIC-0117", "TOPIC-0118",
         "TOPIC-0119", "TOPIC-0120", "TOPIC-0121", "TOPIC-0122"))),
    "research-source-notes": dict(zip(
        ("en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"),
        ("TOPIC-0037", "TOPIC-0088", "TOPIC-0089", "TOPIC-0090", "TOPIC-0091",
         "TOPIC-0092", "TOPIC-0093", "TOPIC-0094", "TOPIC-0095"))),
}

def registered_lifecycle(rows, name):
    from datetime import datetime
    category, slug = PROFILES[name]
    identities = REGISTERED_IDS[name]
    group = [r for r in rows if r.get("slug") == slug or r.get("id") in identities.values()]
    if (len(group) != 9 or
            {(r.get("primary_language"), r.get("id")) for r in group} != set(identities.items()) or
            any(r.get("slug") != slug or r.get("category") != category or
                r.get("review_required") != "true" or
                r.get("canonical_path") !=
                    f"generated/markdown/{r.get('primary_language')}/{category}/{slug}.md"
                for r in group)):
        raise ValueError("Invalid registered preview bundle identity")
    states = {r.get("status") for r in group}
    if len(states) != 1 or not states <= {"review", "scheduled", "published"}:
        raise ValueError("Invalid or mixed registered preview lifecycle")
    state = next(iter(states))
    if state == "review":
        if any(r.get(k) != "" for r in group
               for k in ("scheduled_at", "published_at", "published_url")):
            raise ValueError("Review preview must be dateless")
        return state
    def shared_instant(key):
        try:
            dates = [datetime.fromisoformat(r[key]) for r in group]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Missing or invalid lifecycle date") from exc
        if any(d.tzinfo is None or d.utcoffset() is None for d in dates) or len(set(dates)) != 1:
            raise ValueError("Lifecycle dates must share one timezone-aware instant")
        return dates[0]
    scheduled = shared_instant("scheduled_at")
    if state == "scheduled":
        if any(r.get(k) != "" for r in group for k in ("published_at", "published_url")):
            raise ValueError("Scheduled preview has publication fields")
    else:
        if shared_instant("published_at") < scheduled:
            raise ValueError("Publication predates scheduled instant")
        if any(r.get("published_url") !=
               f"https://onnellab.com/blog/{r['primary_language'].lower()}/{slug}/" for r in group):
            raise ValueError("Published preview URL mismatch")
    return state

def selection_environment(rows, requested="auto", ref="", event=""):
    # Only routine main pushes may report no work; manual/verification runs stay strict.
    if event == "push" and ref == "refs/heads/main" and requested == "auto":
        states = [registered_lifecycle(rows, name) for name in AUTO_PROFILES]
        if "review" not in states:
            return "PREVIEW_REQUIRED=false\nPREVIEW_RESULT=no_work\n" + "\n".join(
                f"{key}=false" for key in ("SEGRA_PREVIEW", "VAULTXT_PREVIEW", "TAGWEAVER_PREVIEW"))
    return "PREVIEW_REQUIRED=true\nPREVIEW_RESULT=selected\n" + environment_lines(
        select_candidate(rows, requested, ref))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="auto", choices=["auto", *PROFILES])
    parser.add_argument("--ref", default="")
    parser.add_argument("--event", default="")
    args = parser.parse_args()
    with (ROOT / "data/topics.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if args.event == "push" and args.ref == "refs/heads/main" and args.candidate == "auto":
        if (ROOT / "data/topics.csv").read_bytes() != (ROOT / "topics/topics.csv").read_bytes():
            raise ValueError("Registered topic mirror mismatch")
    print(selection_environment(rows, args.candidate, args.ref, args.event))

if __name__ == "__main__":
    main()
