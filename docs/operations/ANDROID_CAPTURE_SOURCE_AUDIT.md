# Android capture source audit — 2026-10-04

All five registered Android scenarios have a test target and Flutter project
manifest on their mapped remote `main`. Their configured start/end markers and
Dart environment switches are present in the inspected source. This confirms
remote source availability, **not successful recording or authentic end-to-end
product behavior**. Several harnesses deliberately use fixture or mock services.

| Core-operation assessment | Scenarios | Consequence |
| --- | --- | --- |
| Core result is mocked | Quivra conversion; TagWeaver tag saving; Segra trimming/export/preview playback | Block these paths from factual production feature demonstrations until authentic capture paths are verified. A Saved screen is not proof of the operation. |
| Real operation with controlled sample input, source inspection only | VaultXT file inspection; Aligna filename preview | Potential capture candidates within that narrow scope; device execution and video quality remain unverified. Do not claim real-user data, performance, or completed renaming. |

## Scope and method

Repository ownership comes from `data/app_release_config.csv`, joined by `app_id`
to `data/video_recording_scenarios.json`; no alternate repository was guessed.
The recorder resolves `project_subdir` before `test_target`, so VaultXT was checked
under `vaultxt/` in `onnellab/onnellab-text`.

Using existing `gh` authentication, this audit read each exact
`repos/{owner}/{repo}/branches/main` SHA, then GitHub Contents API resources with
`?ref={that SHA}`. It inspected only registered test files, project manifests, and
small directly related Aligna files needed to trace its defines and actual preview
dependency path. Decoded source
body inspection was capped at 64 KiB per file; every inspected source was below
that cap. No checkout, clone, build, Flutter dependency install, VM, recorder,
render, upload, Mac access, credential change or GitHub write was performed.
An initial shell JSON encoding failure was discarded; the table uses successful
ASCII SHA queries and subsequent SHA-pinned reads only.

## Immutable source observations

| App / mapped repository | Remote main SHA | Resolved target / size | Project manifest |
| --- | --- | --- | --- |
| Quivra — `onnellab/quivra` | `df6c594ccd23b84de809e61a97cfad4aca1dbae8` | `integration_test/store_screenshot_test.dart`, 23,235 bytes | `pubspec.yaml`, 700 bytes, present |
| TagWeaver — `onnellab/tagweaver` | `0d6d6864a68918b4b77a571e617774bb6b1fa6c9` | `integration_test/tagweaver_screenshot_capture_test.dart`, 24,936 bytes | `pubspec.yaml`, 844 bytes, present |
| VaultXT — `onnellab/onnellab-text` | `e2fc95945cf669cba5cf0b4db5bf21b6e23bcd93` | `vaultxt/integration_test/store_promo_capture_test.dart`, 19,162 bytes | `vaultxt/pubspec.yaml`, 1,152 bytes, present |
| Segra — `onnellab/segra` | `735e7abda8f7362a755989166ef4eaa3bf0eb3d2` | `integration_test/segra_store_screenshot_capture_test.dart`, 21,963 bytes | `pubspec.yaml`, 4,878 bytes, present |
| Aligna — `onnellab/aligna` | `ee83b106984c9af28cad24e1dd4f717fe5d0bccb` | `integration_test/aligna_video_flow_test.dart`, 1,573 bytes | `pubspec.yaml`, 4,323 bytes, present |

All five final pinned target/manifest reads succeeded. These SHA values describe
the audit snapshot; they are not promises that future `main` is identical.

### Quivra

