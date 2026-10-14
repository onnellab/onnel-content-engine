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

Only the shared gate's `stage-site` operation copies the Android detail gallery
using the explicit `site_path` values. Home hero originals and other apps are
outside its staging scope. No missing candidate, stale review, changed source,
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
source bytes, image service boundary, home originals and app metadata remain
unchanged. Gallery width/height comes from those same cached PNG bytes in the
selected locale; no app-specific size override remains. Unsupported or mixed-size
legacy galleries retain the existing template fallback. The site helper must land before enabling the content-engine verifier.

## Checks

- `python3 -m unittest discover -s tests -p 'test_homepage_release_artwork.py'`
- Homepage: `node --test scripts/screenshot-versions-contract.mjs`
- The app gate's own independent evidence/geometry/capture tests remain required.
- A live receipt is available only after a future authorized release runs and
  successfully deploys. Local fixture tests do not claim production publication.
