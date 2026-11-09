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
