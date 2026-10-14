# Public app-detail artwork in the existing release publisher

`publish-ready-app-releases.yml` remains the only content-engine publisher for
this flow. Its existing `workflow_run` and manual triggers are unchanged. There
is no new schedule, store writer, rendering pipeline, paid API, or Codex task.

## Required app evidence

For each current public store release, the publisher clones the app repository's
default branch with complete commit history (`--filter=blob:none` avoids
fetching obsolete historical image bytes while preserving source-commit checks). It finds exactly one tracked
`release/artwork.json` whose slug matches the app, next to that app's
`pubspec.yaml`. Nested apps such as `onnellab-text/vaultxt` are supported.

The shared gate from `onnellab-flutter-template` verifies the tracked candidate,
independent review, exact version/build and latest app source commit, captures,
render inputs, locale/kind/index completeness, sizes and SHA-256 values. It never
renders or approves images in this publication workflow. The marketing version
must also equal an independently observed public store version using the same
`public_store_versions` and `is_store_confirmed` decisions as release readiness.
Upload, console, in-review and failed-public-lookup states are insufficient.
Observations must have a timezone-aware timestamp no more than 24 hours old;
missing, invalid or future timestamps block publication. The shared gate also
binds its own SHA-256 into the reviewed candidate, so a different central gate
version cannot silently approve an old app-bundled gate candidate.

The shared gate's `verify-site` validates a complete current reviewed source
set, then `stage-site` copies the Android store-edited detail gallery, or the
medium-iPhone edited gallery when Android is absent. Selection is uniform across
locales and records its reason; broken/partial/stale Android inputs never silently
fall back. Explicit `site_path` values preserve route names. Featured homepage
slots consume the same receipt-backed gallery with exact hashes and dimensions;
other apps and legacy original files are outside staging scope. No missing candidate, stale review, changed source,
wrong version or invalid image is replaced by an old screenshot fallback.

## States, publication and recovery

1. Stage each eligible app independently. Missing/invalid evidence is recorded
   as `blocked`; independently valid apps may still proceed. Nothing is marked
   published merely because the preflight step exits successfully.
2. The existing homepage commit/push includes its usual sealed Ops dashboard
   plus only the exact verified app gallery and public manifest paths. There is
   no second publisher. The existing homepage Pages workflow does the build and
   deploy; this pipeline does not create another deployment job.
3. The live verifier checks the public manifest against the expected candidate,
   each locale's ordinary canonical app-detail HTML URL (without a cache-busting query) and complete ordered image set, every
   hash-versioned screenshot URL, actual downloaded SHA-256 and PNG dimensions, and HTML image width/height
   attributes matching those same reviewed dimensions.
   It also checks every featured homepage slot for that app and locale against
   the same reviewed index/hash/dimensions; a raw legacy fallback cannot pass.
   It waits up to ten minutes for deployment/CDN propagation. A push alone, a
   successful manifest fetch, or successful HTTP image status is insufficient.
4. The workflow retains `artwork-staging.json` and
   `artwork-deployment-receipt.json` as its existing run's artifact for 30 days.
   Only successfully observed apps get `deployed_verified`. Any blocked or
   unverified app makes the terminal verification step fail visibly. No eligible
   public releases produces an explicit no-op state, not a publication claim.

The checked-in public manifest intentionally remains `staged_not_published`:
checking it in cannot prove it is deployed. The separately retained deployment
receipt supplies that evidence without another site commit or a deploy loop.
`expected_site_commit` names the publisher's commit; verified pages and bytes,
not that field alone, establish the live outcome.

On failure, repair/review/commit the missing evidence in the app project or fix
the existing Pages deployment, then rerun the existing publication workflow. The
publisher does not synthesize review approval or silently publish stale content.
The cross-repository read token uses existing release or Pages credentials; no
new persistent grants are created. A clone access failure stays blocked.

## Homepage cache contract

`src/lib/products.ts` serves screenshots through the existing static app-assets
route. Its `Cache-Control: ... immutable` contract requires a content-dependent
URL. `screenshot-versions.mjs` appends `?v=<full SHA-256>` to gallery URLs while
keeping source filesystem and generated static output paths query-free. The
source bytes, image service boundary and app metadata remain unchanged.
Homepage slots use the receipt when available; apps without a receipt retain
their explicit legacy originals. An invalid receipt or missing requested locale
fails the site build rather than silently displaying another source. Gallery width/height comes from those same cached PNG bytes in the
selected locale; no app-specific size override remains. Unsupported or mixed-size
legacy galleries retain the existing template fallback. The site helper must land before enabling the content-engine verifier.

