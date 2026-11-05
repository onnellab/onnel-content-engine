# Aether Inn Sleep pilot

## Owner-approved direction, 2026-11-05

Keep the existing Aether Inn channel and fantasy singles. Create a separate
Aether Inn Sleep playlist for newly composed sleep music, not a compilation of
existing tracks. Prepare a few trial videos with consistent dark artwork, then
compare audience response before deciding whether to expand. No separate channel.

This change implements playlist preparation and an inactive pilot brief only.
It does not authorize new generation spend, schedule a video, or create a second
producer. The existing single and existing-master compilation schedules remain
unchanged.

## What is implemented

- A seventh canonical playlist, exactly titled `Aether Inn Sleep`.
- A narrow `aether_playlists.py --ensure-playlist sleep --execute` command that
  verifies the existing Aether profile, creates or reuses only this playlist, and
  reads back the exact playlist ID, title, owning channel and public status.
  It never enumerates or adds videos. An uncertain create must be reconciled by
  reading existing playlists; do not blindly repeat a POST.
- Normal playlist synchronization recognizes only explicit
  `series=aether_inn_sleep` on eligible jobs in the existing single queue.
  New sources must carry `source_kind=purpose_composed_sleep`; catalog matches
  and legacy backlog sources fail closed. Rest/night/sleep words never reclassify
  existing music. Sleep videos are assigned only to the sleep playlist.
- `data/aether_sleep_pilot.json` stores three working concepts and measurement
  criteria. It is not consumed by the daily producer and contains no job IDs,
  generated media, enabled execution or publication dates. The selected provider
  and bounded pilot budget are not a live cost-verification receipt.

Existing playlist memberships are never removed. No old song, catalog entry,
rights record, approval, queue or live video metadata is relabeled by this work.
The new source marker is routing metadata, not proof of rights or audio quality.

## Pilot creative brief

Selected first format: three 30-minute videos, each repeating and gently joining
its own new Lyria sleep composition. The owner selected Lyria after this format,
one request per composition, no paid retries and an initial USD 0.30 including-tax
cap were proposed. The owner subsequently raised the total ceiling to USD 0.50,
including taxes and mandatory costs. This is not 30 minutes of distinct generated material.
No existing-master medley and no replacement of regular fantasy singles.

1. Moonlit Guestroom: soft midrange keys and warm strings in a dark indigo inn.
2. Stillwater Sanctuary: low warm textures and sparse plucks by a quiet teal lake.
3. Cloudrest Chamber: slow sustained strings above muted violet clouds.

Use restrained harmony, low transient intensity, stable volume, sparse melodic
movement and no drums, dramatic transitions, vocals, spoken introductions or
bright high-register piano. Avoid hard starts/stops and obvious looping seams.
Do not inherit the adventure singles' immediate-melody or high-motion quota.

Artwork shares a full-bleed dark fantasy environment, restrained warm light,
readable small Aether Inn Sleep branding and consistent typography. Dark means
quiet color and contrast, not black letterbox bars or an unreviewed blank image.
Use separately approved commercial-use artwork. No paid cover API is enabled.

## Production remains gated

The existing Lyria permission is one eligible fantasy single request at a provider
base price of at most USD 0.08. It is not blanket permission for three sleep
compositions, 30-minute generation, repeated extensions or a new upload cadence.
Do not change the existing paid guard or mislabel a sleep request as a normal
single. Tax, FX and invoice totals remain separate from the base-price estimate.

The owner subsequently selected the separately proposed Lyria pilot with three
one-shot requests and an all-in ceiling, since revised to USD 0.50. That selected preparation is
recorded separately from execution readiness. Before actual production, verify
the account-specific all-in cost and validate the long-form method. Publication
slots remain unspecified; preparation approval is not immediate-publication approval.
If one new composition is extended into 30 minutes, that method must be explicit;
a 30-minute runtime is not evidence of 30 minutes of distinct newly generated music.
Commercial rights, provenance, current source terms, approved cover, PCM checks,
render validation, YouTube identity and publication checks remain required.
Do not create credentials, accept new terms or enable another paid provider.

Extend the existing canonical worker only after that contract is settled.
Keep `com.onnellab.aether-daily-local` as sole unattended producer, the existing
locks and exact durable single queue, and no new timer or parallel publisher.
Do not run a production worker from the read-only daily reporting task.

## Evaluation

Record actual video ID, duration and public timestamp at publication. Compare
each video at 7 and 28 days with fantasy singles of equal time since publication.
Report views, total watch minutes, average view duration, average percentage
viewed and traffic sources. Show reach and runtime differences rather than
claiming this is a controlled experiment or treating longer runtime alone as
better retention.

