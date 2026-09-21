# Educational short-video pipeline — phases 1 and 2

This is an explicitly approved, isolated extension after the existing completed
article phases in `Phase_Lock.md`; “video phase 1” is not a renaming of article
Phase 1. Teach a useful workflow first. Introduce an app only when it solves the
stated problem. Use honest, optional next-step CTAs, never fabricated screens,
unsupported performance claims, advertisements, or exaggerated outcomes.

ChatGPT or a human authors a brief outside the runtime. The CLI validates it,
durably queues it, and a bounded local Mac/Linux worker renders one MP4.
There is no AI, Codex, paid TTS, provider login UI, Git command, scheduler
installation or timer activation in the runtime. Explicitly authorized YouTube
upload/reconciliation is supplied by phase 2 below. Existing article publishing
and generated dashboards are unaffected.

## Setup

Use Python 3.10+ with system IANA timezone data, Node 22+, npm, `ffmpeg` and
`ffprobe`, and a locally installed headless-capable Chromium/Chrome executable.
Install Noto Sans locally for repeatable English typography; otherwise the system
sans-serif fallback is used. ONNEL Sans is not used by this automation yet.
No font or browser is downloaded by the worker. Prepare dependencies once:

```sh
npm --prefix video ci
npm --prefix video run typecheck
npm --prefix video test
python3 -B scripts/run_unit_tests.py --pattern 'test_short_video*.py'
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

- `app_id` must be `released` and content eligible in `data/apps_registry.csv`.
  `topic_id` must exist, be non-archived and reference that app by the existing
  topic registry convention. App display name and platform availability are
  snapshotted from that trusted row into the immutable queue payload; caller copy
  cannot override them. There is no new product/marketing registry.
- `locale` is fixed to `en`. This restriction applies only to short-video output;
  app and article localization remain unchanged. A Korean source topic may supply
  facts, but the video copy must be newly written as idiomatic English rather than
  mechanically translated. If the source does not support a claim clearly, block
  the brief instead of guessing or publishing awkward translation.
- `template` is `quick_demo` or `problem_solution`. Both use 1080×1920 at 30 fps,
  15–30 integer seconds, a central uncropped recording, large short captions,
  restrained fades, ivory/white and lilac/peach/blue accents. Quick demo follows
  steps; problem/solution labels the initial problem before the solution steps.
  The optional CTA appears in the final three seconds.
- `captions` contains 1–12 `{start, end, text}` records, in seconds. They must be
  ordered, nonoverlapping, at least one second long and fit within duration.
  Gaps are allowed. Hook, caption and CTA are capped at 80 characters and at most
  two authored lines. The renderer measures actual font width, prefers word-boundary
  wrapping, reflows to at most two lines and fits at 40px or larger; it fails rather
  than cropping oversized copy. Use `\n` only when a deliberate break improves reading.
- `due_at` is a seconds-precision ISO timestamp with Z or an explicit offset;
  `timezone` is an installed IANA name such as `UTC` or `Asia/Seoul`. The offset
  must agree at that instant, including DST. Future jobs queue normally, but
  cannot render before due. This is render eligibility, not a promise to publish.
- `recording` is required, even in test mode. Supply an actual production app
  recording from the dedicated trusted asset source, `.mp4`, `.mov` or `.webm`. Optional narration is
  local `.wav`, `.mp3` or `.m4a`; recording audio is muted. No speech generation.
  Recording must cover the full requested duration; optional narration may be
  shorter but not longer than the video. Assets are at most 120 seconds and
  256 MiB; recording dimensions must be between 240 and 4096 pixels.
- Asset paths are relative to `--asset-root`; URLs, absolute paths, traversal,
  and symlinks escaping that root are rejected. Do not place credentials or
  personal files in this trusted asset directory. Review screen notifications,
  accounts, filenames, permissions and rights to any included audio beforehand.
- `test_only: true` enables clearly watermarked test footage, including synthetic
  color bars. It **never** becomes upload eligible, even after successful render.
  Production footage provenance is an unattended input contract: the task may use
  only the dedicated real-recording asset root. Test/fixture/synthetic/sample-style
  filenames are blocked by the automatic publication policy. ffprobe verifies
  media structure, not semantic authenticity, so uncertainty blocks publication.

## English video-copy guide

Video copy is authored directly in plain global English. Do not translate Korean
line-by-line and then polish it. Preserve the source meaning and verified product
facts, then write the shortest natural English that fits the scene.

- Hook: name one concrete user problem or desired outcome; avoid generic hype.
- Captions: use simple verbs and one action at a time (`Select`, `Preview`, `Save`).
- CTA: optional and low-pressure. Prefer `Try it on your own files.` over sales copy.
- Tone: practical, calm, globally understandable; avoid slang, idioms, keyword stuffing,
  superlatives and translationese such as `It is possible to...` when a direct verb works.
- Claims: never invent speed, quality, privacy, compatibility or safety claims. Use only
  behavior supported by the source topic, app registry/release facts and actual footage.
- Language quality: the scheduled ChatGPT authoring pass rewrites and self-checks the
  English against those sources. No human review gate is required. If meaning or support
  is uncertain, the task must not enqueue the brief; runtime objective violations block.

If an English source topic exists, prefer it as the factual base. A Korean source may be
used when needed, but the resulting script is a fresh English adaptation, not a literal
translation. If meaning is uncertain, leave the job blocked rather than asking a human to approve it.

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
No indefinite daemon or timers are supplied. Phase 2 provides inactive service templates.

## Private state and one-worker rule

Default state is `.runtime/short-video/` (ignored, outside generated public
outputs), directory mode 0700. An external private `--state-root` is also
supported; inside this repo only `.runtime/` is allowed. Keep every invocation
for a queue on the **same local filesystem and state root**. NFS/distributed
workers are not supported. Different state roots are independent queues, not a
way to distribute one queue. The operator must run one rendering worker per host.

Queue schema version 2 is `queue.json: {schema_version: 2, jobs: {ID: job}}`.
Each job records the immutable English brief, selected asset SHA-256 hashes, a trusted
product snapshot (`app_name` + ordered iOS/Android availability) resolved from the
released app registry at enqueue time, a combined payload hash, idempotency-derived
ID, status, eligibility, creation time, error
code and verified result. Snapshots are copied into `jobs/ID/`, never served from
the original root. Enqueue verifies the copied hash, fsyncs files/directories,
and atomically replaces state. Identical keys and payloads are a no-op;
different brief **or asset bytes** under the same key are an error.

An OS advisory `flock` is held across each mutation and the entire render.
Concurrent mutations/renderers fail immediately. Lock files remain intentionally;
the kernel releases ownership on process exit. Do not delete lock files while
any process may be running. Read-only status uses complete atomic snapshots.
Corrupt/unsupported state never gets silently reset. Schema-1 video queues fail closed
after the English-only/product-snapshot migration; enqueue a new reviewed job rather
than silently reinterpreting old state. An orphan asset directory
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
phase 1 itself performs no provider action. Phase 2 below now implements the
upload and reconciliation commands using the same queue.

The phase-2 contract is to consume a verified rendered result and immutable metadata/hash,
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

### Historical pre-English-only phase-1 verification recorded 2026-09-21

These smoke results predate the English-only publishing policy and are retained
only as renderer history; Korean is no longer accepted by current video briefs.

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
proof, not Linux execution, production-footage provenance, upload validation,
or release/publication proof. System-font availability may change typography
between hosts; review both previews on the intended production worker.

## Phase 2: authorized local YouTube runtime

Phase 2 extends the same queue; ChatGPT supplies briefs and the worker creates
automatic fail-closed publication attestations from the repository policy. **Codex is not a runtime dependency.** The engine does not
pull Git, log in, activate timers, generate speech, or invent footage. Use one
persistent Mac/Linux host and one local state root, never simultaneous ephemeral
Actions queues. CI is offline validation only. Missing credentials or production
footage block publication automatically; they do not create a human review step.

### Account setup and credential boundary

The implemented setup path is described in `docs/YouTube_Connection.md`. On the worker
Mac, the dashboard's YouTube panel launches the installed local connection helper.
The public dashboard never imports OAuth credentials or directly calls localhost.

1. Enable YouTube Data API v3 in a Google Cloud project and configure its OAuth audience.
   Create a **Desktop app** OAuth client and keep its downloaded JSON private. Copy the
   expected ONNELLAB channel ID independently from YouTube advanced account settings.
2. On the Mac's local connection page, select that JSON and enter the expected channel ID.
   Complete Google's system-browser sign-in and consent once. The local helper uses a
   random loopback port, state, PKCE S256, offline access, and only youtube.upload plus
   youtube.readonly. It verifies the exact channel before atomically storing a complete
   credential bundle in macOS Keychain. Failed reconnects retain the previous bundle.
3. The worker, uploader and youtube-check share `short_video_credentials.py`. Keychain is
   the default. Missing, locked, denied or corrupt entries block without secret prompts,
   exported environment values or automatic fallback to another credential source.
4. `youtube-check` checks configuration without reading the token payload or using the
   network. `youtube-check --execute` refreshes OAuth and checks the exact stored channel;
   it does not upload a test video. Initial setup consent is separate from video approval.

Use the same Mac, macOS user and Python installation for setup and scheduled execution.
An explicit Linux/environment deployment is opt-in, never a workaround for a failed Mac
Keychain lookup. Do not write credentials to task prompts, Git, reports or shell arguments.

Unverified API projects created after 2020-07-28 can have uploads restricted to
private. A Google project compliance audit may be required to lift this. The
engine reports actual API facts (`forced_private`), not an assumed schedule or
public success. The adapter uses Python stdlib urllib, disables redirects, uses
30-second request timeouts and bounded exponential retries. Only the exact HTTPS
`www.googleapis.com/upload/youtube/v3/videos` resumable path with an upload ID
is accepted; unexpected provider URL changes fail closed.

### Commands and automatic publication policy

All examples use this prefix (global options precede the command):

```sh
python3 -B scripts/short_video.py --asset-root /PRIVATE/assets \
  --state-root /PRIVATE/state --browser /ABSOLUTE/chrome COMMAND
