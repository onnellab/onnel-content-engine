# Owned-upload inventory recovery

## Incident and scope (2026-11-03)

The durable local result reported `aether_single_remote_inventory_unverified`
at `uploads_ids_invalid_or_duplicate`, after two pages and 50 verified IDs.
That older combined diagnostic cannot establish whether the provider returned
a malformed ID, a within-page duplicate or a cross-page overlap. Do not claim
a confirmed provider root cause or successful publication from this repair.

## Recovery contract

`require_no_owned_title_match` still requires a complete owner-authenticated
inventory, including private and scheduled videos. On malformed or duplicate
upload-page IDs only, it performs one additional READ-ONLY inventory pass:
re-read the owner channel, discard pagination tokens, and start at page one
with 25 results instead of 50. Each pass retains the existing 100-page bound.
No job, paid-generation call, approval, render or upload is retried here.

The second pass must satisfy every original ownership, title, privacy, detail,
pagination and count gate independently. Valid IDs observed in the first pass,
including those in a defective page, must all be observed and detail-verified
in the complete second pass. Never merge partial passes, skip bad rows,
deduplicate an invalid page into success, or treat missing data as absence.
Persistent anomalies retain the stable top-level blocker. Safe diagnostics
distinguish invalid IDs, duplicates within a page and duplicates across pages,
and retain the first failure counters when a second pass fails. They contain
no IDs, titles, request URLs, provider payloads or credential material.

Title collisions and non-pagination failures are not retried by this recovery.
The existing bounded missing-detail re-read remains unchanged. Check the exact
09:00 KST deadline again after inventory verification, before spending on music
and before creating a first upload/approval.

## Execution ownership and verification

The 06:20 Asia/Seoul LaunchAgent `com.onnellab.aether-daily-local` remains the
only unattended local executor. This repair does not alter launchd, dispatch
a workflow, invoke production or mutate durable job/video/approval records.
A reporting task must not start a replacement worker. A repository commit
alone does not prove Mac adoption, a successful live inventory or publication.

Offline regression tests in `tests/test_aether_inventory_restart.py` compile
the actual guard definitions without importing production modules. Fixtures
exercise normal and transient pagination, persistent/malformed IDs, lost IDs
across retries, title collisions in every privacy state, missing details,
ownership/count/token/transport failures and diagnostic privacy. The deadline
checks are also inspected structurally at both production call sites.
Full integration and live production verification remain separate.


## Verified persistent pagination defect and exact recovery (2026-11-04)

During owner-requested interactive repair (not the daily reporting task), the
current guard reproduced `duplicate_across_pages` with both 50- and 25-item
pages. A richer uploads response reported 67 total entries and positions 0..66,
but repeated the same video AND playlist-item identity at different positions:
only 66 distinct videos/items remained. A separate authenticated owner search
found 67 distinct candidates. An exact uploads lookup for the missing candidate
confirmed its membership at position 50 and its current channel/public status.
This identifies the observed API inconsistency, not an explanation of Google's
internal cause. Restarting the same broken pagination was insufficient.

The ordinary strict path and its bounded smaller-page restart remain unchanged.
Only persistent cross-page duplication on BOTH scans can enter the new recovery:

1. Re-read the owner channel, uploads playlist and public count. Require complete
   rich uploads pagination with a stable exact `pageInfo.totalResults`, valid
   entry identity fields and every ordinal present. Limit recovery to 250 items.
2. Use `search.list(forMine=true,type=video)` ONLY to discover candidate IDs.
   Do not use its approximate result count, public-only search, date/order filters,
   or a cached report as evidence of completeness. Every previously observed ID
   must remain present, and candidate cardinality must match the uploads total.
3. Independently query the uploads playlist by EACH exact candidate video ID,
   twice. Require exactly one bound playlist item per candidate; unique video,
   item and position identities; every position 0..total-1; and identical mappings
   on both passes. Missing, conflicting, foreign or changing evidence still HOLDs.
4. Read current title, owner and privacy details for every candidate. A matching
   public/private/unlisted title still blocks. Require the observed public count
   and final channel/uploads total to remain consistent. Check a 120-second
   deadline before and after each provider request; expiry never becomes success.

Failure preserves the original top-level blocker and adds a safe
`exact_recovery_failure` subreason. Success returns only verification method and
counts, never private IDs, titles, provider payloads or credentials. No duplicate
is silently discarded, no partial inventories are merged into success, and no
paid-generation, upload or approval action is performed by this read-only helper.

