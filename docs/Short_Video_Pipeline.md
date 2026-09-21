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
  Recording must cover the full requested duration; optional narration may be
  shorter but not longer than the video. Assets are at most 120 seconds and
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
No indefinite daemon or timers are supplied. Phase 2 provides inactive service templates.

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

## Phase 2: authorized local YouTube runtime

Phase 2 extends the same queue; ChatGPT supplies briefs and can execute explicitly
authorized approvals. **Codex is not a runtime dependency.** The engine does not
pull Git, log in, activate timers, generate speech, or invent footage. Use one
persistent Mac/Linux host and one local state root, never simultaneous ephemeral
Actions queues. CI is offline validation only. No credentials or approved real
footage are configured by this milestone; upload readiness remains blocked.

### Account setup and credential boundary

1. In your own Google Cloud project enable YouTube Data API v3 and configure the
   OAuth consent screen. Create an appropriate OAuth desktop client. Complete
   Google's normal account/consent flow once, selecting the intended channel
   (including the correct Brand Account). Do not automate login or bypass 2FA.
2. Use a trusted OAuth client supporting a localhost loopback redirect, random
   `state`, PKCE S256 and offline access to obtain a refresh token. Request only
   `https://www.googleapis.com/auth/youtube.upload` and
   `https://www.googleapis.com/auth/youtube.readonly`. The engine deliberately
   supplies no login browser or token acquisition server. Testing-mode consent
   can cause refresh tokens to expire; use the applicable Google consent/project
   configuration for your intended persistent account.
3. Set `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, and
   **trusted** `YOUTUBE_CHANNEL_ID` in the worker's private environment. Obtain
   the expected channel ID independently from your account settings. The brief
   cannot choose it. Never put values in Git, task prompts, command arguments,
   status files, plist examples or generated/public outputs. Use OS secret
   management/private service environment provisioning; restrict any local
   environment file to 0600 and its directory to 0700. Avoid shell tracing.
4. Run `youtube-check` to list required/missing names without printing values.
   Run `youtube-check --execute` only when network access is authorized. It
   refreshes OAuth and verifies `channels.list(mine=true)` returns exactly one
   channel, matching the trusted expected ID. Ambiguous contexts fail closed. Every upload/reconcile invocation repeats channel verification.

Unverified API projects created after 2020-07-28 can have uploads restricted to
private. A Google project compliance audit may be required to lift this. The
engine reports actual API facts (`forced_private`), not an assumed schedule or
public success. The adapter uses Python stdlib urllib, disables redirects, uses
30-second request timeouts and bounded exponential retries. Only the exact HTTPS
`www.googleapis.com/upload/youtube/v3/videos` resumable path with an upload ID
is accepted; unexpected provider URL changes fail closed.

### Commands and approval

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
approve JOB --made-for-kids false --synthetic-media false --execute
upload JOB --execute
reconcile JOB --execute
worker --once --inbox --upload --execute
status JOB
list
```

`approve`, `upload`, `reconcile` and upload-capable `worker` default to a
non-mutating dry-run without `--execute`. `--dry-run` always overrides
`--execute`: no secret loading, API calls, subprocesses, approvals, lock creation
or queue writes. The safe credential check only inspects environment presence.
`enqueue --dry-run` validates local inputs; `enqueue-dir --dry-run` inventories
JSON files only. A normal enqueue imports assets and does not authorize upload.

Approval is a separate durable command **after render**, binding MP4 SHA-256,
immutable payload and exact metadata/disclosures. A brief never authorizes
publication. Choose both disclosure booleans explicitly; `madeForKids` is not
inferred from the audience, and synthetic media is not inferred from narration.
The title is capped at 100 Unicode characters, not 100 UTF-8 bytes; the
description is capped at 5000 UTF-8 bytes. Educational videos use category ID 27. Angle brackets are rejected in upload metadata.

Private is the default. Public/unlisted need the separate `--approve-publish`
policy choice, e.g. append `--privacy public --approve-publish` to `approve`.
Scheduling requires `--privacy private --publish-at 2026-12-01T12:00:00Z
--approve-publish`. Use a genuinely future UTC time at approval **and execution**;
past timestamps are blocked because Google may publish immediately. Scheduling
is only submitted on a new, never-published insert, never via an update of an
existing video. An authorized ChatGPT session may run these approval commands
under the user's publication policy; there is no forced human check on every
run. The engine never grants itself approval. Render, approve, then invoke the
worker again when a newly rendered job is awaiting approval.

### Persistent state, status and recovery

The same `flock` covers render, approval, upload and reconciliation. Resumable
chunks are at most 1 MiB (256 KiB multiple). Media transfer has a 15-minute
elapsed budget, checked before continuing chunks (an in-flight request retains
its 30-second timeout). Budget exhaustion preserves the resumable session. Before each send the file hash/size
are checked against the approved immutable render. Session URLs exist only in
`jobs/JOB/youtube-session.json`, atomically written with mode 0600 before any
media bytes. They are secrets: never paste/copy them into issues or reports.
Queue status contains no token, session URL, absolute media path or raw API body.
Errors are fixed diagnostic codes. Exit 2 means blocked/failed/reconcile-required
or provider rejection, 130 means interrupted; exit 0 alone does not mean public
publication. Inspect `status`, `error`, `upload.video_id`, and `upload.observed`.

```text
rendered + bound approval -> uploading (intent durable before POST)
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
snapshots, outputs, approval and queue JSON, while the worker is stopped. Encrypt
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
service is enabled. Use only approved footage/audio with documented ownership
or license sources. Review Remotion's [license](https://www.remotion.dev/license)
for your organization; Noto fonts use the SIL Open Font License and should be
installed from their official distribution with its license retained.

### Reusable ChatGPT task prompt

> Read current repository instructions, app/topic registry, `data/video_briefs/`,
> pipeline documentation and the persistent worker's machine-readable status.
> Work only within my existing upload/publication authorization. Create an
> accurate brief that teaches a real workflow using approved local app footage
> and licensed assets; never invent screens, claims, footage availability or
> disclosure answers. If assets, authorization or either disclosure choice are
> missing, report the blocker. Commit the brief to the inbox using the authorized
> GitHub workflow or enqueue it with the local CLI. A separately authorized
> checkout update may be necessary; the engine does not pull. If this run has
> Remote Desktop/CLI access to the persistent host, run readiness, enqueue,
> render, approve the exact rendered hash under my policy, and run the one-shot
> worker. Verify the durable YouTube ID and reconciled processing/privacy status.
> Report pending processing, forced-private, missing credentials or uncertain
> upload honestly. Never retry by creating a new job after an uncertain upload.
> Do not assume Remote Desktop is available in every ChatGPT Tasks run. If no
> supported action reaches the host, leave a durable brief and report execution
> blocked. Do not activate schedules or use Codex as a runtime dependency.

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
Linux service execution or actual-footage approval. Phase-1 test footage remains
non-uploadable. The separate dry-run metadata-path defect was fixed without weakening the
article review gate or editing generated articles; the supervisor verified the
full pre-upload suite (435 tests) after that fix.
