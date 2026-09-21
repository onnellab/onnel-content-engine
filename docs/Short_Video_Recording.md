# Managed short-video screen recording

## Purpose

The short-video engine reuses **canonical app recordings**. It does not record the
app again for every YouTube Short. A recording is regenerated only when its trusted
scenario/source/toolchain fingerprint changes or the private recording is missing or
corrupt.

The recorder is unattended and fail-closed. It uses an emulator or simulator, never
a physical Android device. Current production automation starts with the TagWeaver
metadata-edit flow; other apps remain blocked until they receive an explicit scenario.

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

## Current scenario

`tagweaver-core-edit-flow` is registered for `APP-0002` / `TOPIC-0008`.

It uses TagWeaver's existing
`integration_test/tagweaver_screenshot_capture_test.dart` with the app's `video_flow`
harness in English. The test drives real TagWeaver widgets with deterministic demo
data. Recording begins at `VIDEO_STEP:library_empty` and the scenario confirms it
reaches `VIDEO_STEP:saved`.

The resulting master recording may be reused by multiple Shorts that accurately teach
the registered metadata-cleanup topic. It must not be reused for an unrelated topic
such as track numbering until that topic is explicitly added to an appropriate
recording scenario.

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
name matches the scenario (`ONNELLAB Video iPhone 17 Pro` for the current TagWeaver
scenario), records with `xcrun simctl io ... recordVideo`, then shuts down only that simulator. An explicitly supplied, already-booted UDID is treated as
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
Choose another supported topic or leave the job blocked until a reviewed scenario is
added to the repository.

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

The final Android production path was exercised end-to-end on the Mac with the
dedicated `ONNELLAB_Video_API36` AVD. The recorder fetched TagWeaver `origin/main`,
built only in a temporary detached checkout, ran the existing English `video_flow`,
recorded from `VIDEO_STEP:library_empty` through `VIDEO_STEP:saved`, normalized and
indexed the MP4, then shut down only its owned emulator. TagWeaver's active working
tree retained its pre-existing Xcode-only edits and gained no recorder/build edits.

Final verified managed asset:

- scenario: `tagweaver-core-edit-flow`;
- app/topic: `APP-0002` / `TOPIC-0008`;
- source commit: `fb335f0c5e7669ac1fbfe0202665963c15ca0145`;
- scenario hash: `1a4463c08f8776530c73e8303a3307df2baffa927b2e0157a16cf59da2d51a8d`;
- fingerprint: `1fed02e838a5403cb6e28823ba51f34c85bbeb348dc906cc8e6dee513189dbc7`;
- resolved lock SHA-256: `836bdbc60d4c59700afecb5a2837f9957f3e84aec219ea6eea465bd772c147bd`;
- output: H.264, 720×1280, 30 fps, 59.533333 seconds, 790,376 bytes;
- MP4 SHA-256: `0e8fc33a4d6852d954ac97fd2659643c7ff2b0fca1bf79ab5c1c7a745214b7ca`;
- second `ensure-topic` returned `cached` without booting the dedicated AVD;
- after completion ADB contained the pre-existing Melivra emulator only; the recorder's
  dedicated AVD was gone and the physical Samsung device was never selected.

The final managed recording was then used as a real input to the existing Remotion
`problem_solution` pipeline. A 20-second production-eligible draft rendered successfully
without upload; render SHA-256 was
`32692e63a8f0a29ffbad5040624ea653b84ad177ed09fa93fe6a30246b7ab13e`. The same job
passed `managed_recording_attestation` and produced the standing automatic YouTube
choices: public, not made for kids, no synthetic-media disclosure, no scheduled
`publishAt`. No YouTube network/upload action was called.

Final local verification also passed **96 focused short-video Python tests**, the
**509-test full offline Python suite**, Remotion/Node **5 tests**, TypeScript typecheck,
and `git diff --check`.

This proves recorder → managed provenance → Remotion → automatic-publication-policy
integration for the registered TagWeaver Android scenario. The common iOS simulator
implementation has a dedicated `ONNELLAB Video iPhone 17 Pro` target but is not yet
production-verified. Quivra, VaultXT, Segra, Aligna, and ClipNest remain fail-closed
until an English deterministic video-flow scenario is registered for their target
topic; existing screenshot-only harnesses are not silently treated as marketing flows.
