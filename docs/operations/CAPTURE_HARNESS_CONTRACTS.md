# Capture preparation contracts and host verification

This is local source preparation, not capture approval. No device, application
build, recording, render, upload, credentials or schedule was activated. App
runtime features are outside this change. Existing production scenario flags and
published video records are not promoted or rewritten by this preparation.

## Depicted operation and evidence

| App | Authentic operation to exercise | Evidence required before success | Claims excluded from this scenario |
| --- | --- | --- | --- |
| VaultXT | Open and inspect an owned temporary document through the real document repository and reader | Expected search result, unchanged original bytes and clean editor state; owned-file cleanup checked separately | Purchasing, low-space behavior, user-library migration, or an edit/save operation |
| Aligna | Compute proposed names through the actual workbench repository and rename rule engine | All expected preview rows and no unexpected errors; no Apply or picker invocation | Renaming real files, filesystem collision detection, permissions, or successful export |

Seeded input is not proof of a mocked result. VaultXT must read actual owned file
bytes. Aligna's three sample entries are virtual inputs to real preview
computation; they must never be described as completed changes to user files.
Billing, language and review fixtures are setup seams and do not validate those
features. No capture may imply that an untested native operation succeeded.

## Isolation and teardown

- Test data must be owned temporary data, never a default user library, Downloads
  folder or an arbitrarily selected device installation.
- Preferences and review state must remain in memory. Merely restoring a value
  later does not justify writing an existing user's persistent settings.
- Dispose the UI and repository/controller resources before deleting owned files.
  Restore test-only dependency registrations and check cleanup failures.
- A final marker is not sufficient: test and teardown must finish successfully.
  A failing assertion, native operation, cleanup or process must reject the run.
- Test opt-ins do not prove device ownership. The later operator/recorder must
  select the exact separately authorized disposable device and private roots.

## Recorder acceptance contract

The existing app-test command now requests Flutter's expanded reporter. A marker
matches only its complete trimmed line. The supported transport prefixes are
`flutter:` and `I/flutter (numeric PID):`; ANSI color escapes are removed.
Explanations, arbitrary timestamps, suffixes and strings that merely mention a
marker are not accepted. Actual device-log compatibility remains unverified;
unrecognized framing fails closed.

The configured `max_seconds` is the capture window, measured after the recorder
is ready, independently of the larger test startup/process timeout. The recorder
must remain alive before the end marker. Exceeding the window or observing an
early recorder exit fails the capture. On the end marker the recording is
finished immediately. When a scenario declares a distinct `completion_marker`,
that exact line must arrive after the visual end; early or missing completion
fails even if Flutter exits zero. Flutter must still exit zero and owned
resources must clean up successfully. Neither marker overrides a failed test or
cleanup error. Scenarios without this optional field retain the end-plus-exit
contract. Empty, malformed or start/end-equal completion markers are rejected.

The previous implementation could accept a late end marker after Android's
recording time limit, or marker text inside a diagnostic sentence. Mock tests
reproduced both cases. Regressions now cover those cases, early recorder exit,
end-marker termination, nonzero test exit and cleanup failure.

The existing media-structure checks remain necessary. No new arbitrary duration
tolerance is used to claim that the captured final frame contains the expected
screen. Final-frame content, visible operation, output fidelity and usable timing
still require a real managed capture and inspection before publication.

## Activation boundary

App branches are local preparation until explicitly approved for remote transfer.
Before registering a replacement harness, reconcile its exact target, defines,
markers and watched paths with the content-engine scenario at the verified source
commit. A local source review, formatter pass or mock test must not set
`capture_verified` or establish production footage.

The current configured capture windows are **90 seconds for VaultXT** and
**60 seconds for Aligna**. A two-minute Flutter test budget does not extend either
recording window. The VaultXT scenario now supplies
`VAULTXT_CAPTURE_DISPOSABLE=true`, retains `VIDEO_STEP:inspected_unchanged` as the
visual end, and requires `VIDEO_STEP:complete` after app cleanup. Aligna retains
its four existing defines and `selected` / `preview_ready` markers. No scenario
eligibility flag or schedule was promoted or activated here.

This wiring does not publish the prepared app branch. The managed source
checkout still uses app `origin/main`, never an uncommitted or local-only branch.
An older harness that omits `complete` fails closed. Matching app source must be
reviewed and integrated through the separately authorized app workflow before
capture. The full scenario and recorder hashes participate in cache provenance,
and publication checks compare the current scenario hash; pre-change receipts
cannot prove this new completion contract. Existing receipts are preserved.

