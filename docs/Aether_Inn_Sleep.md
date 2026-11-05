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
  generated media, enabled flag, paid approval or publication dates.

Existing playlist memberships are never removed. No old song, catalog entry,
rights record, approval, queue or live video metadata is relabeled by this work.
The new source marker is routing metadata, not proof of rights or audio quality.

## Pilot creative brief

Proposed first format: three 30-minute videos, each based on its own new
sleep-specific composition. Length is a proposal pending the production contract.
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

Before actual production, obtain an explicit sleep-source/request and total pilot
budget, choose and validate the long-form method, and agree publication slots.
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
