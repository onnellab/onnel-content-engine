# Aether Inn Local Daily Worker

## Purpose

The daily Aether/YouTube operations path must not depend on a scheduled ChatGPT
turn successfully dispatching a Remote Desktop terminal command. Scheduled tool
orchestration can reject a terminal call before it reaches the worker Mac even
when Desktop Commander, the repository, Keychain, and the same command are healthy.

The root architecture therefore separates execution from reporting. The hosted
operations component workflows used by this daily pass are `workflow_dispatch`-only;
they do not own independent cron schedules. This keeps `launchd` as the single
scheduled owner and prevents the same source refresh from running again later in
the morning.

1. macOS `launchd` starts `scripts/aether_daily_local.py` locally each morning.
2. The local worker owns operations that require the Mac user session, Keychain,
   Google ADC, MYBOX, ffmpeg, or the durable Aether queues.
3. The scheduled ChatGPT task is read-only: it verifies the durable daily result,
   supporting report files, GitHub workflow/commit evidence, and the live `/ops/`
   page. The local worker owns hosted source refreshes, review notification
   preparation, and `/ops/` reconciliation/deployment as well as local production.
   Since 2026-10-14 it cannot approve or publish a store review reply.
   ChatGPT must not dispatch, retry, compensate for, or duplicate any of them.

This is an execution-boundary fix, not a relaxation of any safety gate.

## Local schedule and result

The installed user LaunchAgent is `com.onnellab.aether-daily-local` and starts at
06:20 Asia/Seoul so the 07:00 operations pass can consume its result while leaving
time for the fail-closed 09:00 Tuesday/Saturday publication boundary.

The durable local result is:

    ~/Library/Application Support/ONNELLAB/content-engine/daily-aether/result.json

Scheduled verification first requires `kind=onnellab_aether_local_daily_result`,
`mode=daily`, and `local_date` equal to the current Asia/Seoul date. A missing or
stale daily result is `local_aether_launchagent_stale`, never permission to start
another worker. If `state=running`, re-read during the same invocation when
practical. For `partial` or `failed`, preserve all durable job/video/approval IDs
and report the recorded blockers without a second production/publication attempt.

Remote Desktop is limited to file reads for the durable result and supporting
reports during scheduled verification. No terminal/process execution, shell,
`gh`, Python worker, ffmpeg, OAuth/Keychain command, probe, or equivalent local
command may run or compensate for Aether/YouTube/Ops work from that task. Connected
GitHub reads and public-page reads are verification only; unavailable, stale,
not_applicable, and manual-only sources must not be reported as live-verified.

The result contains status, safe worker outputs, exact blockers, and timestamps.
It must never contain OAuth tokens, client secrets, refresh/access tokens,
authorization headers, Keychain payloads, service-account JSON, or private keys.

Provider-pricing snapshots contain only current provider prices that the collector
can actually verify. The `$25/1M characters` translation figure remains only in
`data/melivra_ai_credit_policy.csv` as a conservative planning assumption; it is
not reported as a current DeepL API price.

## Local responsibilities

Every normal run uses current `main` only after a clean fast-forward check. A dirty,
diverged, locally-ahead, or unrefreshable content-engine checkout fails closed rather
than using unknown or cached remote state. A failed `git fetch` is a blocker and
must not be followed by divergence decisions against a stale `origin/main`. The worker then:

- refreshes ONNELLAB and Aether Inn private YouTube reports independently;
- refreshes the public-safe YouTube ops snapshot and AI-provider pricing status;
- commits and pushes only those expected local operational snapshots;
- dispatches and waits for the canonical `Sync app operational status`,
  `Refresh AI Operations Sources`, and `Sync Store Reviews` GitHub Actions in
  that order, with dashboard deployment disabled on the app/review sync calls, then
  runs the dedicated `Deploy Ops Dashboard` workflow exactly once after any
  store-review notification preparation; that final workflow rebuilds and
  deploys `/ops/` from the combined hosted and local snapshots and verifies
  custom-domain bytes, indexing directives, robots.txt, sitemap/navigation exclusion,
  and legacy-route absence into `data/ops_live_verification.json`;
- after the fresh review sync, prepares pending owner notifications in
  `data/store_review_notifications.json`, mirrored in the daily result's
  `store_review_notifications` field. It never creates standing approvals,
  dispatches a reply publisher, or retries a queued/failed public reply. The
  owner-chat reporter delivers each current notification once and records the
  returned owner-message receipt; see `docs/Store_Review_Response_Guide.md`;