[Pinned test](https://github.com/onnellab/quivra/blob/df6c594ccd23b84de809e61a97cfad4aca1dbae8/integration_test/store_screenshot_test.dart#L18)
consumes `QUIVRA_VIDEO_FLOW` at line 18. The configured value is `true`.
`VIDEO_STEP:empty` appears at line 142 and `VIDEO_STEP:saved` at line 152, around
the file-selection and Convert UI interactions.

The same test installs file-picker and transcoder mock handlers. In the
[transcoder handler](https://github.com/onnellab/quivra/blob/df6c594ccd23b84de809e61a97cfad4aca1dbae8/integration_test/store_screenshot_test.dart#L105),
lines 110–125 wait, write four fixed bytes `[0, 1, 2, 3]`, and return `ok: true`.
A recorded Saved screen from this path would demonstrate a controlled UI fixture,
not a successful real media conversion. Do not claim conversion quality, speed,
or valid output from this capture alone.

### TagWeaver

[Pinned test](https://github.com/onnellab/tagweaver/blob/0d6d6864a68918b4b77a571e617774bb6b1fa6c9/integration_test/tagweaver_screenshot_capture_test.dart#L20)
consumes `TAGWEAVER_SKIP_SCREENSHOT` at line 20, `TAGWEAVER_SCREEN` at lines 31–33,
and `TAGWEAVER_LOCALE` at lines 39–41. Configured values are respectively `true`,
`video_flow`, and `en`; lines 90–92 route `video_flow` into `_runVideoFlow`.

Markers are generated dynamically: `_videoHold('library_empty', ...)` at line
285 and `_videoHold('saved', ...)` at line 350 call the `VIDEO_STEP:$name` emitter
at line 354. Both exact configured markers are therefore represented by the source,
even though neither is a single full string literal. The flow takes a
`_ScreenshotTagcoreService` and changes its `showCover`/`showExtraTags` fixture flags.
UI interaction and marker availability do not establish real media-tag writes.

The core substitution is explicit: lines 63–66 configure `_ScreenshotRepository`
and `_ScreenshotTagcoreService` in the application registries.
[`saveBasicTags` at lines 583–589 and `saveTagBundle` at lines 593–603](https://github.com/onnellab/tagweaver/blob/0d6d6864a68918b4b77a571e617774bb6b1fa6c9/integration_test/tagweaver_screenshot_capture_test.dart#L583)
return `_ok(targets.length)` directly. `applyPatch` at lines 607–612 returns
`_ok(1)`. Those implementations do not edit the selected audio files. The observed
Saved state must not be presented as evidence of real tag persistence.

### VaultXT

[Pinned test](https://github.com/onnellab/onnellab-text/blob/e2fc95945cf669cba5cf0b4db5bf21b6e23bcd93/vaultxt/integration_test/store_promo_capture_test.dart#L31)
consumes `VAULTXT_VIDEO_FLOW` at line 31; its configured value is `true`.
`VIDEO_STEP:library` is at line 129 and `VIDEO_STEP:inspected_unchanged` at line
211. Shared-preference fixture setup is visible at line 105. The configured scope
is log inspection; source presence does not establish on-device file fidelity or
capture success. This audit did not execute the test.

This fixture does **not** replace the document repository with a fake: the video
flow constructs `DocumentRepositoryImpl` with a real temporary vault at lines
84–89, calls `createDocument` and `openDocument` at lines 100–104, and injects that
instance through `documentRepositoryProvider` at line 110. It overrides the
reported free-space amount, language preferences, and purchase repository, which
does not demonstrate purchasing. Crucially,
[`File(bundle.ref.path).readAsString()` assertions at lines 200 and 210](https://github.com/onnellab/onnellab-text/blob/e2fc95945cf669cba5cf0b4db5bf21b6e23bcd93/vaultxt/integration_test/store_promo_capture_test.dart#L200)
compare disk contents to the seeded body after inspection. Source structure thus
supports a real-file inspection scenario, without claiming execution success.

### Segra

[Pinned test](https://github.com/onnellab/segra/blob/735e7abda8f7362a755989166ef4eaa3bf0eb3d2/integration_test/segra_store_screenshot_capture_test.dart#L62)
consumes `SEGRA_VIDEO_FLOW` at line 62 with configured value `true`.
`VIDEO_STEP:trim_loaded` is at line 95 and `VIDEO_STEP:saved` at line 112, with
range-selection and preview markers in between. No on-device trim/export or
generated media was verified by this source-only audit.

The native processing path is replaced: `_configureDependencies` creates
`_ScreenshotTrimRepository` at line 240 and injects it as the repository and
load/waveform/play/save use cases at lines 248–267. The fixture writes 256 zero
bytes as its input at line 295.
[`createTrimmedTempFile` at lines 383–388](https://github.com/onnellab/segra/blob/735e7abda8f7362a755989166ef4eaa3bf0eb3d2/integration_test/segra_store_screenshot_capture_test.dart#L383)
returns the input `asset.path` unchanged; `exportToUserLocation` at lines 392–400
returns success without exporting. `playPreview` at lines 407–412 is empty, as are
pause and seek. Therefore this is a simulated trim/preview/save UI flow, not
native trimming or audible selection preview, and requires the same production
capture quarantine as Quivra and TagWeaver.

### Aligna

[Pinned test](https://github.com/onnellab/aligna/blob/ee83b106984c9af28cad24e1dd4f717fe5d0bccb/integration_test/aligna_video_flow_test.dart#L8)
consumes `ALIGNA_VIDEO_FLOW` at line 8 (configured `true`). Its markers are
`VIDEO_STEP:selected` at line 25 and `VIDEO_STEP:preview_ready` at line 36.
It imports the actual application entrypoint and rename workbench screen.

The imported application path consumes `ALIGNA_SCREENSHOT_LOCALE=en` in
[`lib/app_bootstrap.dart`, lines 18–19](https://github.com/onnellab/aligna/blob/ee83b106984c9af28cad24e1dd4f717fe5d0bccb/lib/app_bootstrap.dart#L18).
[`rename_workbench_screen.dart`, lines 37–41](https://github.com/onnellab/aligna/blob/ee83b106984c9af28cad24e1dd4f717fe5d0bccb/lib/features/rename_workbench/presentation/pages/rename_workbench_screen.dart#L37)
consumes `ALIGNA_SCREENSHOT_MODE=true` and `ALIGNA_SCREENSHOT_STAGE=selected`.
That mode seeds three screenshot file entries before the preview flow; the fixture
list begins at line 673. The scenario ends at preview, not Apply: do not portray
this as proof of completed renaming of real user files.

Unlike the three mocked core-result scenarios, the test calls `app.main()` at
line 18, taps the sequence preset at lines 28–30 and waits for computed text
`0001_field_recording (1).mp3` at line 33. The application's
[`app_di.dart`, lines 122–147](https://github.com/onnellab/aligna/blob/ee83b106984c9af28cad24e1dd4f717fe5d0bccb/lib/app_di.dart#L122)
registers the normal controller and `RenameWorkbenchRepositoryImpl`. An old
"Fake implementations for skeleton stage" comment at line 140 is not sufficient
to classify the implementation: the actual
[`RenameWorkbenchRepositoryImpl`, lines 121–172](https://github.com/onnellab/aligna/blob/ee83b106984c9af28cad24e1dd4f717fe5d0bccb/lib/features/rename_workbench/data/repositories/rename_workbench_repository_impl.dart#L121)
computes preview through `_ruleEngine.buildPreviewAsync` at line 162. Its default
engine is `RenameRuleEngine`, constructed at lines 44–49. The
[`RenameWorkbenchController`, lines 308–321](https://github.com/onnellab/aligna/blob/ee83b106984c9af28cad24e1dd4f717fe5d0bccb/lib/features/rename_workbench/application/controllers/rename_workbench_controller.dart#L308)
calls that repository's preview stream. This supports authentic computation of a
preview for sample inputs; it neither verifies disk rename operations nor proves
that the device run will pass.

## Operational consequence

The remote harnesses are not missing. The next approved source-preparation step can
use these exact mappings and SHAs rather than searching or inventing repositories.
This audit does not repair absent/stale N checkouts, materialize worktrees, verify
Android toolchain compatibility, or claim that the configured marker windows yield
usable recordings. The registered repository basename is also significant:
TagWeaver's existing local inventory mentions `tagweaver2`, while the recorder
expects `tagweaver` under its chosen projects root. Confirm the actual runner path
without moving personal worktrees.

Before authentic demo publication, distinguish seeded input/UI fixtures from
mocked core processing, and verify the depicted operation against supported real
behavior. Where a harness fakes the core result (Quivra conversion, TagWeaver tag
saving, and Segra trimming), improve
the capture path or constrain its claims before publication. Local capture trials
still require the resource-owner agreement, private roots, free-space floor and
other gates in [Windows Shorts recovery](WINDOWS_SHORTS_RECOVERY.md). No
`production_verified` or eligibility flag was added or promoted, and no engine
configuration was changed.
