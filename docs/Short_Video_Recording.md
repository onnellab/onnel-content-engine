# Managed short-video screen recording

## Purpose

The short-video engine reuses **canonical app recordings**. It does not record the
app again for every YouTube Short. A recording is regenerated only when its trusted
scenario/source/toolchain fingerprint changes or the private recording is missing or
corrupt.

The recorder is unattended and fail-closed. It uses an emulator or simulator, never
a physical Android device. Every currently released/content-eligible app has one
explicit English production scenario. Topics outside those mappings remain blocked.

## Source isolation

The recorder never builds inside the user's active app working tree.

For a real recording it:

1. fetches `origin/main` in the local repository;
2. resolves the exact remote-main commit;
3. creates a temporary shared, detached Git checkout;
4. runs `flutter pub get` only inside that temporary checkout;
5. fingerprints the resolved private `pubspec.lock`;
6. runs the fixed Flutter integration-test target there;
7. deletes the entire temporary checkout afterward.

Uncommitted work in the active app repository is therefore neither recorded nor
overwritten. The active repository is only used as the local Git object source and
as the place where `origin/main` is refreshed.

## Recording identity and reuse

The final recording fingerprint covers:

- the registered scenario definition;
- platform (`android_emulator` or `ios_simulator`);
- Git tree entries for the scenario's watched app paths;
- the Flutter framework/toolchain version;
- the privately resolved `pubspec.lock` hash;
- the recorder implementation SHA-256, so recorder behavior changes invalidate cache.

The private asset index additionally stores the source commit, scenario hash, output
SHA-256, supported topic IDs and whether the scenario is production-eligible.

A cached recording is reused only when its fingerprint and file hash match and ffprobe
confirms a single H.264 video stream. The auto-publication gate also requires the
brief's recording hash to match the managed recording index and verifies that the
scenario still permits the same app/topic.

Changing unrelated app source does not force a rerecord. Changing watched UI/business
source, the recording scenario, Flutter toolchain, or resolved dependency lock does.

## Current scenarios

| App | Scenario | Topic | Verified capture | Deterministic flow |
| --- | --- | --- | --- | --- |
| Quivra | `quivra-conversion-flow` | `TOPIC-0007` | Android | empty → choose fixture files → convert → saved |
| TagWeaver | `tagweaver-core-edit-flow` | `TOPIC-0008` | Android | library → select demo tracks → edit metadata → save |
| VaultXT | `vaultxt-log-inspection-flow` | `TOPIC-0031` | Android | library → open large log → find error text → close unchanged |
| Segra | `segra-trim-flow` | `TOPIC-0009` | Android | trim editor → select range → preview → save |
| ClipNest | `clipnest-saved-snippet-flow` | `TOPIC-0010` | iOS Simulator | saved snippets → pin one snippet |
| Aligna | `aligna-preview-before-apply` | `TOPIC-0012` | Android | seeded files → sequence preset → preview renamed files |

The flows use semantic Flutter widget interactions and repository-owned deterministic
fixtures. They do not use screen coordinates, fabricate production UI, or bypass the
app's presentation layer. Quivra and Segra extend existing store-capture integration
harnesses; VaultXT extends its store-promo harness; Aligna and ClipNest use narrow
integration-test-only flows.

Each master recording may be reused by multiple Shorts only when the Short accurately
teaches the scenario's registered topic. A scenario cannot silently stand in for an
unregistered topic. TagWeaver track numbering, for example, remains blocked until a
flow explicitly covers that topic.

VaultXT lives in the `onnellab-text` monorepo. Its scenario uses
`project_subdir=vaultxt`; source hashing covers both VaultXT and the shared
`packages/onnel_text_engine` paths before the isolated project is built.

## Device ownership

### Android

Without an explicit serial, the recorder starts the scenario's dedicated AVD on a
free emulator port with no window/audio/snapshot loading or saving. It records through Android `screenrecord` at a fixed 720×1280 capture size into `/data/local/tmp`, pulls the
file, removes the remote temporary file, terminates only the
emulator process it started, and waits for that device to disappear from ADB.

A serial supplied through `ONNELLAB_VIDEO_ANDROID_SERIAL` or `--android-serial` must
be an `emulator-*` serial. Physical Android serials are rejected. An explicitly
provided existing emulator is never shut down by the recorder.