- reconciles existing durable Aether single and compilation jobs; when the
  single reconcile already returns a same-day durable job/video in scheduled,
  processing, or published state, that exact job becomes the slot result and the
  wrapper does not touch the backlog WAV or create another upload;
- synchronizes the six canonical Aether playlists idempotently;
- on Tuesday/Saturday before 09:00 KST, processes the first actually-missing
  canonical backlog WAV with its own approved cover. Only after all canonical
  backlog entries are independently confirmed already public may the launchd-owned
  wrapper attempt ONE newly approved-cover Lyria 3 Pro single at a fixed estimated
  $0.08 charge. New audio generation must start before 08:00 KST, be authorized
  by the local enabled/candidate/spend controls, and use the same durable single
  queue and the exact 09:00 PRIVATE + publishAt YouTube policy. No per-song cover
  approval means no spend or generated candidate; Lyria may never replace a
  missing backlog master. The wrapper re-reads current KST before each backlog
  attempt, and the canonical single worker checks the deadline again before a
  first upload. Crossing 09:00 prevents late publication;
- on every other Sunday beginning 2026-09-27, invokes at most one canonical
  existing-track compilation worker.

All music generation, cover, render, upload, thumbnail, publishAt, public-inventory
cross-check, same-video reconciliation, rights gates, and playlist classification
remain owned by the canonical repository workers. The daily wrapper does not
reimplement or weaken those contracts.

## Scoped paid-API production policy (owner authorization 2026-10-10)

Only `lyria-3-pro-preview` is enabled for **one** paid generated song at an
estimated **$0.08 per eligible single**. `aether_cost_policy.py` requires the
specific Lyria purpose, exact model, one candidate and no more than $0.08;
`lyria_config.py` enforces the matching enabled local settings. The installed
Mac config was already enabled for one candidate and a $0.08 per-run cap when
this owner authorization was given. An error or uncertain response does NOT
authorize a retry. The generator writes a private `request_started` manifest
before the charged request and blocks resuming an uncertain result without
additional owner action.

Gemini paid image generation, Gemini paid audio review, and all other paid
providers remain blocked before credentials or API requests. There is no generic
environment, CLI or settings bypass. Existing music/cover/result records and
uploaded video IDs are preserved; uploaded jobs reconcile only their hash-bound
video and thumbnail, never regenerate missing source media.

The no-cost single-cover path requires per-title, hash-bound commercial-use and
quality approval. Missing approval or artwork stops the slot rather than falling
back to a paid image request. See [Existing Single Covers](Aether_Inn_Existing_Covers.md).
The compilation worker continues using its existing approved masters/artwork and
local render path. Production runtime installation must be verified separately
from a repository commit; source tests do not prove a live upload or Mac update.

## Autonomous no-cost audio quality gate

Song-by-song owner listening approval is **not** a prerequisite for audio
selection. The canonical worker analyzes the actual local WAV/MP3 with
`scripts/aether_offline_audio_review.py` before a new single is accepted.
It measures PCM loudness, clipping, silence, start/end continuity and
rudimentary temporal variation, records the exact audio SHA-256, and rejects
failures without asking the owner to rubber-stamp a candidate. Backlog masters
use this path; existing/generated candidates also use the same no-cost gate
when a production source is available.

For compilation assets, the owner-attested **commercial-use rights** field
continues to be mandatory. A track with `quality_accepted=false` and the
explicit `quality_basis=not_yet_owner_quality_approved` can be evaluated
automatically. Accepted tracks get a separate SHA-bound quality decision in
the private compiled manifest; the original owner-approval file is not
modified or rewritten as an owner signature. An explicitly rejected track or
one without rights attestation must not be silently approved.

This is an *automated signal-quality check*, not human/AI listening, legal
originality certification, or a claim to judge melody memorability, genre
fit or harmonic resolution. Inconclusive/malformed/unreadable material fails
closed, with no synthetic perfect score. The paid Gemini listening service
and paid cover API remain **disabled**. Only the owner-authorized one-candidate
Lyria 3 Pro generation is enabled within its explicit budget and readiness
limits. Missing separately approved cover artwork or
unverified commercial rights remain blockers; the audio quality delegation
does not authorize bypassing those gates.

## Fail-closed compilation-only recovery (MYBOX)

A `partial` report with **only** `aether_asset_source_materialization_failed`
may be recovered on the **same Asia/Seoul date** by another invocation of the
**same installed LaunchAgent**. An invocation of
`scripts/aether_daily_local.py` after a same-day report now always checks that
report before it can touch operational data:

