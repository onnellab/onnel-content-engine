# Sleep pilot safety follow-up, 2026-11-10 KST

Scope: the existing sleep candidate based on 7d4a3a0b. No live deployment,
producer execution, paid generation, upload, timer change or activation occurred.

## Changes

- Sleep runtime is OFF unless AETHER_SLEEP_PILOT_ENABLED is exactly 1.
- Daily orchestration, direct worker execution, resumed work and canonical paid
  dispatch enforce the dedicated gate. Expired unuploaded jobs can still retire
  after unsettled-charge checks while the gate is OFF.
- Before queue admission or generation, prior irreversible reservations plus all
  remaining compositions at the verified current per-request bound must fit USD
  0.50. Reservation repeats the check under the ledger lock.
- Fixed dates are unchanged. November 9 is expired and cannot be recovered by
  enabling the flag. The three-composition goal needs an approved revised schedule.
- No ordinary fantasy schedule, prompt, budget or publication policy changed.

## Verification performed on the Mac

Sequential Python tests used the existing audio-studio-mcp Python 3.11 environment.
No dependency installation occurred. Available PyYAML was 6.0.3 and Pillow was
13.0.0, rather than the repository's Pillow 12.0.0 pin; no real image/media test
was executed in this pass.

1. Focused guard, non-media worker and daily regression: 62 passed in 0.061s.
   The network socket fence recorded zero attempts. The subprocess fence recorded
   zero attempts.
2. Expanded test_aether*.py and test_lyria*.py regression: 406 executed in 0.944s.
   402 passed; four existing compilation tests hit the deliberately strict
   subprocess fence on /bin/cp fixture copies. No child was launched by these
   blocked attempts; network attempts were zero.
3. Those four tests passed in 0.062s under a refined fixture-only subprocess fence.
   Only /bin/cp -p of files smaller than 1 MiB between paths inside a temporary
   directory created by that same test runner was allowed. Fifteen fixture copies
   completed; all other subprocesses remained blocked; network attempts were zero.

Together, all 406 distinct selected non-media tests passed. This is not a claim
that the repository-wide suite or final integrated main commit has been tested.
The four fixture tests were:
- test_asset_sync_never_infers_unapproved_tracks
- test_auto_rejected_audio_remains_unapproved_and_no_manifest_is_published
- test_pending_owner_quality_can_be_auto_checked_without_authorizing_rights
- test_theme_sync_materializes_only_preselected_tracks_and_cover

Three real-ffmpeg tests were intentionally excluded due to the current resource
constraint:
- test_actual_30minute_render_is_not_quality_approval
- test_mp3_decode_pins_original_and_does_not_overwrite
- test_wav_decode_uses_distinct_snapshot_output

The existing Aether launchd plist contained no activation variable and no flag in
its program arguments. The task shell and launchctl global variable were unset.
The loaded Aether service was readable and contained no activation-variable entry.
Only this specific key was inspected; no full environment was disclosed.

## Remaining adoption boundary

The new safeguards address default activation and whole-pilot affordability.
Keep runtime activation OFF. Before live adoption, validate the actual integrated
commit with the remaining regression/media checks when resources permit.
Activation still requires authorization, current real account evidence, approved
artwork, real audio/video review and a valid approved schedule. Synthetic fixtures
and passing tests supply none of those approvals.

## Integrated verification after resources recovered

This later pass supersedes the earlier media-test deferral. Memory pressure
returned to normal (level 1), with 41% reported free memory. No existing Aether
producer or ffmpeg process was running. The candidate was merged without
conflicts with main 1746b29294445461f5c7b1e9770ad487b90055ea, preserving all
intervening unrelated changes. Integrated code commit:
ed370a66f1e21de7b24aff568dad8685ebd091a6.

All 409 tests selected by test_aether*.py and test_lyria*.py passed sequentially
in 3.487 seconds, including the real 30-minute PCM render and MP3/WAV decode
tests previously deferred. No tests in that selection were excluded.

The socket fence recorded zero network attempts. The subprocess fence permitted
only tiny fixture copies and ffmpeg inputs/outputs inside temporary directories
created by the same test runner. It allowed 15 cp and four ffmpeg invocations,
with zero denied subprocess attempts. Child-process polling and a subsequent
process-list check both confirmed no test/ffmpeg processes remained.

This verifies mechanics on synthetic local fixtures, not actual composition
quality, rights, final-video review, account tax/billing evidence or permission to
publish. Runtime remains OFF; no producer was run and no charge or upload occurred.
The past November 9 slot remains unchanged. The complete three-composition goal
still requires a separately approved valid schedule and real evidence/reviews.

The verified code is suitable for dormant integration through the existing
producer path. This is not runtime activation and does not create another producer.

## Main integration and hosted dependency correction

The owner subsequently approved main and existing-Mac-checkout integration.
Both were fast-forwarded to 63e66e5d with runtime still OFF. Its Publishing
Pipeline run 42728267736 succeeded in push-event DRY_RUN mode; actual publication,
deployment and output commits were skipped.

Hosted full-suite run 42728267668 exposed a missing test dependency: all three
Linux/macOS matrix jobs failed only the two new decode tests because ffmpeg was
absent. The workflow now installs ffmpeg through its existing official apt/Homebrew
setup, checks ffmpeg and ffprobe before tests, and retains all offline and
permissions/time-limit protections. Regression tests require this setup.
No production code or runtime activation setting changed in this correction.