If the scenario's dedicated AVD is already running without explicit authorization,
the recorder blocks rather than taking control of another job's emulator.

### iOS

Without an explicit UDID, the recorder boots the one shutdown dedicated simulator whose
name matches the scenario (`ONNELLAB Video iPhone 17 Pro` for the current portfolio),
records with `xcrun simctl io ... recordVideo`, then shuts down only that simulator. An explicitly supplied, already-booted UDID is treated as
externally owned and is not shut down.

Ambiguous/missing simulators block the run. The recorder never uses iPhone Mirroring.

## Output

Use a private asset root outside Git. Example:

```text
/PRIVATE/video-assets/
  recordings/
    index.json
    app-0002/
      tagweaver-core-edit-flow/
        <fingerprint>.mp4
```

The MP4 is normalized to H.264, yuv420p, 30 fps, no audio. The file and index remain
private runtime assets and are never committed.

A canonical flow may be shorter than a 15-second Short. The renderer may hold the
recording's final verified frame only when the master is at least 3 seconds long and
the resulting tail hold is at most 10 seconds. It never loops fake interaction. Longer
Shorts must use a sufficiently long master rather than stretching the tail indefinitely.

## Commands

List registered scenarios:

```sh
python3 -B scripts/short_video_record.py \
  --asset-root /PRIVATE/video-assets list
```

Plan without booting a device or writing recording state:

```sh
python3 -B scripts/short_video_record.py \
  --asset-root /PRIVATE/video-assets \
  --projects-root ~/Projects \
  ensure tagweaver-core-edit-flow \
  --platform android_emulator \
  --dry-run
```

Create or reuse the managed recording by app/topic (preferred for automation):

```sh
python3 -B scripts/short_video_record.py \
  --asset-root /PRIVATE/video-assets \
  --projects-root ~/Projects \
  ensure-topic APP-0002 TOPIC-0008 \
  --platform android_emulator
```

`ensure-topic` fails when no production scenario exists or when more than one scenario
claims the same app/topic/platform. `ensure SCENARIO_ID` remains available for direct
diagnostics.

Inspect managed recordings:

```sh
python3 -B scripts/short_video_record.py \
  --asset-root /PRIVATE/video-assets status
```

`ONNELLAB_PROJECTS_ROOT` may replace `--projects-root`.

## Scheduled ChatGPT flow

For each due video, the scheduled task should:

1. choose a released/content-eligible app and supported English topic;
2. call `short_video_record.py ensure-topic APP_ID TOPIC_ID`; the recorder selects the
   one registered production scenario that explicitly covers that app/topic;
3. use the returned private relative `path` as the brief's `recording`;
4. write concise, grounded English copy;
5. enqueue the brief;
6. run the existing one-shot render/upload worker;
7. report success, provider processing, or `blocked` without requesting human review.

If no scenario covers the chosen topic, do not improvise UI automation or coordinates.
Choose another supported topic or leave the job blocked until a repository-verified
scenario is added.

## Adding another app

Add automation only when the app already has a deterministic Flutter integration test
or an equally bounded repository-owned UI harness. Prefer semantic widget actions and
stable test fixtures over coordinate taps.

A new scenario must specify:

- app and allowed topic IDs;
- repository-relative test target;
- start/end log markers;
- English-only Dart defines;
- watched source paths;
- supported emulator/simulator platforms;
- dedicated device identity;
- whether the scenario is production-eligible.

Do not add generic arbitrary command execution to the scenario schema. The recorder
supports only the fixed `flutter_integration_test` runner. This keeps an authored
brief from becoming a way to execute shell commands on the Mac.

## Failure behavior

Missing repositories/tools/devices, stale or invalid scenario data, failed Flutter
tests, missing step markers, media verification failure, concurrent recording, or
unexpected provider/device state all fail closed. Partial recordings are not indexed
and therefore cannot pass automatic publication.

The recorder may create build caches only inside its temporary checkout and normal
Flutter/Gradle global caches. It must not commit, push, reset or rewrite an app's
active working tree.


## Verification recorded 2026-09-21

The portfolio flows were exercised through the actual managed recorder, not merely
validated as JSON. All source builds came from fetched `origin/main` commits in
temporary detached checkouts. No active app working tree was used as a build source.