- `complete` returns `already_complete`; `running`, `failed`, malformed,
  and non-recoverable `partial` records fail closed and never rerun the daily
  YouTube/Ops/review/single workflow.
- Compilation-only recovery requires the original current-date daily result,
  the correct biweekly Sunday theme, that *one* recorded materialization blocker,
  an idle compilation reconcile, synced playlists, **no compilation worker step**
  or possible job/video/upload ID, and fewer than two same-day recovery attempts.
- It preserves the original daily result, original workflow/approval/video IDs,
  step history and other operational outcomes. The isolated recovery first
  checks/pulls the current clean `main`, then retries only compilation asset
  registration and, if successful, enters the canonical idempotent compilation
  worker for the **same date/theme**. All rights, local PCM quality, cover,
  upload, profile, thumbnail and public-observation guards still apply.
- A first normal Sunday run itself allows two bounded delayed retries of
  **asset registration only** after MYBOX materialization errors (45 s and
  120 s). No delay/retry is permitted for approval, rights, quality, cover,
  job/upload uncertainty or any other error. Once the publication worker
  begins, it is never retried by this recovery route.
- Every attempt is checkpointed in `result.json` under
  `compilation_recovery_attempts` and `steps`. Successful recovery removes
  the resolved transient blocker; other original blockers would remain.
  `complete` is an operations-pass state, not proof of public video publication.

The existing installed `com.onnellab.aether-daily-local` currently fires only
at 06:20. **Repository code changes do not themselves install a revised
LaunchAgent or start an immediate retry.** To permit unattended same-day
recovery after a cloud hydrate completes, the owner-controlled local LaunchAgent
installation must retain the 06:20 first invocation and add two later
calendar triggers (for example 07:20 and 08:20) to the *same label, script,
lock, result path and OS user*. The script's same-day guard makes these later
invocations either a safe isolated compilation resume or a no-op; no separate
production owner or extra ChatGPT task is introduced.

Example for the existing plist's `StartCalendarInterval`, applied/reloaded
**only through authorized local maintenance**, never from scheduled ChatGPT:

```xml
<key>StartCalendarInterval</key>
<array>
  <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>20</integer></dict>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>20</integer></dict>
  <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>20</integer></dict>
</array>
```

Do not enable these later triggers until both the new recovery code and
matching tests are installed on the Mac, the LaunchAgent's new schedule has
been loaded, and the Mac's effective launchd configuration is verified.
Do not kickstart, execute a shell, run a probe or trigger a replacement job
from the reporting-only ChatGPT task. Until the install is verified, report
the partial result honestly; a GitHub commit or an MYBOX file listing is
**not** evidence that today's compilation was produced.

## GitHub workflow watch 502 reconciliation

The Mac LaunchAgent is the **only** executor and dispatcher. A nonzero exit from
`gh run watch --exit-status` is ambiguous because the GitHub **jobs** API can
return HTTP 502 while the already-dispatched workflow ultimately succeeds.
Never classify the watched workflow as failed solely from this CLI exit.

After a nonzero watch, the same local worker now polls the read-only
`/repos/onnellab/onnel-content-engine/actions/runs/<original-run-id>`
endpoint. The query returns only an allowlisted set of run metadata:
`id, name, status, conclusion, event, head_branch`. To trust the result it
must match the dispatched run ID, expected workflow name, `workflow_dispatch`
event and `main` branch. Run/job logs, credentials and headers are never
written to the durable report.

- `completed + success` => `success` with
  `verification_source=same_run_api` and
  `workflow_watch_error_recovered:<step>` warning.
- `completed + failure/cancelled/timed_out/other nonsuccess` => real
  `failed` with the confirmed conclusion.
- In progress, unavailable API, malformed or mismatched run identity, or
  missing terminal conclusion => bounded read-only polling, then `unverified`
  with an explicit `*_workflow_verification_unavailable` blocker.
- The polling is limited to 90 metadata reads spaced 10 seconds apart, with
  early fail-closed stop after 6 consecutive read errors. No workflow is
  dispatched or retried during reconciliation.
- Hosted workflow verification failures stop the dependent hosted stage but do
  not automatically cancel independent Aether reconciliation or music slots;
  those still require the usual clean-worktree and timing gates.
- For the sequential app/AI/review source sync chain, a truly failed or
  unverified predecessor prevents subsequent dispatches, reply approvals,
  notification preparation and the Ops deploy. The Ops deploy uses the same
  read-only check. Historical already-dispatched review
  replies retain their durable approval IDs and still require store-observed
  reply proof before being reported as published.