For the current source audit, VaultXT is pinned to
`e2fc95945cf669cba5cf0b4db5bf21b6e23bcd93` in `onnellab/onnellab-text`, subdirectory
`vaultxt`; Aligna is pinned to `ee83b106984c9af28cad24e1dd4f717fe5d0bccb` in
`onnellab/aligna`. Prepared local commit references and validation results are
recorded below when review is complete.

## Completion-contract host regressions (2026-10-04)

- Windows and WSL recorder suites: 25 passed on each host, zero failures/skips.
- Independent WSL verification: recorder 25/25, portability 14 passed with two
  Windows-only skips, and core Shorts 23/23; 64 total, 62 passed, two skipped.
- Regressions separate valid post-cleanup completion from truncated/quoted
  output, completion before visual end, nonzero test exit and cleanup failure.
  A complete marker arriving after the visual window does not lengthen the clip;
  the overall test-process deadline still applies.
- Independent stale-receipt check rejected a prior scenario hash with
  `managed_recording_scenario_changed`. Exactly the disposable define and
  completion marker changed in the registry; eligibility and rotation flags
  stayed unchanged. All 594 protected content/history files retained their
  hashes. These are mocked host checks, not device or video evidence.

## Earlier recorder verification

- WSL recorder: 20 total, 20 passed, zero failed/errors/skipped (0.480 seconds).
- WSL portability: 16 total, 14 passed, zero failed/errors, two Windows-only
  skips (2.624 seconds). The skipped cases are the Windows ownership guard and
  Windows iOS preflight rejection.
- Native Windows recorder: 20 total, 20 passed, zero failed/errors/skipped
  (3.005 seconds; implementation-owner run).
- Independent reviewer additionally ran the seven capture-completion regressions.
  Independent verification found no generated content, app data or topic changes.
- These checks use mocked capture processes; they do not launch an app or device,
  render video or establish capture quality. No remote push was performed.

## Prepared app branches

- Aligna: local branch `codex/aligna-preview-capture-prep`, commit
  `cf9b95f13fee9f0726ccb00e93d5c3196113c4e6` in `onnellab/aligna`. Two files:
  the existing integration test and `docs/operations/PREVIEW_CAPTURE_PREPARATION.md`.
  Dart formatter/parser and diff checks passed; independent source review and
  contract verification completed. Runtime `lib/` and package configuration were
  unchanged. Flutter 3.47.6 / Dart 3.13.5 resolved the existing lock unchanged;
  four targeted files analyzed cleanly, 18 rule/preview host tests and one
  import-only compilation probe passed. Native build, integration execution,
  device and capture remain NOT_RUN.
- VaultXT: local branch `codex/vaultxt-capture-contract`, commit
  `21c53802bb5970e104ccf2a833588e5dab1b914c` in `onnellab/onnellab-text`, changes only the existing
  integration test and `vaultxt/docs/VIDEO_CAPTURE_CONTRACT.md`. Independent
  source checks confirmed a 99,696-byte synthetic UTF-8 file with one match at
  byte offset 75,911. Formatter/parser, policy checks and independent source
  review passed. Runtime app, FloMo and shared engine source were unchanged.
  Flutter 3.47.6 / Dart 3.13.5 preserved the lock; two targeted files analyzed
  cleanly, 22 supporting host tests and one import-only compilation probe passed.
  Native build/storage behavior, capture integration, device and recording remain
  NOT_RUN. Neither app's compilation probe invokes the capture entry point.

These commits are not installed release changes and no remote publication is
implied. Separate remote-transfer approval and the later execution/capture gates
still apply.

## Quivra host compilation

Local branch `codex/quivra-native-capture` is at
`d378b10d267905dcc13c89fbc0f899ddaded5e60`. Its prepared Android harness is
`integration_test/quivra_native_video_capture_test.dart`; see the app's
`docs/NATIVE_VIDEO_CAPTURE_PREPARATION.md` for the owned WAV/native conversion
contract. The engine's older mock-transcoder scenario remains quarantined.

Quivra CI requests stable Flutter without a version pin. Official Flutter 3.47.6
/ Dart 3.13.5 passed lock-preserving dependency resolution, targeted analysis of
the harness and temporary import probe, 13 existing host tests and one import
probe. The probe never calls capture `main`; existing use-case tests employ
fake transcoders. These results establish host compilation and selected logic,
not actual codec/channel execution, output-media correctness or capture.

