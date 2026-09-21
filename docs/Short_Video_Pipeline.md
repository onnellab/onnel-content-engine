# Educational short-video pipeline — phase 1

This is an explicitly approved, isolated extension after the existing completed
article phases in `Phase_Lock.md`; “video phase 1” is not a renaming of article
Phase 1. Teach a useful workflow first. Introduce an app only when it solves the
stated problem. Use honest, optional next-step CTAs, never fabricated screens,
unsupported performance claims, advertisements, or exaggerated outcomes.

ChatGPT or a human authors a brief outside the runtime. The CLI validates it,
durably queues it, and a bounded local Mac/Linux worker renders one MP4.
There is no AI, Codex, paid TTS, provider login, GUI, publishing, Git command,
scheduler installation, or timer activation in the runtime. Existing article
publishing and generated dashboards are unaffected. Upload is a separate phase.

## Setup

Use Python 3.10+ with system IANA timezone data, Node 22+, npm, `ffmpeg` and
`ffprobe`, and a locally installed headless-capable Chromium/Chrome executable.
Install Noto Sans and Noto Sans KR locally for repeatable Korean typography;
otherwise the system sans-serif fallback is used. ONNEL Sans is not used.
No font or browser is downloaded by the worker. Prepare dependencies once:

```sh
npm --prefix video ci
npm --prefix video run typecheck
npm --prefix video test
python3 -B scripts/run_unit_tests.py --pattern test_short_video.py
```

The Python runner uses the repository's `requirements-test.txt`. If the default
npm cache is not writable, use `npm --cache /private/tmp/onnel-video-npm-cache
--prefix video ci` (on Linux, use a writable directory under `/tmp`).
All direct and transitive `@remotion/*` packages and `remotion` are locked to
4.0.526. `npm view` confirmed React/React DOM peers `>=16.8.0`; installed React
and React DOM are both 19.2.0. `npm ls` and a lockfile test check the resolved
versions. There is no root Node package or root toolchain migration.

## Author a brief and prepare assets

Use [`video/brief.schema.json`](../video/brief.schema.json) and
[`video/example.brief.json`](../video/example.brief.json). The example has a
**deliberately missing path**, a placeholder idempotency key and future due date;
it will not enqueue without replacement and is never automatically submitted.
`validate` is the authoritative semantic gate in addition to the JSON Schema.

Required fields: schema_version=1, app_id, topic_id, locale, template,
duration_seconds, due_at, timezone, idempotency_key, test_only, recording,
hook, captions, title, description, cta. `narration` is the only optional field.
Unknown fields, duplicate JSON keys, NaN/Infinity and JSON over 64 KiB fail.
Title and description are upload metadata, not executable code or HTML.
Hook, captions and CTA are plain React text. No caller-authored expressions,
components, CSS, browser URLs or scripts are accepted.

- `app_id` must exist and be content eligible in `data/apps_registry.csv`.
  `topic_id` must exist, be non-archived and reference that app by the existing
  topic registry convention. There is no new product/marketing registry.
- `locale` is `en` or `ko`, from the existing topic validator. The source topic
  may be adapted into either supported language. The caller reviews translation.
- `template` is `quick_demo` or `problem_solution`. Both use 1080×1920 at 30 fps,
  15–30 integer seconds, a central uncropped recording, large short captions,
  restrained fades, ivory/white and lilac/peach/blue accents. Quick demo follows
  steps; problem/solution labels the initial problem before the solution steps.
  The optional CTA appears in the final three seconds.
- `captions` contains 1–12 `{start, end, text}` records, in seconds. They must be
  ordered, nonoverlapping, at least one second long and fit within duration.
  Gaps are allowed. Keep hook, caption and CTA to 1–2 short lines and 44 characters total; each line is
  limited to 44 width units (ASCII=1, other characters=2). Use `\n` deliberately. The renderer measures text, reflows to at most two
  lines and fits it at 40px or larger; it fails rather than cropping oversized copy.
- `due_at` is a seconds-precision ISO timestamp with Z or an explicit offset;
  `timezone` is an installed IANA name such as `UTC` or `Asia/Seoul`. The offset
  must agree at that instant, including DST. Future jobs queue normally, but
  cannot render before due. This is render eligibility, not a promise to publish.