```

Commands replacing `COMMAND`:

```text
readiness
youtube-check
youtube-check --execute
enqueue-dir                         # data/video_briefs, sorted JSON files
enqueue-dir /PRIVATE/inbox --dry-run
worker --once --inbox --dry-run
worker --once --inbox                # import and render one due job
upload JOB --execute                 # low-level recovery/diagnostic path
reconcile JOB --execute
worker --once --inbox --upload --execute
status JOB
list
```

There is **no per-video human approval command in the normal workflow**. The tracked
`data/video_publish_policy.json` is the one-time publication policy. For the current
real-screen, no-narration format it fixes English-only YouTube Shorts, public privacy,
`made_for_kids=false`, `synthetic_media=false`, and fail-closed automatic review.
The worker uses the brief `due_at` only as its execution gate; once a due job passes
all automatic checks it uploads as public immediately. If the Google project forces
private uploads, the queue reports `forced_private` instead of claiming publication.

After a production render the worker automatically binds a durable attestation to the
exact MP4 SHA-256, immutable job payload, exact YouTube metadata, and publication-policy
hash. The existing state key remains named `approval` for compatibility, but its `mode`
is `automatic_fail_closed`; it is not evidence of a human review. A changed render,
payload, metadata, or malformed policy cannot reuse that attestation.

The automatic gate refuses at least: test/ineligible jobs, non-English CJK copy,
fixture/test/synthetic/sample-style recording names, narration under the current
no-narration policy, excessive exclamation, and configured hype/absolute marketing
claims such as `best`, `fastest`, `guaranteed`, `100%`, or `never fails`. These checks
are intentionally conservative and objective; they do not pretend to prove prose
quality. The scheduled ChatGPT authoring pass must ground copy in the source topic,
registry/release facts, and real app footage. Uncertainty means **blocked, not review**.

`upload`, `reconcile`, and upload-capable `worker` default to non-mutating dry-run
without `--execute`. `--dry-run` always overrides `--execute`: no provider mutation,
media upload, or queue write occurs. `enqueue --dry-run` validates local inputs;
`enqueue-dir --dry-run` inventories JSON only.

The current `synthetic_media=false` policy is valid only while unattended production
uses real app screen recordings, deterministic layout graphics, and no narration. If a
future template adds synthetic narration, generated people, altered realistic scenes,
or another disclosure-sensitive format, change the policy/validation first; otherwise
the worker must remain blocked. The title is capped at 100 Unicode characters and the
description at 5000 UTF-8 bytes. Educational videos use YouTube category ID 27.

### Persistent state, status and recovery

The same `flock` covers render, automatic attestation, upload and reconciliation. Resumable
chunks are at most 1 MiB (256 KiB multiple). Media transfer has a 15-minute
elapsed budget, checked before continuing chunks (an in-flight request retains
its 30-second timeout). Budget exhaustion preserves the resumable session. Before each send the file hash/size
are checked against the automatically attested immutable render. Session URLs exist only in
`jobs/JOB/youtube-session.json`, atomically written with mode 0600 before any
media bytes. They are secrets: never paste/copy them into issues or reports.
Queue status contains no token, session URL, absolute media path or raw API body.
Errors are fixed diagnostic codes. Exit 2 means blocked/failed/reconcile-required
or provider rejection, 130 means interrupted; exit 0 alone does not mean public
publication. Inspect `status`, `error`, `upload.video_id`, and `upload.observed`.

```text
rendered + automatic hash-bound attestation -> uploading (intent durable before POST)
 -> accepted (video ID durable) -> processing
 -> uploaded_private | scheduled | published | uploaded_unlisted | forced_private
 -> rejected (processing/upload rejected or failed)
