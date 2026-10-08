# Nine-language article publication

## Approved scope

Future canonical ONNELLAB articles require one complete bundle in English,
Korean, Japanese, Simplified Chinese, Traditional Chinese, Brazilian Portuguese,
German, French, and Spanish. The exact locale identifiers are `en`, `ko`, `ja`,
`zh-Hans`, `zh-Hant`, `pt-BR`, `de`, `fr`, and `es`, matching the homepage registry.
Locale folder identities retain case. Public routes use lowercase segments.
Already published bilingual records and existing public URLs remain unchanged.

The locked phases remain Topic → Research → Article → Images → Publishing.
Do not represent a translated page shell as a translated article. Every locale
needs its own complete manuscript, metadata, image text and current review.
The score remains strictly greater than 9.0, with every mandatory check passing.
Mechanical checks do not establish factual accuracy or translation quality;
the supplier must also review source claims, completeness, natural wording and
rendered images. No invented facts, manufactured quality scores or English
fallback manuscripts may fill a missing translation.

## Schedule and ownership

Keep the existing GitHub publishing workflow as the only canonical publisher:
daily 00:00 UTC checks, with a three-day article cadence at 09:00 Asia/Seoul.
GitHub cron execution can be delayed; its nominal time is not proof of posting.
The separately requested daily evening supplier prepares the next two complete
article bundles before their publication slots. It updates the existing source
queue, not a second external publishing queue. Leave supplied bundles in the
review stage; the canonical publisher owns assignment of publication slots and
published status. Do not run the scheduling CLI at the evening supply time and
misrepresent that preparation time as the later public publication time.
The supplier must re-read current main and
existing receipt state before writing and preserve concurrent unrelated work.
Use the same category/slug bundle identity across all nine locales. Reject a
duplicate ready/scheduled/published bundle. Commit against the exact observed
main SHA with a compare-and-swap/lease; on a concurrent change, re-read and
revalidate rather than overwriting or blindly rebasing generated manuscripts.
This prevents conflicting final writes, but it is not a cross-machine production
lock. Installed old suppliers must be reconciled before claiming single-owner
operation or that duplicate paid generation is prevented.

A new bundle is scheduled only when all nine locales are ready. All nine use
one publication instant. Missing locales, duplicate locale/topic identities,
different dates, stale reviews or failed quality checks hold the whole bundle.
`check_content_supply.py` reports missing languages and qualified bundles;
legacy `qualified_pair_count` report keys count nine-language bundles now.

Only the existing approved distribution channels remain eligible. Medium and
Hashnode stay excluded. This work does not authorize app releases, privacy
policy updates, new accounts, credentials, paid model usage, or another
Work/Codex execution service. The historical Windows `ONNELLAB Codex Content Supply` trigger was separately
verified Disabled on 2026-10-08, with no next run. Only its Enabled flag changed;
its command, files, logs and other tasks were preserved. A repository change
alone must never be presented as updating or disabling an installed supplier.

## ASO, SEO and AEO-aware content planning

ASO optimizes store metadata. These external articles support SEO, relevant
discovery, and informed conversion to verified store listings; they do not
promise store ranking improvements. Do not edit store listings under this scope.
SEO aligns the canonical article with a real search intent and discoverable,
accurate page metadata. AEO makes the answer easy to identify and attribute:
state the question, give a direct short answer, then explain the method and its
limits with trustworthy sources. Neither guarantees ranking, inclusion in an
AI-generated answer, traffic, or installation volume.

For each planned article and locale, record:

1. The reader's concrete task and intended search query.
2. The relevant app name and verified, currently available feature, if applicable.
3. Natural localized primary and secondary keywords for the title, description,
   short answer and optional CTA. Consider local phrasing rather than literal
   keyword translation. Explain the problem before introducing a product.
4. Whether keyword demand comes from actual measured data or is an editorial
   hypothesis. Record the source and observation date for measured claims;
   never invent search volumes or claim that a suggested keyword is proven.
5. The verified platform and destination for a CTA. Use the canonical article
   when no current public store listing is verified. Respect Android-only or
   iOS-only availability and do not imply unreleased functionality.

Use app names and feature terms where they clarify relevance. Avoid keyword
stuffing, repetitive titles, exaggerated outcomes and forced product mentions.
Product-neutral articles remain useful without an installation. Localized body,
title, card title, description, diagram and CTA must describe the same claim.
Use descriptive headings, explicit app/entity names when relevant, and clear
source attribution. Keep comparison criteria, step lists, definitions and FAQ
answers genuinely useful. Do not add misleading structured data or unrelated
FAQ blocks merely to target search engines. Canonical and alternate-language
links must resolve to the correct complete article, never to a missing locale.