- `recording` is required, even in test mode. Supply an actual reviewed app
  recording for production, `.mp4`, `.mov` or `.webm`. Optional narration is
  local `.wav`, `.mp3` or `.m4a`; recording audio is muted. No speech generation.
  Each asset must cover the full requested duration, be at most 120 seconds and
  256 MiB; recording dimensions must be between 240 and 4096 pixels.
- Asset paths are relative to `--asset-root`; URLs, absolute paths, traversal,
  and symlinks escaping that root are rejected. Do not place credentials or
  personal files in this trusted asset directory. Review screen notifications,
  accounts, filenames, permissions and rights to any included audio beforehand.
- `test_only: true` enables clearly watermarked test footage, including synthetic
  color bars. It **never** becomes upload eligible, even after successful render.
  Production footage authenticity is a human preparation requirement: ffprobe
  verifies media structure, not whether the pixels actually depict your app.

## Commands

All commands return JSON; errors return exit code 2 and JSON on stderr. Global
options precede the subcommand. Replace the example paths with your own files.

```sh
python3 -B scripts/short_video.py --asset-root /private/local-recordings validate /private/brief.json
python3 -B scripts/short_video.py --asset-root /private/local-recordings enqueue /private/brief.json
python3 -B scripts/short_video.py --asset-root /private/local-recordings list
python3 -B scripts/short_video.py --asset-root /private/local-recordings status JOB_ID
python3 -B scripts/short_video.py --asset-root /private/local-recordings worker --once --dry-run
python3 -B scripts/short_video.py --asset-root /private/local-recordings \
  --browser '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' render JOB_ID
python3 -B scripts/short_video.py --asset-root /private/local-recordings \
  --browser /usr/bin/chromium worker --once
```

`validate` reads the brief, registry and assets and computes hashes; it does not
spawn a renderer or mutate queue state. Media probing is an additional required
gate before any render. Dry-run reads atomic queue snapshots only: it does not
create directories/locks, modify state, probe media, spawn processes or access
the network. It reports the earliest due queued candidate, or null. Dry-run is
advisory and does not reserve that candidate.

`render JOB_ID` can retry failed/blocked jobs once their cause is corrected.
An unchanged already-rendered job verifies hashes and MP4 and returns without
rendering again. A changed renderer or output requires a new idempotency key.
The worker processes at most one due queued job; it never auto-retries failures.
No indefinite daemon or timers are supplied.

## Private state and one-worker rule

Default state is `.runtime/short-video/` (ignored, outside generated public
outputs), directory mode 0700. An external private `--state-root` is also
supported; inside this repo only `.runtime/` is allowed. Keep every invocation
for a queue on the **same local filesystem and state root**. NFS/distributed
workers are not supported. Different state roots are independent queues, not a
way to distribute one queue. The operator must run one rendering worker per host.

Queue schema version 1 is `queue.json: {schema_version: 1, jobs: {ID: job}}`.
Each job records the immutable brief, selected asset SHA-256 hashes, a combined
payload hash, idempotency-derived ID, status, eligibility, creation time, error
code and verified result. Snapshots are copied into `jobs/ID/`, never served from
the original root. Enqueue verifies the copied hash, fsyncs files/directories,
and atomically replaces state. Identical keys and payloads are a no-op;
different brief **or asset bytes** under the same key are an error.

An OS advisory `flock` is held across each mutation and the entire render.
Concurrent mutations/renderers fail immediately. Lock files remain intentionally;
the kernel releases ownership on process exit. Do not delete lock files while
any process may be running. Read-only status uses complete atomic snapshots.
Corrupt/unsupported state never gets silently reset. An orphan asset directory
or missing queue file with existing jobs requires operator inspection/recovery
from a trusted backup; no automatic deletion or acceptance of unknown work.

Durable phase-1 transitions:

```text
queued -> rendering -> rendered
                  \-> failed
queued/failed/blocked -> rendering (explicit retry)
interrupted rendering -> blocked (next real worker invocation)
asset integrity failure -> blocked
```

On success, `jobs/ID/` holds `video.mp4`, `preview.png`, `result.json` and input
snapshots. The result includes dimensions, fps, duration, render-input digest,
output SHA-256 hashes and test/upload eligibility. ffprobe verifies H.264,
1080×1920, 30 fps and duration within 0.1 seconds. A failed process or invalid MP4
never marks the queue rendered. A crash between artifact replacement and state
commit leaves an incomplete operation, not a fabricated success.

