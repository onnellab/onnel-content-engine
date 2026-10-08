"""Canonical article locales, matching the homepage allSiteLocales registry.

Locale identity is case-sensitive; public route segments are lowercase.
Previously published bilingual articles remain historical records. Every new
publication must be a complete nine-locale bundle.
"""

PUBLICATION_LOCALES = ("en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es")
REQUIRED_PUBLICATION_LANGUAGES = frozenset(PUBLICATION_LOCALES)


def public_locale_segment(language: str) -> str:
    if language not in REQUIRED_PUBLICATION_LANGUAGES:
        raise ValueError(f"unsupported publication language: {language}")
    return language.lower()


def require_publication_bundle(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_language: dict[str, dict[str, str]] = {}
    for row in rows:
        language = row["primary_language"]
        if language not in REQUIRED_PUBLICATION_LANGUAGES:
            raise ValueError(f"unsupported publication language: {language}")
        if language in by_language:
            raise ValueError(f"duplicate publication language: {language}")
        by_language[language] = row
    missing = REQUIRED_PUBLICATION_LANGUAGES - by_language.keys()
    if missing:
        raise ValueError("publication bundle is missing language counterpart(s): " + ", ".join(sorted(missing)))
    identities = {(row["category"], row["slug"]) for row in rows}
    if len(identities) != 1:
        raise ValueError("publication bundle must share one category and slug")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("publication bundle must have unique topic IDs")
    return {language: by_language[language] for language in PUBLICATION_LOCALES}