| App | Platform | Source commit | Duration | Geometry | MP4 SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| Quivra | Android emulator | `d4b77585753bf426c4a2695905e2f8a8db283fbd` | 6.733333 s | 720×1280 @ 30 | `8d055788946de8b82fc22dbcd2ac644ff117b971729ef076a932c2c048051b3b` |
| VaultXT | Android emulator | `49be30d2102a3a436886dbfa9e732b7181b52471` | 9.100000 s | 720×1280 @ 30 | `26a50a4399fb209edcde0ce2119b64fa0f30f269b5f36bbec26a265b002ca04c` |
| Segra | Android emulator | `9ac4c7be55ba48efb985c30120e9c2671988f2e0` | 11.500000 s | 720×1280 @ 30 | `2eba498064088cc14cf0e5ac2e8ac510febe330693ea131d52afd084f568f75a` |
| ClipNest | iOS Simulator | `33c5391216d1514e7b01c03ac20a8baaf41a8623` | 6.533333 s | 1206×2622 @ 30 | `c6bd25e50b7d18dd909f477a65d892b3dc2889ce3f40fcf04d3038a0e291bb3e` |
| Aligna | Android emulator | `b2584b762fbc268509f55ba7369e065a6fd278f6` | 6.266667 s | 720×1280 @ 30 | `c18bb621079089024c0c481e37eb366b2ba66d0758a0cffef9f21051198f78ec` |

The earlier TagWeaver proof remains valid for `tagweaver-core-edit-flow`
(`APP-0002` / `TOPIC-0008`): H.264 720×1280 @ 30 fps, 59.533333 seconds,
SHA-256 `0e8fc33a4d6852d954ac97fd2659643c7ff2b0fca1bf79ab5c1c7a745214b7ca`.

After each new recording, a second `ensure-topic` returned `cached`. Those cache checks
completed without booting the dedicated recorder devices. `ffprobe` verified every
new managed asset as a single H.264 stream at 30 fps.

Important root-cause fixes discovered by real runs are preserved in the app repos:
Quivra waits for and verifies its saved conversion state; Segra paces the real trim
workflow; Aligna does not require release signing for debug integration builds and
paces the preview; ClipNest's keyboard extension inherits Flutter build-version
settings so the simulator can install it; VaultXT submits large-file search through
the active `EditableText` client and closes the search sheet deterministically.

The physical Samsung Android device was never selected. After verification, the
dedicated recorder devices were shut down and recorder-owned screen-recording
processes were absent.

The shortest portfolio master (Aligna, 6.266667 seconds) and the Quivra master were
also exercised through a 15-second Remotion render using the bounded final-frame hold.
The Quivra TEST ONLY proof produced a 1080×1920, 30 fps, 15-second Short without looping
or fabricating additional app interaction.

These recordings prove deterministic capture flows. They do not authorize unsupported
marketing claims, and no YouTube upload was performed during this registration work.

### Portfolio-to-Shorts proof after registration

The five newly registered managed recordings were each enqueued as a real
production-eligible English brief and rendered through Remotion at 1080×1920,
30 fps, 15 seconds. Short canonical recordings used only the bounded final-frame
hold described above; no interaction was looped or fabricated.

| App | 15-second render SHA-256 | Automatic policy |
| --- | --- | --- |
| Quivra | `1c71d88f49a2ab2f4ec2ce91ec2373df496f64aabd81035ff074faa4a4f18a69` | pass |
| VaultXT | `4049134579d433e37cbbd94f86621a22d0bb474c06459331136b30a0ea476039` | pass |
| Segra | `f51d091704bb265f58ba2bfc2752dc0b7f5528c20cd5cad61c9cabd6efdd4db9` | pass |
| ClipNest | `5deb03a55ef20f520bff01a270812c9ad3619f80671f547ed3d67a8b0eef3566` | pass |
| Aligna | `313ee14ddfbcb00b40ec3401c014dc37152b6cc9568d55d3259ee0b0aa0bc72e` | pass |

For every rendered job, `automatic_choices` accepted the managed provenance and
returned the standing policy values: public, `made_for_kids=false`,
`synthetic_media=false`, no `publishAt`, and `publish_approved=true`. This was a
local policy verification only; no YouTube upload was issued.

Final regression verification after the portfolio registration: **98** focused
short-video Python tests passed, **511** full offline Python tests passed,
Remotion/Node **5** tests passed, TypeScript typecheck passed, and `git diff --check`
was clean.