## Current app coverage and selection

The source registry contains eight content-eligible apps, including Melivra and
Papira. Choose from verified current releases using reader need, documented
features, localized search intent and recent exposure; do not repeatedly choose
the oldest app merely because it has the largest existing content archive.
Check store evidence before each planned CTA. Target-platform declarations alone
do not prove public availability.

At the inspected source snapshot, Papira has one published bilingual article.
Melivra's TOPIC-0043 is explicitly a video-scenario idea, not an authored blog
manuscript. Preserve that video record and create a separate blog candidate for
Melivra's verified offline local-audio use case. Treat proposed keyword demand
as an editorial hypothesis until measured evidence exists.

The 2026-10-08 public Google Play check confirms both
[Melivra](https://play.google.com/store/apps/details?id=com.onnellab.melivra) and
[Papira](https://play.google.com/store/apps/details?id=com.onnellab.papira).
Papira's Android availability also appears in the 2026-10-07 store snapshot,
but its source notes, registry notes and existing bilingual article still say
Android is unconfirmed. Correct this inconsistency before translating that
claim. Melivra's latest tracked iOS status remains in review; do not promote an
iOS download from an unverified target URL.

## Existing-article translation backlog

Homepage source commit `137faed9` contains 16 article identities: nine complete
nine-language articles and seven bilingual articles. The existing 95 Markdown
pages are not replacement targets. Add only the 49 missing pages, for 144 pages
after completion. Preserve each original publication date, stable slug and
existing public URLs; use self-canonical URLs for each added locale and update
alternate links only for pages that actually exist.

Process one article bundle at a time, with a fresh current-main matrix check:

1. `prepare-txt-manuscript-for-epub` (Papira; correct stale availability first).
2. `keep-durable-research-reading-log` (currently distributed research topic).
3. `choose-media-output-format-before-conversion` (Quivra).
4. `number-tracks-multi-disc-mp3-album` (TagWeaver).
5. `inspect-large-log-file-without-altering-original` (VaultXT).
6. `organize-downloads-small-folder-system`.
7. `turn-rough-notes-into-structured-first-draft`.

For every batch, conduct a separate language-quality review after translation,
preferably independent of the author. Check semantic fidelity, missing sections,
mistranslation, natural local usage, consistent terms, feature/pricing facts,
ASO/SEO/AEO alignment, localized image text, and actual rendered page/link
behavior. Record issues and their corrections by locale, then recheck. An
automated score or the author's own PASS is not completion evidence. Do not
announce a batch complete until the seven new pages and original two pages pass
the relevant checks and the intended deployment is verified.

## Verification and deployment boundaries

The implementation is fail-closed. Source changes, test success, a prepared
queue and a completed public deployment are distinct outcomes.

Local verification on 2026-10-08 passed the full 980-test offline suite (three
pre-existing platform-specific skips), including the actual-data dry-run.
The local renderer used the installed librsvg/Cairo libraries through an
isolated compatibility command. Official CI on commit 0f4434b4 also passed all
three jobs with the supported renderer: Ubuntu Python 3.12/3.14 (three skips
each) and macOS Python 3.14 (17 platform-specific skips). The publishing
push dry-run succeeded; live publication and deployment steps were skipped. Linux workflows install the CJK fonts needed by the
new localized assets; do not claim font rendering from text inspection alone.

The nine-locale tests include a real evaluate/schedule/publish lifecycle using
synthetic fixtures, strict threshold/current-review failures, all-file rollback
and interrupted-journal recovery. Such fixtures are not publishable articles.
The actual first Papira bundle also passed the mechanical checks, separately
from the seven independent language reviews and rendered-image inspection.
Live page/link and deployment verification remain separate release gates.

Preserve unrelated remote commits and use compare-and-swap for final writes.
Changes to publishing.py also match an unrelated privacy-policy push workflow.
For a blog-only integration, prevent that side effect: publish the code with a
commit-scoped CI skip, then trigger validation with a separate change confined
to a read-only test workflow. The second push must not include privacy-triggering
paths. Verify the actual run list, conclusions and skipped live-publishing steps.
Do not pause or reconfigure other owners' tasks as an implicit side effect.
