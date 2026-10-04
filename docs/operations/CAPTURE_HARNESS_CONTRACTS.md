# VaultXT and Aligna capture preparation contracts

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
finished immediately, then Flutter must still exit zero and owned resources
must clean up successfully. An end marker followed by a failed test is failure.

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
recording window. The prepared VaultXT contract additionally requires an explicit
disposable-installation opt-in and a cleanup-complete marker; those requirements
must be wired into a future scenario revision only with the matching verified app
source. Aligna retains its four existing defines and `selected` / `preview_ready`
markers. Neither prepared app harness was registered or activated here.

Concretely, the current VaultXT scenario still lacks
`VAULTXT_CAPTURE_DISPOSABLE=true` and ends at `VIDEO_STEP:inspected_unchanged`.
The recorder has no separate completion-marker setting. Before using the new
app harness, the later scenario change must require `VIDEO_STEP:complete` as its
end marker (plus process exit zero), or add and verify a distinct completion
contract. The earlier inspection marker alone must not be treated as proof of
cleanup. This document does not silently make that activation change.

For the current source audit, VaultXT is pinned to
`e2fc95945cf669cba5cf0b4db5bf21b6e23bcd93` in `onnellab/onnellab-text`, subdirectory
`vaultxt`; Aligna is pinned to `ee83b106984c9af28cad24e1dd4f717fe5d0bccb` in
`onnellab/aligna`. Prepared local commit references and validation results are
recorded below when review is complete.

## Local recorder verification

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
  `acabc6b555eccd84cbc54573b9a726589a89b367` in `onnellab/aligna`. Two files:
  the existing integration test and `docs/operations/PREVIEW_CAPTURE_PREPARATION.md`.
  Dart formatter/parser and diff checks passed; independent source review and
  contract verification completed. Runtime `lib/` and package configuration were
  unchanged. Analyzer, Flutter tests, build, device and capture are NOT_RUN.
- VaultXT: local branch `codex/vaultxt-capture-contract`, commit
  `cf86e179afec3fc199392aeb8dca8e4840cf2e49` in `onnellab/onnellab-text`, changes only the existing
  integration test and `vaultxt/docs/VIDEO_CAPTURE_CONTRACT.md`. Independent
  source checks confirmed a 99,696-byte synthetic UTF-8 file with one match at
  byte offset 75,911. Formatter/parser, policy checks and independent source
  review passed. Runtime app and shared engine source were unchanged; analyzer,
  build, native storage behavior, device and recording remain NOT_RUN.

These commits are not installed release changes and no remote publication is
implied. Separate remote-transfer approval and the later execution/capture gates
still apply.
