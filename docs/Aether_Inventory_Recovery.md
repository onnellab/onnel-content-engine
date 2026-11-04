# Owned-upload inventory recovery

## Current resolution — 2026-11-04

The current policy is `docs/Aether_Inn_Lyria.md`, not the historical all-in
proof-file wording below. The owner requested correcting the internally added
requirements. Runtime now validates the original one-candidate Lyria-only
USD 0.08 **provider-base** budget against freshly collected official price and
commercial-use documents. Account taxes/FX/final invoices remain explicitly
unverified, not zero. No per-song copyright certificate or manually authored
account `proof.json` is required. Original evidence and job records are retained.

The collector atomically indexes validated public sources as `current.json`.
The existing LaunchAgent refreshes these on an eligible new-single slot before
choosing a title; the paid adapter rechecks the same project-bound receipt/hash
and source bytes before dispatch. Changed price/terms, missing or expired sources,
wrong model/count, uncertain earlier charges, duplicate uploads and expired
production/publication windows still block. No platform/tool safety setting,
authentication source, schedule or durable job/video ID was changed.

Live Mac verification using official sources checked at 2026-11-04T02:44:47Z
returned `inputs_verified` and `provider_base_price_usd=0.08`, with
`gross_cost_verified=false` and `final_billed_cost_usd=null`. No paid model
request, render or upload was executed during this maintenance. The original
November 3 single is still unproduced; this is a verified prerequisite/policy
repair, not a retroactive publication receipt. No stale-slot recovery was run.

Validation: 138 focused Aether/source/intent/upload regressions plus 16 Lyria
adapter/configuration regressions passed (154 total). Tests preserve one-request
intent semantics and exercise exact model/currency/unit parsing, price increases,
changed sources, project binding, source-refresh failure and crossing 08:00 while
refreshing, while leaving existing uploads and canonical WAVs independent.

The dated sections below are historical incident evidence. Their former missing
manual-proof blocker is superseded, not an instruction to reintroduce it.

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

## Actual requested manual production attempt — 2026-11-04 06:11 UTC

The owner again explicitly requested completion of the original missed song.
The implemented manual-release path was committed as `f30465fd`, then its
immutable request was recorded for existing job `1f5cf414734a3a362b4db5cc`.
The canonical worker was executed once. Unlike the earlier preparation-only
sessions, a real Lyria POST was entered at `2026-11-04T06:11:34.587187+00:00`.
Run directory: `20261104T061134Z-the-pass-beyond-the-racing-plains`.

It stopped with `lyria_audio_missing` while parsing the received provider
response. No candidate, render, upload session or video ID was created. The
existing manifest remains `request_started`, `dispatch_started=true`; charge
outcome is unverified and must not be represented as zero. No second generation
request was sent, and neither the manifest nor one-use claim was reset.

The previous adapter did not persist stateless response bytes before parsing.
Consequently this attempt's original response is not available locally; its
exact payload-shape/content cause cannot be established retrospectively. A
read-only Interactions list returned no retained records, and a bounded read of
Cloud Logging for this project's request interval returned no entries, including
an unfiltered-service recheck. These empty reads do not prove non-billing.

The adapter now fsyncs the exact response to private `provider-response.json`
before parsing, records its hash/length in the existing intent, and preserves
the original uncertain-request restriction on parse failure. Two new fixtures
verify successful capture and malformed/missing-audio capture with no repayment;
167 focused tests pass. This fixes loss of future response evidence, not the
already-discarded response or the present publication failure.

The requested song is still NOT published. A further model request would be a
new potentially charged attempt, not a no-cost resume. Keep the original record
and obtain explicit additional-attempt authorization rather than silently
clearing it. New generation remains held by the existing unsettled-intent gate;
known-video reconciliation is separate. The daily LaunchAgent schedule and its
historical daily result were not changed by this interactive attempt.

## Explicit additional-attempt approval — 2026-11-04

After being told the first actual request had unknown billing and no retained
output, the owner replied `승인` to exactly one additional generation at USD
0.08 provider base, cumulative possible base spend USD 0.16 (tax/FX separate).
`aether_additional_attempt.py` records that instruction for the existing song
and exact first manifest hash. It does not overwrite or reclassify the original
request_started manifest as free, failed-before-send, generated or refunded.