uncertain API/network/storage outcome -> reconcile_required
```

`accepted` means insert acknowledged, not processing complete. `processing`
requires another `reconcile JOB --execute` later. Completion requires
`uploadStatus=processed` and `processingStatus=succeeded`; then actual privacy
and the matching future `publishAt` determine the state. Public is reported only
when observed public. A requested public/scheduled result remaining private is
`forced_private` (possible project restriction; exact cause is not inferred).
The worker reconciles scheduled jobs once their approved publication time is due;
it skips not-yet-due schedules and settled final states. It processes one candidate
per invocation. Provider timestamps with fractional seconds or explicit offsets
are compared as instants, not as raw strings. Explicit reconcile remains available.

After a crash or request failure, run `reconcile JOB --execute` on the same host
and queue. It probes the **same** session with `Content-Range: bytes */TOTAL`.
A 308 offset resumes that session; a completed response saves its video ID.
Lost final ACK therefore cannot trigger a new insert. Once an ID is durable,
only `videos.list` is used. A past schedule can still be observed; no further
media is sent under that stale schedule. A lost initiation ACK, missing/expired
session or unknown completed response remains `reconcile_required`; it never
silently inserts again. Inspect the account manually and recover a consistent
trusted state backup if available. If no unique ID/session can be proven,
leave the job blocked and resolve with an operator/provider. Do not delete its
upload evidence, change its key, enqueue a replacement or guess a video ID.
There is intentionally no automatic reset or manual-ID adoption command.

401: renew the authorized account token; 403: check consent, scopes, channel,
quota/project restrictions; 429/5xx: bounded retries then rerun reconciliation;
`render_integrity`: restore the exact approved bytes from backup. Never re-render
a job with any upload evidence, even if blocked/failed. The worker stops on
config/auth failure and reports it before rendering/uploading further jobs.
SIGTERM/SIGINT unwinds Python cleanup, terminating only its own child process
group. Abrupt kill/power loss leaves durable intent for recovery. An interrupted
render is blocked on the next worker invocation and can be explicitly retried.

Back up the **entire** private queue directory, including session files, input
snapshots, outputs, automatic attestation and queue JSON, while the worker is stopped. Encrypt
and restrict backup access; do not restore only queue.json or run original and
restored hosts concurrently. Local POSIX filesystems only; no NFS lock claims.

### Inbox, manual runner and opt-in services

Committed briefs belong in `data/video_briefs/`. The worker's Git checkout must
be updated separately by an authorized operator/ChatGPT action. The engine does
not auto-pull or update itself. ChatGPT GitHub writes and Remote Desktop CLI can
feed this same inbox/queue; assets must already exist at the local relative paths.
The immutable idempotency key makes repeated inbox imports harmless. Partial
inbox import is durable: fix the invalid brief and retry, without losing earlier
valid imports. Committed JSON must never contain private media or credentials.

`video/runners/run-once.sh` requires `VIDEO_REPO`, `VIDEO_ASSETS`, `VIDEO_STATE`,
`VIDEO_BROWSER` and optionally `VIDEO_PYTHON` in the configured host environment.
It executes one bounded worker and exits; running it via an authorized Remote
Desktop terminal needs no Codex. The `.service.example` and `.plist.example`
files are **inactive templates**, with no timers or automatic startup. Customize
paths/environment privately and validate before an operator explicitly installs:

- Linux: place the customized service in `~/.config/systemd/user/short-video.service`,
  then `systemctl --user daemon-reload` and manually
  `systemctl --user start short-video.service`. No enable command or timer is
  required. The private `EnvironmentFile` includes the VIDEO_* and YOUTUBE_* names.
- macOS: provision the environment securely for the user LaunchAgent without
  committing secrets. Copy the customized plist to `~/Library/LaunchAgents/`,
  then explicitly `launchctl bootstrap gui/$(id -u) PATH_TO_PLIST` and
  `launchctl kickstart gui/$(id -u)/com.onnellab.short-video` for a single run.
  `RunAtLoad` and `KeepAlive` are false. To remove, use the corresponding
  `launchctl bootout`; no service was installed or activated by this milestone.

Local headless rendering can run with the screen locked. The computer must be
powered on, awake, with required files accessible; YouTube needs network access.
A sleeping/offline host does not run jobs. Service environments may have a
narrower PATH than terminals; provide full Python/browser paths and a PATH
containing Node/ffprobe. Verify fonts on that host. Optional local narration may
be shorter than the video, must be positive and no longer than it; no padded
silence is required. Recording still covers the full duration. No paid AI/TTS/API
service is enabled. Use only production footage/audio with documented ownership
or license sources. Review Remotion's [license](https://www.remotion.dev/license)
for your organization; Noto fonts use the SIL Open Font License and should be
installed from their official distribution with its license retained.

### Reusable ChatGPT task prompt

> Read current repository instructions, app/topic registry,
> `data/video_recording_scenarios.json`, `data/video_briefs/`,
> `data/video_publish_policy.json`, the recording/pipeline documentation and the
> persistent worker status. Work only within my standing automatic-publication policy.
> Choose a released/content-eligible app and an English topic that is explicitly covered
> by a managed recording scenario. Run `short_video_record.py ensure-topic APP_ID TOPIC_ID` first.
> It must use
> the isolated `origin/main` checkout and either reuse the matching managed recording or
> create it on an emulator/simulator; never build from uncommitted app work, use a
> physical Android device, iPhone Mirroring, or coordinate-click automation. Use the
> returned relative recording path in the brief. Write fresh idiomatic English from the
> verified topic/app facts and the actual flow; never invent screens or claims. Do not
> request per-video human review. If no scenario covers the topic, source meaning is
> uncertain, recording fails, assets/credentials are missing, or policy compatibility is
> uncertain, leave the job blocked rather than guessing. Enqueue the brief, then—when
> Remote Desktop/CLI is available—run readiness and the one-shot worker with `--upload
> --execute`. Verify the durable YouTube ID and actual processing/privacy state. Report
> pending processing, forced-private, missing credentials or uncertain upload honestly.
> Never create a replacement job after an uncertain upload. If no supported action
> reaches the host, report execution blocked. Do not use Codex as a runtime dependency.

Official contracts: [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert),
[resumable upload protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol),
[video status / publishAt](https://developers.google.com/youtube/v3/docs/videos#status.publishAt),
and [ChatGPT Tasks](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt).
Tasks/app actions may require approval; Remote Desktop availability is not assumed.

### Phase-2 verification boundary

Run `python3 -B scripts/run_unit_tests.py --pattern 'test_short_video*.py'`,
`npm --prefix video run typecheck`, and `npm --prefix video test`.
The isolated `short-video.yml` workflow performs these checks on changed video
paths or manual dispatch, using repository action-version conventions and no
secrets, dispatch shell input, real uploads or service activation. Fake-transport
tests are protocol/state evidence, **not** live OAuth, provider acceptance,
Linux service execution or production-footage provenance. Phase-1 test footage remains
non-uploadable. The separate dry-run metadata-path defect was fixed without weakening the
article review gate or editing generated articles; the supervisor verified the
full pre-upload suite (435 tests) after that fix.

## Supervisor verification — 2026-09-21

Implementation reviewed through code commit `00f2c652` (video publishing: `ead6191a`).
- Full offline Python suite: **471 tests passed** on macOS/Python 3.14.7.
- Focused video suite: **58 tests passed**; Node suite: **5 passed**; TypeScript check passed.
- GitHub isolated short-video checks: success, run `35553666174` (`ead6191a`).
- GitHub offline Python tests: success, run `35553965283` (`00f2c652`).
- GitHub publishing pipeline validation/dry-run: success, run `35553965282` (`00f2c652`).
- GitHub workflow validation: success, run `35553666273` (`ead6191a`).
- Both Python orchestration and direct publication CLI now use the correct isolated metadata root; review thresholds/fingerprint checks were not relaxed.

Historical independent render before the English-only policy: `problem_solution`, Korean, 1080x1920, 30fps,
15 seconds, H.264, **7,311,399 bytes**. Preview visually reviewed; this is a synthetic
TEST ONLY pattern, not app footage. Private job ID: `af1ff959a55715eb83405dfb0bd2a5b7`.
MP4 SHA-256: `09ba73e298c05c1d4b19e70a91228e8f81da93a4797271ee7084c650e7295a35`.
The earlier Korean quick-demo and English problem-solution/AAC smoke checks are
recorded above. No test fixture was upload-eligible or sent to YouTube.

Historical reviewer regressions reproduced and fixed: Unicode 100-character titles, ambiguous
channel refusal before insert, normalized provider timestamps, scheduled-job
reconciliation when due, and resumable transfer time budgets. Every regression
uses an injected fake HTTP transport and runs with sockets blocked.

Host readiness verified Node/npm/ffmpeg/ffprobe/Remotion/Chrome availability;
all four YouTube credential variables were absent from the checked environment,
and no production footage had been registered.
Dry-run/readiness created no runtime state. Owned Codex/render processes exited;
this work started no emulator, mirroring app, service, timer, or ChatGPT scheduled task.
Live OAuth/YouTube acceptance, production-footage provenance, Linux service execution,
and Remote Desktop availability inside a future ChatGPT scheduled run remain
activation checks, not completed verification claims.

## English-only creative verification — 2026-09-21

The short-video contract now accepts only `locale=en`; app/article localization is
unchanged. Queue schema 2 snapshots the released app display name and ordered
iOS/Android availability into the immutable payload so a later registry edit cannot
silently change an already queued render or closing slate. Schema-1 video queues fail
closed rather than being reinterpreted.

Two full Python → Node → Remotion TEST ONLY renders used synthetic color-bar footage
with TagWeaver registry data and English copy. Neither was upload eligible:

| Template | Duration | Geometry / fps / codec | MP4 bytes | SHA-256 |
| --- | ---: | --- | ---: | --- |
| quick_demo | 20.000 s | 1080×1920 / 30 / H.264 | 9,949,733 | `3bdd79797cb4e6226a43cc86e866cfa75f5581bdb7aa0b9570e0283b10efa7af` |
| problem_solution | 20.000 s | 1080×1920 / 30 / H.264 | 9,925,783 | `10e5ce904d6911ee5a176fa5e4250d10fec94b2f4bb7409c913893d1428aa601` |

The new design keeps the app recording dominant, changes problem/solution navigation
from three simultaneous pills to one active stage chip, keeps a quiet ONNELLAB cue,
and reserves the final three seconds for trusted app name + supported platforms +
secondary CTA. English copy may use up to 80 characters, but rendered typography is
measured and must fit at 40px or larger in no more than two lines.

Verification after the English-only migration:
- focused short-video Python tests: **77 passed**;
- full offline Python suite: **490 passed**;
- Remotion/Node tests: **5 passed** and TypeScript typecheck passed;
- GitHub isolated short-video checks: success, run `35556098293`;
- GitHub offline Python tests: success, run `35556098286`;
- GitHub publishing pipeline: success, run `35556098361`.

No production footage, YouTube upload, timer/service activation, emulator, or iPhone
Mirroring was used. Codex implementation was unavailable due its usage limit; the
change was implemented and verified directly. Runtime still has no Codex dependency.
