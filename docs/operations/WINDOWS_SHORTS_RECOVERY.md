# Windows Shorts recovery - 2026-10-04

## Authorized scope and observed state

Restore the existing ONNELLAB app Shorts cadence (Monday, Wednesday, Friday at
09:00 Asia/Seoul), rotating released app kinds. This is the ONNELLAB channel
UCXyRedrldRBl9Y35nyWoTLg, not Aether Inn. The existing policy publishes publicly
when a worker is due; it does not reserve future publication with YouTube
publishAt. No new paid model, login, credential or security changes are included.
Mac access is prohibited for this recovery.

Windows N has Node, npm, FFmpeg/ffprobe, Flutter and ADB. The installed source had
native Windows import failures from fcntl, Unix-only process-group termination,
POSIX directory fsync/open flags, and select over subprocess pipes. Its default
YouTube credential source is macOS Keychain. The existing environment credential
adapter is supported, but all four ONNELLAB credential variables were absent
from the inspected N process. No values or credentials were extracted.

N has no discovered Shorts Windows task, WSL cron/user timer, local Codex
Shorts automation or Shorts automation run record. The old Mac scheduler state
is unknown and must not be inferred from repository examples. The September 30
git-status failure mentioned in prior reporting could not be reverified from N.
The repaired supplier/blog pipeline is separate and is not a Shorts scheduler.

## Concurrency and activation boundary

Existing queue file locks and idempotency keys protect one local state root only.
They cannot prevent an old Mac worker with another state root from uploading the
same slot. A shared GitHub compare-and-swap ledger coordinates upgraded writers,
but cannot fence an unmodified or disconnected legacy writer. Therefore activation
requires an authorized owner to verify the old writer is stopped/fenced before
setting the shared control enabled/fencing fields. Do not enable a second schedule
while that fact is unknown. Never mark fencing complete just to pass preflight.

An uncertain upload permanently blocks new slot allocation until its original
provider session/video is reconciled. Neither expiry nor a new machine grants
permission to retry an uncertain upload as a new video. A completed receipt must
match the fixed channel, slot, payload, and a verified specific public video URL.
The ledger belongs on a dedicated state branch, not main, to avoid triggering
unrelated article publication workflows for every claim.

## Recording coverage

Registered scenarios cover Quivra, TagWeaver, VaultXT, Segra, ClipNest,
and Aligna. The follow-up source audit quarantined Quivra, TagWeaver and Segra
because their capture targets simulate core processing. Only VaultXT file
inspection and Aligna naming preview remain Android source candidates; actual
capture is still unverified. See [source evidence](ANDROID_CAPTURE_SOURCE_AUDIT.md). ClipNest is iOS Simulator only. Papira is confirmed iOS-only; native
Windows cannot execute xcrun/iOS Simulator. Melivra is confirmed Android-only.
The inspected Melivra benchmark tests inject synthetic track repositories and
have no production VIDEO_STEP capture markers; do not reuse those as authentic
product recordings. Papira's independent repository/capture harness was not
available in the inspected N project paths. Candidate registrations must remain
explicitly blocked until actual supported capture harnesses and recordings exist.
No unreleased platform link or invented feature may appear in a brief/video.

## Resource ownership

The parent reports that its D: app-verification VM exited after a QEMU exception
and all 49 owned processes were absent. No VM is currently reserved by that run.
Do not stop, reuse, or reconfigure another operator's future VM. Before any Flutter
build, emulator start, or heavy FFmpeg/Remotion render, inspect current RAM, CPU and
disk, record owned processes, and run one heavy task at a time. Coordinate again
if another VM starts. Keep at least 10 GiB free on C:. Runtime outputs belong to dedicated private state/assets, never personal
videos or existing article outputs.

## Remaining operational prerequisites

- Verified legacy-writer fencing / one active scheduling owner.
- An already authorized ONNELLAB YouTube connection on N; adding a new connection
  needs separate authorization and user-managed login. Never transfer Mac secrets.
- Dedicated recording resources and a resource window approved by the VM owner.
- Actual production recording harnesses/assets for missing app/platform coverage.
- Shared state branch/control provisioning and a verified dry-run before enabling
  the existing cadence on N. Code readiness does not mean a schedule is active.

No new Shorts were generated, uploaded or scheduled while these prerequisites
were unverified. The last independently checked public clip is ClipNest
https://www.youtube.com/watch?v=ScIaoTTLmc8 (public oEmbed 200, matching ONNELLAB
title). This is evidence of that video's existence, not a latest-upload receipt
or proof that a recurring task is healthy.