Validation ran under `D:/CodexBuildCache/shorts-capture-20261004/work/quivra`;
the root holds `quivra-pubget.log`, `quivra-analyze.log` and
`quivra-host-tests.log`. All 436 copied tracked files retained their Git blob
hashes. Product code, dependencies and capture source were unchanged in this
verification step. The updated runbook was committed locally only. Native
build, integration execution, device and recording remain NOT_RUN.

## TagWeaver host compilation

The prepared source on `codex/tagweaver-native-capture` is
`a5c2128f0c17e1ef427b2cda61bc38a6432ae7b7`, including
`integration_test/tagweaver_native_video_capture_test.dart` and the original-tone
fixture helper. The local branch now includes the host-validation runbook at
`ccd61382a731ae02441625a6c91590c4acef30ba`. Unlike Quivra,
`.github/workflows/ci.yml` pins Flutter 3.47.2 for
both quality and native-test jobs. Validation therefore used that exact official
Flutter 3.47.2 / Dart 3.13.2 in a separate D SDK directory, without replacing
3.47.6 or changing shared configuration.

Lock-preserving dependency resolution passed. Targeted analysis found no issues
in the capture target, `original_tone.dart` and a temporary import probe; that
single host compilation probe also passed. It references `capture.main` without
calling it. It does not execute native tag reading/writing, reopen saved media,
exercise platform permission/picker behavior or establish video correctness.
The old screenshot-backed engine scenario remains quarantined.

The D validation copy is `work/tagweaver` under
`D:/CodexBuildCache/shorts-capture-20261004`. Logs are in `logs/tagweaver`:
`dependencies-20261004-171406.log`, `analyze-20261004-171434.log` and
`smoke-20261004-171524.log`. Original pubspec/lock, capture target and fixture
bytes were preserved. No product or capture code fix was needed; app remote
push, native build, integration execution, device and recording remain NOT_RUN.

## Melivra: existing local playback candidate

The existing prepared branch `codex/melivra-android-capture`, commit
`d5ad64330fa8cd91eefc8ea0cb970ef352d475e3`, already contains
`integration_test/melivra_video_capture_test.dart`. No replacement harness or new
product feature is needed for the source-level candidate: library selection,
native playback, opening Player, pausing and resuming. This is existing behavior
in `Melivra.md` (lines 17 and 148-152), not a claim of AI processing.

The harness synthesizes an original 40-second 440 Hz mono PCM16 WAV at 16 kHz
(1,280,044 bytes). It uses production DI, SQLite, the platform scanner/metadata
reader and Android native playback. It checks scanned duration, advancing and
paused positions, preserved input bytes and final cleanup. No paid model,
personal recording, downloaded music, user API key, fake Track row or fabricated
network-model result is required. See the app harness lines 56-133 and 151-180
and `docs/ANDROID_VIDEO_CAPTURE_PREPARATION.md` at that commit.

This remains **PREPARED / NOT_RUN / NOT_CAPTURED** with `capture_verified: false`.
The existing engine backlog and scenario eligibility stay unchanged. Required
execution inputs and unresolved conditions are:

- An authorized environment compatible with Melivra `APP_ANCHOR.md` lines 66-87.
  It prohibits every Flutter/Dart command on Windows/Linux; Mac access is outside
  this task. Source inspection is not compilation or playback evidence.
- A separately authorized disposable Android installation and its exact owned
  device serial. Database overrides alone do not isolate all native preferences.
  Do not reset a personal installation or grant broad permissions for the test.
- Defines `MELIVRA_VIDEO_CAPTURE=true` and `MELIVRA_NATIVE_AUDIO_IN_TEST=true`,
  and a compatible integration launcher. `lib/di/container.dart` lines 192-205
  chooses a seed scanner when `FLUTTER_TEST` exists; the harness rejects that
  environment. Launcher compatibility is unverified. Do not remove this guard
  or present seeded behavior as real scanning.
- Focused format/analysis, bounded native execution, all semantic markers plus
  exit zero, actual audio/video inspection and owned-file cleanup evidence.
  None ran in this Windows/WSL preparation.

The scenario does not establish external picker/permission UI, AI transcription
or translation, streaming, purchases or cloud behavior. Repository release
evidence in `data/store_versions.csv` records Android 1.0.5 and iOS `in_review`;
only Android is supported by that stored public-release evidence. This audit did
not perform a fresh store lookup or change either platform's release status.