Render uses programmatic `bundle`, `selectComposition`, `renderMedia` and
`renderStill`, with identical whitelisted inputProps. Only selected media is
staged, not the repository. No host tokens or arbitrary environment variables
are injected into browser props. Render subprocess env is a small allowlist.
Concurrency is 1, parallel encoding is disabled, video decoding threads are 1,
media and offthread caches are each capped at 64 MiB, and webpack disk caching
is disabled. Chromium/process/encoder overhead is additional to these caches.
The renderer has a 15-minute cancellation timer; Python enforces a 16-minute
outer deadline and terminates only its own process group. ffprobe is limited to
60 seconds. Owned browser/temp resources close in finally; Remotion owns and
closes its per-call local servers. There is no killall/pkill or existing browser
session attachment. The local render server requires loopback binding permission.

## Failures and phase 2 boundary

Missing browser, ffprobe, fonts/dependencies, invalid media, timeout, asset
changes or encoding errors stop the render. Diagnose the local prerequisites,
then explicitly retry. After interruption, run the real worker once to mark
abandoned `rendering` jobs blocked, inspect them, then retry by job ID. Never
edit status to claim success or repurpose test footage as production.

Reserved lifecycle states are `uploading`, `uploaded_private`, `scheduled`,
`published`, `blocked`, `failed`, alongside the render states. The Python module
exports the allowed upload transition map and `Queue.upload_candidate(job_id)`
as the integration contract. The latter verifies an existing production render
and returns `{schema_version, job_id, idempotency_key, render_key, test_only,
source, metadata, artifacts}`. Each artifact has a local path and SHA-256;
source contains app/topic IDs, metadata contains title/description/locale/due
time/timezone. It does not change queue state or call any provider;
there is deliberately **no upload command, fake provider, credential reader or
function that claims successful publication** in phase 1.

Phase 2 must consume a verified rendered result and immutable metadata/hash,
reject test_only/invalid artifacts, lock and atomically persist transitions,
obtain separate upload authorization, and record real provider IDs/evidence.
`uploaded_private` requires confirmed private upload, `scheduled` requires
provider-confirmed scheduling, and `published` requires confirmed public state.
Interrupted uploads must be reconciled with the provider before retry to avoid
duplicates; they must never be inferred from an MP4 or dry-run. Title,
description, locale, source IDs and due_at are available for that adapter.

## Verification scope

Focused Python tests use temporary directories, injected clocks/renderers and
mocked probes, and run under the existing offline discovery runner. Node tests
exercise props, staging, identical render inputs, resource cleanup, bounds and
version alignment. Typecheck covers TypeScript and the Node renderer. Real
headless render smoke tests require the local browser/ffmpeg prerequisites and
are separate from offline unit tests. Review previews for text/font rendering
on each target host before producing educational production content.

Remotion references: [server-side rendering](https://www.remotion.dev/docs/ssr)
and [renderMedia](https://www.remotion.dev/docs/renderer/render-media).

### Phase-1 verification recorded 2026-09-21

On macOS with Node 26.7.0 / Python 3.14.7, typecheck, 5 Node tests,
and 22 Python tests under the repository offline runner passed. `git diff --check`
passed. npm peer resolution and the committed lockfile agree on Remotion 4.0.526.
The placeholder example correctly failed validation; empty-queue dry-run created
no state directory. No article publisher or generated dashboard was invoked.

Final headless smoke tests used explicitly test-only color bars (not app screens)
and, for the second template, a local test tone. Both passed the Python queue's
real ffprobe gate and cached-repeat check without a second renderer invocation:

| Template / locale | Encoded duration | Geometry / fps | MP4 size | Render wall time |
| --- | --- | --- | --- | --- |
| quick_demo / ko | 15.000 s | 1080×1920 / 30 | 7,286,702 bytes | 34.52 s |
| problem_solution / en, AAC audio | 30.058667 s | 1080×1920 / 30 | 15,364,443 bytes | 64.91 s |

MP4s, previews, queue state and machine-readable results remain ignored under
`.runtime/video-smoke/`; they are not committed. This is local macOS fixture
proof, not Linux execution, actual-product footage approval, upload validation,
or release/publication proof. System-font availability may change typography
between hosts; review both previews on the intended production worker.