The actual Mac owner-inventory check completed successfully with 67 verified
videos, 67 covered positions and two identical exact-entry passes (64.38 seconds).
This is live inventory verification, NOT a production/publication receipt.
The requested prior single has an approved cover but no retained generated audio,
no render and no video ID; its stale job remains preserved. Its required private
paid-cost/rights proof is absent. The existing gross $0.08 ceiling, generation
window, original 09:00 schedule and durable job records were not changed, and no
paid request or upload was attempted. Scheduled reporting remains read-only.

Regression verification: 90 tests passed across exact/restart/owned inventory,
single-worker behavior, paid-boundary and cost-policy suites. The older
render-crossing-deadline fixture now advances its mocked clock at actual render
completion instead of assuming a fixed number of clock checks; its no-upload
and no-approval assertions remain intact.

## New-generation input checks before title consumption (2026-11-04)

A separate failure path remained after the uploads-list repair: the daily wrapper
selected an approved title and invoked the single worker before discovering that
the existing Lyria cost/rights evidence was missing. The worker could persist an
unproduced job, which later became stale; the planner then excluded that title
because it was already in the queue. Repeating this consumed approved concepts
without producing audio. This is distinct from a ChatGPT tool-edit rejection and
from a YouTube upload failure.

The daily wrapper now calls the existing local settings, paid-proof and unsettled
intent readers before selecting a new Lyria concept or starting its worker.
A failure reports the original safe reason with `stage=generation_preflight`,
`created_new_job=false`, `generation_attempted=false`, `upload_attempted=false`.
No unknown historical spend is reported as zero. Existing-video reconciliation
and canonical WAV backlog handling precede this check and remain unchanged.
The generator repeats all original checks at dispatch; no limit, authorization,
proof schema, publication deadline, credential handling or launchd owner changed.
No proof is fabricated, no rejected job is revived, and no production is retried.

Validation: 124 focused regressions passed, including missing-proof behavior on
two later slots, actual proof-reader use, no title/worker creation on failure,
original spending/uncertainty blocks and preserved backlog/existing-upload paths.
The read-only Mac input check returned `aether_lyria_cost_proof_missing` without
authentication, a provider request, job creation or publication. Therefore this
patch fixes repeated empty job/title consumption, NOT end-to-end production.
The requested prior single remains unproduced; tool restriction clearance and
successful generation/upload have not been established.

## Public evidence collection repair (2026-11-04 02:02 UTC)

The previous uncommitted rights-source collector used one 2 MiB limit for both
HTML download and evidence content, then collapsed every fetch/size error into
`aether_lyria_provider_terms_fetch_failed`. The actual official preview-terms
HTML is 2,124,814 bytes, although its complete normalized visible text is only
39,955 bytes. This was an ordinary source-collection failure, not evidence that
Google rejected commercial use. It does not explain any host tool-safety denial;
those provider-side reasons remain unavailable.

The restored `scripts/aether_lyria_rights.py collect` accepts a bounded 8 MiB
HTML response, excludes script/style/noscript payloads, and preserves complete
normalized visible text within the existing 2 MiB evidence-file limit. It records
both raw-response and stored-text hashes with exact official URLs. Oversize,
HTTP, transport, encoding and source-validation errors are now distinct.
The old pricing endpoint returned HTTP 301. The collector uses the current
Google `https://cloud.google.com/model-garden/pricing` endpoint directly, and
that exact official source was added to the existing pricing URL allowlist.
Redirects to arbitrary endpoints remain disabled.

Interactive live collection succeeded for model documentation, preview terms,
service terms and pricing. HTML sizes were 435510, 2124814, 1070488 and 3026453;
stored-text sizes were 30658, 39955, 202939 and 106729 bytes respectively.
The source receipt is retained in private `lyria-paid-evidence/public-sources/`.
This is a source bundle, NOT active `proof.json`, a new contract acceptance,
account/billing attestation or paid-generation authorization. It leaves every
existing amount, evidence, time, identity and duplicate-request check unchanged.
Scheduled reporting still must not invoke this maintenance collector or workers.

134 focused regressions passed, including the >2 MiB HTML case, separate text
limits, allowed URLs, real source hashes, preservation of existing proof bytes,
and the unchanged gross-cost rejection using the new official pricing URL.
No charged model request, render, upload, durable-job mutation or schedule change
was performed. End-to-end production remains unverified and blocked by missing
account-specific evidence; do not report this source repair as an uploaded song.
