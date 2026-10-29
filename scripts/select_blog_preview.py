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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="auto", choices=["auto", *PROFILES])
    parser.add_argument("--ref", default="")
    args = parser.parse_args()
    with (ROOT / "data/topics.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    print(environment_lines(select_candidate(rows, args.candidate, args.ref)))

if __name__ == "__main__":
    main()
