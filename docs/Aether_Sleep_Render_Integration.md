# Sleep rendering implementation, 2026-11-09

The owner's latest instruction requests one sleep release today and recurring
alternation with fantasy music. This supersedes the earlier unspecified-publication
timing, but does not lift the three-composition / USD 0.50 all-in pilot ceiling,
one request each, zero paid retries, rights checks or single-producer ownership.

## Implemented and tested

`scripts/aether_sleep_render.py` is a callable offline PCM renderer, not a new
producer or uploader. It snapshots and verifies the supplied source SHA, accepts
30–184-second PCM16 sources, and uses independently opened copies of the same
source with linear crossfades, exact 1800-second trim and gentle endpoint fades.
The result is an auditable repeated-source file, not 30 minutes of unique music.
Output publication into the caller's filesystem is atomic and create-only.
All temporary rendering files are scoped to this call and removed on failure.

Actual cloud ffmpeg testing exposed a broken shared asplit/acrossfade approach:
it exhausted input early. The implemented independent-input version passed the
real 30-minute 24kHz mono synthetic PCM test. Ten focused tests passed including
SHA mismatch, snapshot corruption, malformed input, invalid fades, no-overwrite
and a racing destination. Independent review of the corrected implementation
found no remaining blocking issue for the default path.

Synthetic signals establish renderer behavior only, not musical quality or
sleep suitability. Stereo/44.1/48kHz, full repository checks, actual Lyria audio,
audible seams and final video remain unverified. No paid request, real music,
cover, video upload, launchd change or queue mutation was performed by this patch.

## Remaining integration gates

1. Existing single Mac producer must own the operation and locks. Extend its
   exact durable queue contract with explicit sleep source/series markers; do not
   pass sleep music off as an ordinary fantasy single or weaken ordinary guards.
2. Refresh current provider rights/price evidence and verify account-specific
   all-in costs against the pilot's USD 0.50 total. A historical KRW SKU price
   is not a verified tax/FX/mandatory-fee total. Reserve durable intent before each
   of at most three requests; uncertain requests count as unresolved, never retry.
3. Bind generated source, delegated audio/seam review, cover review and final
   video validation to their actual SHA values. PCM success is not those reviews.
4. Use only existing Aether credentials/uploader, reconcile remote state before
   retrying an uncertain upload, then verify the exact channel and public video ID.
5. Record the user's today-release exception independently of normal 09:00
   cutoffs. A possible pilot alternation preserving Tue/Sat fantasy is Mon Nov9
   sleep, Tue Nov10 fantasy, Fri Nov13 sleep, Sat Nov14 fantasy, Mon Nov16 sleep,
   Tue Nov17 fantasy. This is a proposal, not an installed or executed schedule.
   After three sleep sources, stop new paid sleep production pending a new budget.

The old planner intentionally remains preparation-only. This patch does not
flip readiness flags, install a scheduler or assert today's publication occurred.