Use returning-viewer data only at the scope YouTube actually provides. If no
series-level breakdown is available, show channel-level context and mark it
unattributed. Small samples and missing metrics are inconclusive. The pilot has
no promise of sleep benefit, medical efficacy or monetization performance.

## Initial verification, 2026-11-05

318 Aether tests passed with the repository's network-blocking test context and
zero network attempts. The standard aggregate runner could not start under the
system Python because PyYAML was absent; CI is tracked separately. Both existing
live queues had no active jobs before this work and were preserved byte-for-byte.
No music, cover or rendering process was started.

The narrow live playlist command stopped before provider access with
`keychain_locked_or_access_denied`. This is not a creation receipt. No playlist
ID or URL was returned, and no alternate credential path or security change was
attempted. The existing canonical sync can ensure the playlist when its normal
profile access is available; do not create a replacement timer or producer.

## Lyria selection and offline preparation, 2026-11-05

The owner's reply, after the bounded three-video proposal and Suno comparison,
was `그럼 그냥 lyria로 해`, followed by `0.50달러 기준으로 해`. Preserve the latest
scope: three new compositions, one charged request each, zero paid retries,
total including taxes and mandatory costs at most USD 0.50. The selected method
repeats each new short composition into its own
30-minute video. Do not silently require another approval for the same selection;
ask only for missing information or a material change. Publication timing was
not supplied, so no dates or immediate-publication decision have been invented.

`scripts/aether_sleep_plan.py` is an offline-only planner. It creates three
distinct prompt drafts and an illustrative repeated-source timeline. It has no
execute flag, credential lookup, request dispatch, queue writer or renderer.
All outputs explicitly report `paid_authorized=false` and
`publication_authorized=false`. These execution flags do not erase the owner's
selected preparation. Use `--source-seconds 184` to inspect the geometry of a
possible source; it is not an actual-audio measurement or seam-quality result.
An eight-second crossfade is a planning default, not an approved audible join.
Actual music, looping seams, volume, ending and artwork must still be reviewed.

Read-only checks found the existing Lyria configuration enabled for the exact
model, one candidate and USD 0.08 provider-base cap, with authentication usable.
The canonical unsettled-request scan was clear. These checks do not certify
billing, publication readiness or an audio generation. The public provider
receipt was refreshed through the existing collector at 2026-11-05 05:32:30 UTC,
valid until 2026-11-06 05:32:30 UTC; no new agreement was accepted.

Official sources checked on 2026-11-05:
- [Lyria model and commercial-use permission](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/lyria/lyria-3?hl=en): exact model, at most 184 seconds and one clip per prompt.
- [Provider price](https://cloud.google.com/model-garden/pricing?hl=en): USD 0.08 per full song, USD 0.24 for three before taxes and currency adjustments.
- [Preview exception](https://cloud.google.com/terms/genai-preview-products?hl=en): Lyria 3 Pro is explicitly excepted from the default preview commercial-use restriction.
- [Service terms](https://cloud.google.com/terms/service-terms): use remains subject to the existing account agreement; public permission does not establish originality or non-infringement.
- [Taxes](https://docs.cloud.google.com/billing/docs/resources/vat-overview): displayed SKU prices exclude taxes. South Korea is listed at 10% VAT, but the user's billing location must not be inferred from language or timezone.

If the actual account uses USD pricing and the South Korean VAT treatment, the
arithmetic would be USD 0.264 before any other mandatory adjustment. This is a
conditional illustration, not verified billing. Keep production stopped until
the existing account's tax/currency/mandatory-charge basis fits the all-in cap.
The ordinary fantasy-single paid guard is unchanged and must not be reused to
mislabel a sleep request. All 324 Aether tests passed with zero network attempts.

A read-only query of the configured project's billing link exited with code 1.
No billing account, country or currency was established from that query; no new
credentials or permissions were requested. This remains a billing-information
blocker, not evidence of a disabled billing account or a generation failure.

## Budget revision, 2026-11-05

The owner explicitly revised the total ceiling to USD 0.50. This replaces only
the prior USD 0.30 cap; it does not increase the three-request allowance, the
one-request-per-composition limit or the observed USD 0.08 provider-base price.
Zero paid retries remains unchanged. Taxes and all mandatory charges count
against the same USD 0.50 total, not a separate allowance.

The budget increase does not verify the billing country, currency or other
mandatory costs, authorize a new credential/permission, or specify publication
dates. No paid POST, playlist retry, queue mutation or production launch is
part of this revision. The existing billing-read failure remains unresolved;
changing the budget alone is not evidence that the read or YouTube credential
access can now succeed. Continue offline preparation and obtain the missing
account-specific cost basis and publication slots before enabling execution.
The revised cap and unchanged inactive guards passed 326 Aether tests with zero
network attempts. The offline estimate remains USD 0.24 before account-specific
taxes and mandatory adjustments; it is not a new generation or billing receipt.