A prior local `partial` result with a watch error is **historical evidence**:
reconciling its status for a report is read-only and does not rewrite the old
`result.json`, reset its same-day state or trigger any production compensation.
Scheduled ChatGPT verification remains file/GitHub-read-only; it must not invoke
this helper independently, call local commands, or start GitHub workflows.

## Failure behavior

The worker is single-instance. A second normal invocation on the same KST date
returns `already_complete` without repeating work when the durable daily result is
already `complete`. It records a blocker and stops or skips the affected stage when
repository state, credentials, source WAVs, publication timing, worker readiness, or
canonical worker results are unsafe. Repository refresh failures block
before cached remote refs are trusted. It never compensates for a stale 09:00 single
slot by publishing immediately, never creates a replacement upload to
escape an uncertain durable session, and never launches interactive authorization.

Every step checkpoints `active_step` before launching its command and saves the
completed step afterward. Exceptions retain the original start date, completed
steps, warnings, blockers, and durable IDs; only the failure state, finish time,
and safe exception-class blocker are added. Failure before owning a report leaves
the existing result untouched. Timeout output is decoded before JSON serialization.

Manual-only `--probe` performs a non-paid connectivity/readiness check and writes
`probe-result.json`, never the authoritative daily `result.json`. It may refresh
read-only YouTube reports but never generates music, renders media, or publishes
a video. Scheduled ChatGPT verification must not invoke this probe.


## Recovered local backlog masters

An existing per-title commercial-rights row in private `assets/approval.json` may
carry `local_master` with an assets-relative `path`, exact WAV `sha256`, and
`source_filename` equal to the exact catalog title plus `.wav`. Stage the original
bytes under `assets/staged/singles/masters/`; do not replace MYBOX originals or
create queue jobs to make a source reusable. The worker checks profile, title,
rights, regular local files, symlinks, SHA and conflicting retained masters. It
then applies the usual duration and offline-audio review on import. This mapping
does not change existing quality approval, attest human listening, authorize a
new music charge, or complete an upload.

## 2026-10-31 Aether single owner-inventory preflight hardening

The 2026-10-31 06:33 KST local job for **Across the Frontier Before Sunrise**
was blocked at **`aether_single_remote_inventory_unverified`** *before* the
Lyria request, with no audio, upload, video ID, thumbnail or publishAt. The job
remains under its existing durable ID `12f0b00ce03459ffa4e0c63e` in the
same Mac single queue. The then-current exception collapsed multiple YouTube
API response mismatches into that one code, so the exact failing response
condition **cannot be reconstructed** from the saved 2026-10-31 receipt.
A successful six-playlist sync (67 videos considered) is *not* proof that the
stricter owner-only title-inventory preflight saw every public/private/unlisted
upload or matched all its `videos.list` details.

The canonical single worker now uses a bounded read-only enumeration of the
authenticated owner's uploads: `channels.list(mine=true)`, complete uploads
`playlistItems.list` pagination, then `videos.list` per page. It requests
only `id`, `snippet.channelId/title` and `status.privacyStatus` plus
upload/video IDs; the unused, privileged `processingDetails` data and
bulky descriptions/tags are omitted using Google API `fields` filtering.
If a bulk `videos.list` response omits records, the worker performs at most
one additional read of only those missing IDs, then **fails closed** unless
every ID is observed with exact owner/title/privacy information. Other holds
cover wrong channel, invalid uploads playlist, malformed/duplicate IDs,
unknown ownership/privacy, pagination anomalies, and a playlist inventory
smaller than the supplied public video count. Existing title collisions
(including private and scheduled videos) still block immediately.

The original blocker `aether_single_remote_inventory_unverified` remains
stable. New subreasons and bounded counts are recorded in
`remote_inventory_diagnostic` both in the private queue and in the local
daily-result step; no private video IDs, channel search results, token values,
credentials, or raw provider payloads are recorded. The next *ordinary*
Tuesday/Saturday LaunchAgent run may classify an intermittent API omission and
continue only after full verification. Persistent inaccessible/ambiguous
remote videos still HOLD. No manual/ChatGPT fallback, no duplicate upload,
no paid generation before inventory verification and no 09:00 catch-up.

**Do not rerun the 2026-10-31 production slot.** It is already stale after
09:00 KST. Deploying repository code does not change the installed LaunchAgent
or start a worker; its existing scheduled owner will fetch main on the next run.
Any exact root-cause subtype can only be confirmed on fresh worker evidence,
not inferred retroactively from the old generic exception.