## Safe operator checks

The native Windows worker requires Python **3.13 or newer**; local native
verification uses **3.14**, which is also the portable-worker CI version.
Python only started honoring Windows `mkdir(mode=0o700)` in 3.13, so older
interpreters cannot supply the private-directory creation behavior this worker
requires ([Python `os.mkdir` documentation](https://docs.python.org/3/library/os.html#os.mkdir)).
Preflight blocks older Windows interpreters. The independent read-only ACL
checks remain mandatory; upgrading Python does not repair existing permissions.

Install the pinned runtime requirements into the worker's dedicated Python
environment with `python -m pip install -r requirements-short-video.txt`.
Windows requires the `tzdata` IANA database for `ZoneInfo("Asia/Seoul")` and
other configured IANA timezones; do not replace this with a fixed-offset fallback.
The test requirements include the same runtime dependency so Windows CI exercises
the actual timezone handling. This package setup does not connect YouTube or
activate any schedule.

The scheduled worker defaults to read-only dry-run. Supply dedicated private paths:

```powershell
python -B scripts/short_video_scheduled_worker.py --dry-run --asset-root <private-assets> --state-root <private-state> --projects-root <projects>
```

This command does not read the shared ledger or prove rotation against live history.
Execution additionally requires `heavy_work_authorized` and
`published_history_migration: {verified: true, evidence: "..."}`. Migrate and verify
existing channel publications before activation; the public ClipNest, Segra, VaultXT,
Aligna and older TagWeaver URLs alone are not complete upload receipts.

Windows runtime permission checks inspect existing ACLs without editing them.
Unsafe or uninspectable state/asset/session paths fail closed before upload session
initiation. POSIX mode checks remain enforced. A private local claim token and
whole-worker lock distinguish separate queues even when they share an owner name.

Capture subprocess cleanup terminates only the worker-owned job/process group.
It must not send a serial-based emulator kill that could affect another operator.

## Verification completed before branch publication

- Final full offline Python suite: 805 tests, 90.140 seconds, exit 0; three
  Windows-only cases skipped on WSL.
- Independent native Windows control suite: 49 tests, 5.093 seconds, exit 0;
  one POSIX-only case skipped. The declared tzdata package was installed into a
  temporary target and exposed only to that test process; no global setup changed.
- Actual-data offline publishing dry-run: exit 0, zero network attempts.
- Protected generated/state files: 508 before and after, identical SHA-256 values.
  Existing manual state, schedule, remote receipts and posted URLs were preserved.
- Relative to main 2ea3e6d3, topic data only adds TOPIC-0043 as an idea, mirrored
  in both topic CSVs. It is not a manuscript, recording, upload or publication.
- Independent code review found no remaining code blocker after ACL, process
  ownership, Aether shared-uploader regression and app-specific campaign fixes.

This evidence verifies code behavior with offline fixtures and preserved data.
It does not verify a real recording, render, new upload, active Windows schedule,
legacy-writer fencing or analytics attribution.

Melivra now has a source-only prepared harness on `codex/melivra-android-capture`,
commit `d5ad64330fa8cd91eefc8ea0cb970ef352d475e3`. It uses an owned generated WAV
and actual scanner/repository/native playback. The app policy forbids Flutter/Dart
commands on Windows/Linux, so compilation, device execution and capture remain
NOT_RUN/NOT_CAPTURED. The backlog records this reference and stays ineligible.

## Follow-up quarantine and portability verification

- Final offline suite: 820 tests, 94.627 seconds, exit 0; three Windows-only skips.
- Native Windows suite: 70 tests, 8.790 seconds, exit 0; five POSIX-only skips.
- Actual-data offline dry-run passed with zero network calls. All 594 protected
  files retained identical SHA-256 values; no missing files. Diff checks passed.
- Independent review accepted trusted built-in Windows ACL owners, current-scenario
  checks on reused recordings, and Windows-safe repository/path validation.
- Main a5dac7defcc9d265e656515269110b26abe1b26d passed unit workflow 37180880030,
  actionlint 37180880114 and publishing dry-run 37180880073. Its Windows video
  workflow failed because the private fixture owner was Administrators. The
  follow-up permission fix accepts that already-trusted principal without changing
  ACLs, ownership or credentials; hosted CI must verify this follow-up separately.
- No recording, emulator, render, authentication, upload or schedule activation
  was performed during these checks.
