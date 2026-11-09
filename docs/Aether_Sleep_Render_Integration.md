# Sleep pilot integration, 2026-11-09

The owner requested one sleep release today and recurring alternation with fantasy
music. The three-composition / USD 0.50 all-in ceiling, one request each, no paid
retries and sole existing Mac producer remain mandatory. This implementation does
not claim that any track has been generated, reviewed or published.

## Existing owner, queue and transport

`aether_daily_local.py` owns execution under its existing worker lock. Its daily
pass routes the three sleep dates through `aether_single.py sleep-worker`, using
the exact existing `SingleQueue` and resumable `Uploader`, Aether profile only.
There is no second timer, producer, credential source, queue or direct HTTP path.
`--sleep-only` on that same daily runner resumes only the sleep lane and writes
`sleep-result.json`; it preserves the ordinary daily result and never repeats
fantasy, compilation or Ops stages. Do not run an independent timer for it.

Fixed pilot dates are Nov 9 (Moonlit Guestroom), Nov 13 (Stillwater Sanctuary),
and Nov 16 (Cloudrest Chamber), 2026, Asia/Seoul. Nov 9 permits an immediate
release only within that exact local date and only for the first concept.
The later two dates retain generation before 08:00 and publication before 09:00.
Fantasy Tue/Sat dates remain unchanged. No fourth sleep composition is enabled.
A missed pilot date is not automatically shifted or regenerated.

The old `aether_sleep_plan.py` and pilot JSON remain offline preparation artifacts,
not runtime activation switches. Actual activation requires the explicit existing
runner invocation, the fixed sleep scope, current verified account evidence and
all runtime gates below. A preparation plan is never a paid authorization receipt.

## Default-off adoption boundary

The dedicated runtime gate `AETHER_SLEEP_PILOT_ENABLED` defaults OFF. Only the
exact value `1` permits the sleep lane. No checked-in launchd configuration or
runner invocation sets it. The ordinary daily pass reports the sleep lane disabled
without launching it. Direct worker execution, resumed publication and paid
dispatch also enforce the gate. Offline plans and safe expired-job retirement
remain possible. Enabling the gate is a separate authorized operational change,
not part of integrating this branch; it never replaces cost, review or date gates.

The November 9 KST slot is now expired. It is deliberately unchanged and cannot
be recovered by enabling the gate. Completing all three compositions requires
a separately approved revised schedule; this change does not move or reactivate it.

Before queue admission or generation, the complete remaining pilot must fit
USD 0.50: irreversible prior reservations plus the current verified per-request
upper bound times the number of unreserved compositions. The check is repeated
under the ledger lock immediately before reservation. Future evidence is still
revalidated for every request, and failures/uncertain charges remain reserved.

## Paid generation

`lyria_generate.generate_sleep` pins the separate sleep prompt and passes an
explicit sleep scope through the existing canonical `request_song` transport.
It never calls ordinary fantasy generation with a force flag. The ordinary
single prompt, schedule and spend policy remain unchanged.

`aether_sleep_guard.py` validates private, project/account-bound all-in evidence,
including provider base, tax, currency conversion and mandatory fees; it retains
the original evidence bytes and an attributed field-level review. Hash integrity
and an attestation do not independently authenticate an invoice. Do not fabricate
a receipt or fill uncertain adjustments with zero. Missing proof fails before a
new sleep queue job or paid request is created.

The same global paid-request lock serializes dispatch. A private pilot ledger
reserves the exact concept/job/intent/prompt/proof before its only request. All
reservations count against the total, including failed or uncertain requests.
A dispatch claim and durable intent prevent retry. Recovery validates the same
reservation, scope, generated manifest and source bytes; it never buys again.
Expired evidence may accompany a previously completed source but never authorize
another charge. Unsettled intents remain blockers even when queue status changes.

## Media and real review

Provider MP3/WAV bytes are hash-pinned and retained. A bounded local ffmpeg decode
produces PCM16 48kHz stereo with a separate SHA. Oversized, too-short, too-long,
changed or symlink inputs fail closed. Output creation does not overwrite existing
files. `aether_sleep_render.py` repeats the one source with gentle linear
crossfades to exactly 1800 seconds. This is not 30 minutes of unique music.

Three private exact-job review receipts are required in the existing job folder:

* `sleep-source-review.json`: exact original and decoded source SHA, commercial
  rights, actual listening, sleep suitability, no abrupt swells/prominent beat/voice.
* `sleep-loop-review.json`: exact source and repeated-loop SHA, actual listening
  to seams, endpoint fades and stable dynamics.
* `sleep-video-review.json`: exact source/loop/cover/video SHA, actual final-video
  inspection, suitable static sleep artwork and audiovisual synchronization.

Each contains its stage, series, job ID, accepted boolean, actual reviewer,
review timestamp and authority reference. See `require_review` for the exact field
contract. Never generate these assertions from a successful render. Sleep does
not use the ordinary adventure-density audio score. Cover import still requires
the existing exact-title SHA-bound rights and quality approval. Every upload
revalidates source provenance, reviews and final video integrity. Duplicate owned
video titles and uncertain resumable sessions block a new insert.

Expired unuploaded sleep jobs retire only after unsettled-charge checks, preserving
sources and reservations. Render-only jobs do not gain publication intent through
ordinary reconciliation. An uncertain charge cannot be retired away to permit new
spending. Existing uploaded jobs use the same uploader reconciliation path.

## Verification and deployment boundary

Focused cloud tests cover the aggregate reservation cap, no retries, canonical
transport fences, source identity and hash changes, real MP3 and WAV decode,
real 30-minute PCM rendering, review gates, publication windows, missing billing
without queue insertion, and expired-job handling. Synthetic media proves
mechanics, not musical quality. Full ordinary Aether regression tests and the
actual Mac environment must still be checked on the exact commit before adoption.
No paid request, real track, live queue, cover registration, timer change or upload
was performed during this implementation. The branch is not production deployment.
