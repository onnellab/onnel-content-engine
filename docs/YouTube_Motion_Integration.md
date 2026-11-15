# ONNELLAB YouTube motion production — Shorts and long-form

## Scope and safeguards

This integration reuses the existing `video/` Remotion installation and locally
installed FFmpeg. It is **not** a text-to-video generative model and does not
install or run all 18 unrelated animation libraries. Videos are composed from
reviewed text, deterministic shapes, real recordings and optional rights-cleared
narration. Existing scheduled YouTube publishing is not modified by this change.

- **Shorts:** existing scheduled production queue, 1080 × 1920 at 30 fps,
  15–30 seconds. The current `quick_demo` and `problem_solution` templates
  use short, bounded caption, hook and closing entrances. Real app footage stays
  uncropped, unmoved and free of overlaid text covering critical evidence.
  Source, upload and idempotency rules still come from
  [Short_Video_Pipeline.md](Short_Video_Pipeline.md).
- **Educational long-form:** a separate **local draft-only** renderer,
  1920 × 1080 at 30 fps. It supports an opening, explanation, authentic
  demonstration and closing, without taking control of the Shorts queue.
  Audio is optional and must be supplied from a rights-cleared local file.
- **Aether Inn long music videos:** keep the existing FFmpeg/audio-quality and
  licensed-cover workflow; do not force Remotion to re-render 30-minute audio
  loops merely for decorative movement. Other YouTube concepts may reuse the
  long-form renderer after their own source and channel policies are approved.

In both formats: teach first, product second when genuinely relevant, global
English copy, and follow [Motion_Design_Guide.md](Motion_Design_Guide.md).
No fabricated interface, performance claim, ratings, footage, voice, watermark
removal or copyright-uncleared asset. No paid speech API or upload action is
invoked by the new long-form renderer.

## First-time prerequisites

- Node 22+, `npm --prefix video ci`
- `ffmpeg`, `ffprobe` installed locally
- An installed Chrome/Chromium binary and fonts already present on the machine
- Rights-cleared media stored privately **outside Git**
- Sufficient disk and render time for full-resolution video

Use the existing pinned Remotion package versions; do not upgrade the render
toolchain just to enable long-form. Check Remotion's current license for your
organization before production:
https://www.remotion.dev/docs/license/pricing

## Short-form operations

The automated one-shot runner is unchanged. It already uses real, reproducible
device recordings and refuses test/synthetic assets for uploading. To verify
the motion code on its own:

```sh
npm --prefix video run typecheck
node --test video/test/motion.test.mjs video/test/render.test.mjs
python3 -B scripts/short_video.py --asset-root /PRIVATE/video-assets worker --once --dry-run
```

Only run the existing scheduled publishing job when its documented readiness,
recording and YouTube preflight gates succeed. This change does **not** activate
or expand a scheduler, bypass an upload approval, or alter due times.

## Long-form local draft

Start from [example.longform.request.json](../video/example.longform.request.json).
The request is **not** queued or scheduled. It is an operator-owned file with:

- `brief.schema_version = 1`, `locale = "en"`, `test_only` as a real boolean
- `brief.scenes` of 1–16 entries; each 3–90 seconds, total 60–600 seconds
  for production drafts or 3–600 seconds when `test_only = true`
- `kind = opening | explanation | demonstration | closing`
- `heading` (max 70 characters); optional `body` (max 135) or
  `points` (1–3, max 95 characters each), not both
- `demonstration` **requires** a `recording` relative to `asset_root`.
  That real clip must cover the scene duration; it is shown without crop
  or source sound. Record with the dedicated production flow when available.
- Optional `narration` relative to the same private asset root, in WAV,
  MP3 or M4A. The narration must fit inside the total video duration.
- `asset_root` and `browser` are absolute local paths. `output` is an
  absolute **new directory** under an existing parent; existing output
  directories cannot be replaced.

Run on a machine with the approved media and browser:

```sh
npm --prefix video run typecheck
npm --prefix video run render:longform -- /ABSOLUTE/PRIVATE/longform-request.json
```

The output directory contains `video.mp4`, `preview.png` and
`manifest.json`. Remotion creates a bounded H.264 draft; FFmpeg stream-copies
the verified result into a fast-start MP4; ffprobe then verifies 1920×1080,
30 fps, codec, pixel format and duration. Delivery is staged and renamed only
after all checks pass. Selected source assets are copied into a private
temporary directory and SHA-256 checked. Other host files and credentials are
never passed to the browser. Concurrency is one, browser and temporary files
are cleaned in `finally`; only processes started by the renderer are owned.

The long-form `manifest.json` deliberately records
`upload_eligible: false` and `publication_review_required: true` even
for non-test drafts. A separate, documented provider-specific release path
must check content claims, actual playback, source rights, channel identity,
metadata and upload approval before publishing. Do **not** pass this manifest
into the existing Shorts upload queue or treat a successful render as approval.

## Verification

```sh
npm --prefix video run typecheck
node --test video/test/motion.test.mjs video/test/longform.test.mjs video/test/render.test.mjs
```

If the full `npm --prefix video test` fails in
`video/test/dependency-security.test.mjs`, investigate the separately
tracked upstream dependency-security regression rather than concealing it
behind the new renderer's isolated test success. All new unit tests should
be green before a commit. A real bounded TEST ONLY render must be ffprobed
at least once on the intended macOS host before enabling production use.

## Resource ownership

Snapshot pre-existing macOS Chrome/Node/FFmpeg/Flutter/emulator processes
before rendering. Never use `killall` or stop shared workers. New
Remotion-owned browser instances, FFmpeg render subprocesses and temporary
files must close at the end; inspect process status afterward. No simulator
is needed for a text-only test render. Existing AVDs/Simulators should not
be stopped by this integration.