## Checks

- `python3 -m unittest discover -s tests -p 'test_homepage_release_artwork.py'`
- Homepage: `node --test scripts/screenshot-versions-contract.mjs`
- The app gate's own independent evidence/geometry/capture tests remain required.
- A live receipt is available only after a future authorized release runs and
  successfully deploys. Local fixture tests do not claim production publication.

The existing operational-status completion trigger checks the latest committed
artwork candidate automatically on its next successful run; it is not a local
filesystem watcher. Merely producing uncommitted files or an unreviewed candidate
cannot publish. Store-public observations authorize release status independently
of the selected image platform, and iPhone fallback never creates an Android
launch claim. No new schedule, workflow runner or app-release action is added.

## Read-only runtime access test

The existing `Sync app operational status` workflow accepts
`artwork_read_only: true`. It reuses the already-bound credential in its existing
repository-read step to read the configured app repositories and the public
site/engine. The private shared template is not a runtime dependency. It does not issue new tokens,
change permissions, mutate operational data, stage artwork, or publish. All
mutation steps are skipped. Its run title is `Read-only artwork access probe`,
which the existing publisher explicitly excludes from its workflow-run trigger.
The normal manual workflow behavior remains unchanged. No schedule is enabled
until this runtime check has actually succeeded using the existing credentials.

## Isolated verifier and read-only runtime proof

The publisher no longer reads the private template repository at runtime. It
uses an existing app's vendored bundle only when all 27 files match the
independently reviewed engine allowlist, and the app's root entry point matches
the approved thin shim. The allowlist contains hashes, not template source.
Unknown pins, missing dependencies, extra importable code, bytecode, symlinks or
custom root gates block that app. Papira's distinct custom evidence remains
unsupported until a separately reviewed bridge preserves its extra checks.
There is no fallback to an older bundle or execution of arbitrary app code.

The verified bytes execute with isolated Python inside Linux bubblewrap, with
no network, credentials, host home, engine checkout or inherited environment.
The app is read-only. Only stage-site receives the dedicated website directory,
with its Git metadata hidden. Missing or denied OS isolation fails closed.
The existing public standard-runner jobs install Ubuntu's bubblewrap package;
no new credential, secret binding or permission is introduced.

The existing status workflow's artwork_read_only input reports each repository
read result, including a safe numeric HTTP status on failure, then exercises the
actual sandbox and checks fresh app bundles as data. Unsupported app evidence
is reported separately from successful access and isolation. This probe never
executes app code, commits, publishes, or authorizes the follow-on publisher.
A passed access/isolation probe alone does not prove any artwork was published.

## Artwork-only change checks

The existing status workflow has an opt-in artwork_check_only manual input.
It refreshes store/version evidence locally and stages current reviewed artwork
in a temporary checkout. Only a changed candidate or actual image bytes produces
an engine trigger bound to the exact workflow run ID and run attempt. Timestamp
or JSON-formatting-only changes do not create commits; an unchanged run preserves
any old trigger bytes and skips all later operational mutations. Ordinary manual
status runs retain their previous operational behavior.

The sole existing publisher checks that exact trigger against its workflow_run
source before proceeding. Reruns cannot reuse an earlier attempt's trigger.
The publisher revalidates fresh app evidence rather than trusting the trigger as
an approval. Existing concurrency serialization remains in effect.

No hourly schedule is enabled in this patch. It remains contingent on verified
read-only runtime access and isolation. Coverage is the current public-release
registry and existing website pages, not every template consumer: registering
other apps and resolving custom evidence are separate readiness requirements.

If the fixed public sandbox self-test fails, it reports only allowlisted failure
categories, fixed errno names, bubblewrap version/required-option support and
bounded read-only namespace/AppArmor capability facts. It never prints raw child
output, profile names, host paths, credentials or private implementation code.
The extra version/help reads do not retry the sandbox. Capability values alone
are not proof of which security mechanism caused a failure. No kernel setting,
profile, privilege or isolation option is changed by this diagnostic path.