The existing unsettled-intent reader and source recovery may recognize only this
exact owner-acknowledged prior request. Every other ambiguous attempt still holds.
The additional generation is claimed once under the canonical paid-request lock;
the same job, original manual-publication receipt and canonical worker are reused.
A third request is disallowed, and the new response is retained before parsing.
Five extra fixtures plus existing affected suites passed (87 tests in this pass).
This records authorization and code validation, not proof of a successful song.

### Additional attempt outcome (observed, not successful publication)

The approved second POST was dispatched at `2026-11-04T06:33:31.927204+00:00`
(15:33:31 KST) through the same canonical manual worker. It again ended with
`lyria_audio_missing`. This time the complete response was saved before parsing:
141 bytes, received `2026-11-04T06:34:05.043518+00:00`, SHA-256
`7ab6d16fe633f2e81e7583ec234e6eb411d8460a3986aeb8bca350d875907013`.
Its entire JSON was:

```json
{"status":"completed","created":"2026-11-04T06:34:04Z","updated":"2026-11-04T06:34:04Z","object":"interaction","model":"lyria-3-pro-preview"}
```

It contains no `steps`, `outputs`, audio, text, interaction ID, usage or diagnostic
error. There are no hidden audio bytes for a parser change to recover. Current
Google music documentation's sample includes model_output/audio content; it does
not establish why this particular response omitted content. Do not invent a
provider root cause, refund or successful charge. The first response remains
unavailable, so this observation cannot prove the first payload was identical.

Exactly two requests are now recorded for the song, one initial and one explicitly
approved additional attempt. Potential combined provider-base cost is USD 0.16,
with actual billing/tax/FX unverified. The first manifest's exact original hash is
unchanged. The second response, manifest and single-use claims remain private and
intact; no third POST was sent. No audio, render, upload session or video ID exists.
The new unsettled second request still blocks automatic new generation; no timer
was disabled or restarted and no historical daily report was overwritten. This is
a failed production result with preserved evidence, NOT a completed publication.


## Explicit audio output request — 2026-11-04

The latest owner instruction requests completing the missed song and restoring
normal future scheduling. Google's official GenMedia Creative Studio Lyria
implementation explicitly requests `response_modalities=["audio", "text"]`:
https://googlecloudplatform.github.io/genmedia-creative-studio/core/foundation-models/lyria/
The current Interactions reference also documents those lowercase values:
https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api
Our request omitted this field. The canonical adapter now explicitly requests
both audio and text, preserving the model, prompt, auth provider, statelessness,
one-request claim and raw-response retention. This is a concrete request-shape
correction; its effectiveness still requires a live production outcome.

The latest instruction is limited operationally to one corrected USD 0.08 base
request for the same existing job; maximum possible cumulative base spend is
USD 0.24, with prior billing and tax/FX still unknown. A separate immutable
completion receipt binds both earlier manifest hashes. Neither is erased or
reclassified as non-billable. A one-use claim prevents a fourth request. Any new
unsettled attempt still blocks. Scheduled model/count/price/cover/quality/time
and upload safeguards remain unchanged. 175 focused regressions passed.

## Original REST transport restoration — 2026-11-04

The explicit-modalities v1 attempt returned `lyria_api_error`; its HTTP body was
not retained by the then-current HTTPError branch. Do not invent a status code
or billing outcome. The actual current GoogleCloudPlatform implementation at
`genmedia-creative-studio/main/models/lyria.py` uses v1beta1 with flat text input,
matching the earlier successful Aether adapter. Its source was read directly.
The adapter is restored to that exact request shape, without a generic automatic
endpoint fallback/retry. Both legacy outputs and v1 response parsing remain.
Future HTTP errors now retain bounded private response bytes and the real code.

The broad owner completion request is bounded here to one restored-protocol
request, USD 0.08 base, possible cumulative base USD 0.32 (actual bills unknown).
A separate immutable receipt binds all three prior manifests; none is erased or
reclassified. All other gates and the ordinary LaunchAgent schedule remain.
177 focused offline tests passed. This entry is not a publication receipt.