## Explicit public-fixture Docker trial

The separately approved experiment uses the existing status workflow with
`artwork_read_only=true`, `artwork_docker_trial=true`,
`artwork_check_only=false`, and `deploy_dashboard=false`. The trial input defaults
to false. Invalid combinations fail before checkout or other operations. Both
valid and invalid trial requests use the publisher-excluded read-only run title.
The trial branch clears inherited environment variables and does not call the
private repository access probe, install bubblewrap, or execute any app code.

Only an already-running local Docker daemon with existing access and an
already-loaded enforcing `docker-default` profile is eligible. Missing or
unverifiable prerequisites stop before image pull or container creation. No
profile loading, daemon restart, group/socket permission change, host setting
change, privileged/unconfined container or fallback is permitted.

The public synthetic-canary trial is separate from production verification.
It does not replace bubblewrap, select or publish app artwork, or enable a
schedule. A passed trial establishes only the tested container boundaries;
production adoption requires a separate reviewed change. The existing rootful
Docker daemon is a different trust boundary, even with a nonroot child process.

The chosen official linux/amd64 Python 3.12.15 bookworm image is pinned to
`docker.io/library/python@sha256:edd0b3ec946cc68bd20e39480bd03929016d0fb6254cbf870cd3bc55ea25116d`.
Its config ID is
`sha256:61d53b56a648da09aa966c5cc46a7e751aea2b38d01f33b04456a9f289685be9`.
Raw registry metadata hashes were verified on 2026-10-14; the matching official
[image record](https://github.com/docker-library/repo-info/blob/ac916a0682807597ecd7a991ebf852e366b2571c/repos/python/remote/3.12-bookworm.md)
and [package inventory](https://github.com/docker-library/repo-info/blob/b109cef5939d0a66fe91551f7d663a910a90d0cb/repos/python/local/3.12-bookworm.md)
confirm the immutable image and Git dependency. A digest fixes identity, not a
promise of vulnerability-free software or automatic security updates.


### Standalone AppArmor profile inspection

The Docker trial's `existing_apparmor_policy_unreadable` result does not distinguish
permission denial from a missing kernel file. An explicitly approved standalone
inspection can diagnose this without starting Docker. Dispatch the existing
workflow with `artwork_read_only=true`, `artwork_profile_inspection=true`,
`artwork_docker_trial=false`, `artwork_check_only=false`, and
`deploy_dashboard=false`. Combining the two diagnostics is rejected before checkout.

The fixed public probe uses noninteractive `sudo` only to read
`/sys/kernel/security/apparmor/profiles` and
`/sys/module/apparmor/parameters/enabled`. Its environment is empty except a fixed
PATH and locale. Output contains only fixed status/error categories and the
presence of the unique enforcing `docker-default` profile; no profile listing,
private inputs, credentials, or arbitrary command/path arguments are accepted.
Reads and execution are bounded. Sudo may produce ordinary system audit records.
No profile is loaded, no configuration is changed, and no daemon, image pull, or
container is started. The diagnostic always ends after its report; even a positive
result does not authorize or automatically resume the Docker trial or production.


### Explicit synthetic trial with fresh profile inspection

The standalone inspection is a snapshot of one ephemeral runner and cannot serve
as runtime evidence for a different runner. The separate default-off
`artwork_docker_profile_trial=true` mode combines the approved fixed read-only
inspection and public synthetic Docker trial in the same job. Set
`artwork_read_only=true`, `artwork_docker_trial=false`,
`artwork_profile_inspection=false`, `artwork_check_only=false`, and
`deploy_dashboard=false`. Exactly one diagnostic mode must be selected.

This mode performs a fresh fixed inspection at every existing profile checkpoint;
no previous workflow report is reused. Missing, unreadable, disabled, or
non-enforcing evidence stops the trial. The approved helper may use noninteractive
sudo only to resolve permission-denied reads of the two fixed kernel files.
Docker itself still runs through the existing ordinary daemon access. No profile
loading, security configuration, daemon restart, or production backend change is
allowed. Standalone inspection continues to end after its report. All prior
synthetic-image, environment, mount, namespace, capability and cleanup checks
remain required; this mode is not production adoption or scheduled publication.
