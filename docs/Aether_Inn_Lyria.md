# Aether Inn — Lyria 3 Pro Production

## Current generation policy — owner correction, 2026-11-04

This section supersedes the 2026-10-27 assistant-added interpretation requiring
an all-in USD 0.08 invoice ceiling and a manually authored account/rights proof.
The recovered original owner instruction permits only Lyria 3 Pro at USD 0.08
per song. The owner then explicitly requested restoring the previous generation
basis, separating provider rights from billing and correcting these blockers.
The implemented cost basis is the **provider base price**, not a certified
all-in tax/FX amount. This is a business-policy correction, not a tool-safety
setting change or a claim that a platform restriction has been disabled.

- Exact paid model: `lyria-3-pro-preview`; exactly one candidate/request per song.
- Provider base price must be positive and no more than **USD 0.08**. A price
  increase, absent price, ambiguous row or incompatible model still blocks.
- Tax, currency adjustment and final invoice are reported separately as unknown
  unless actually observed. Never claim the final charge is USD 0.08 or tax-free.
- Gemini paid cover generation, paid audio review and other paid providers remain
  disabled. Approved existing artwork and local signal-quality review are used.
- The owner's connected Google Cloud project and existing authentication are
  reused. The code does not accept new terms, change billing or fabricate an
  account agreement/rights attestation. Public permission is not copyright
  ownership, originality or non-infringement certification.

## Public-source verification, not manual proof.json

`scripts/aether_lyria_rights.py collect` reads these official documents:

- Model permission: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/lyria/lyria-3?hl=en
- Explicit preview exception: https://cloud.google.com/terms/genai-preview-products?hl=en
- Applicable service terms: https://cloud.google.com/terms/service-terms?hl=en
- Full-song USD unit price: https://cloud.google.com/model-garden/pricing?hl=en

The collector retains complete visible source text, URLs, original HTML hashes
and stored-text hashes under private `lyria-paid-evidence/public-sources/`.
After all sources succeed it atomically publishes schema-v2 `current.json`.
The ordinary Tuesday/Saturday LaunchAgent slot refreshes these public documents
before concept selection. The receipt is valid for 24 hours; this is automatic
source freshness, not a request that the owner produce a daily certificate.
Collection failure does not turn old evidence into success or create a new job.

The compatibility-named `aether_paid_guard.load_paid_proof` now reads this public
receipt. It rechecks source bytes, source URLs, model permission, the preview
exception, the specific Lyria 3 Pro price row and expiry. Its digest also binds
the exact receipt to the configured project. No account-specific hand-authored
`lyria-paid-evidence/proof.json` is required, created or overwritten. Old files
and charge/job histories are retained; they are not rewritten as new approvals.

The receipt alone has `generation_authorized=false`. Actual dispatch additionally
requires the original enabled setting, model/purpose/count/base-budget gates,
current time window, approved cover, complete owned-video inventory, exclusive
paid-request lock and a new durable one-use request intent. Every active check
is repeated immediately before the one paid POST. Changed receipts or source
bytes, uncertain earlier requests and mismatched settings stop the request.

## Execution and publication boundaries remain unchanged

Only `com.onnellab.aether-daily-local` at 06:20 Asia/Seoul owns unattended execution
through `scripts/aether_daily_local.py`. Scheduled ChatGPT reporting remains
read-only and must not run a replacement producer or this source collector.
Interactive code maintenance/tests do not imply a production run.

The worker first reconciles exact existing video/session IDs and checks all six
registered WAV backlog titles. Backlog WAVs never use Lyria, and `A Fantasy Still
Breathing` must not be regenerated/re-uploaded. Only an exhausted verified
backlog and an approved per-title local cover permit considering a new song.

New paid generation begins only on the current Tuesday/Saturday before 08:00 KST.
After refreshing sources, the wrapper rechecks the time before consuming a title.
The single uploader remains PRIVATE with `publishAt` exactly 09:00 Asia/Seoul.
A missed slot is not silently resurrected, moved or published immediately.
Any owner-requested recovery of a stale slot must be handled as a separate,
explicit publication decision; this policy correction does not make one.

The existing uncertain-request scanner checks every old manifest even for
rejected/stale jobs. The paid adapter persists its intent and one-use dispatch
claim before POST. A lost/uncertain result never permits another paid attempt.
Existing generated audio, approved artwork, hashes and upload IDs are reused.
No test or dry-run result may be called a real upload/publication receipt.

## Connection and local configuration

Model: `lyria-3-pro-preview`; region: `global`.
Official endpoint:
`https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/interactions`.
The current request matches Google's GenMedia Creative Studio REST adapter:
`{"model":"lyria-3-pro-preview","input":[{"type":"text","text":"..."}]}`.
Source read 2026-11-04:
https://github.com/GoogleCloudPlatform/genmedia-creative-studio/blob/main/models/lyria.py
This is also the earlier successful Aether request shape. The intervening v1
step-shaped request returned completed metadata without audio in a live attempt;
adding response_modalities to that request then produced an API error. Restoring
the original beta transport produced real accepted audio on 2026-11-04.
Both `outputs` and v1 `steps[].type=model_output` responses remain readable.
The exact raw successful/error response is retained privately before parsing;
no automatic endpoint fallback or second POST occurs on an ambiguous response.
This transport correction does not change ordinary generation windows,
publication timing, spending or approval checks.
The existing local configuration remains `enabled=true`, `candidate_count=1`,
`max_usd_per_run=0.08`. Its cap is explicitly a provider-base budget.
Credentials remain in the existing Google ADC/Keychain providers, never Git,
reports, terminal arguments or public Ops snapshots. No new authentication flow
or provider has been added. Dry plans remain `paid_authorized=false`.

## Aether Inn prompt contract

Every new single must begin with musical movement immediately; prefer warm guitar, midrange piano, mellow strings, cello or flute; feel like a nostalgic JRPG/MMORPG journey rather than ambience, battle music, EDM, or trailer music; expand gradually; and avoid aggressive percussion and sharp high-register piano.

### Ending contract

The first Lyria test exposed an unresolved ending: a C-major piece stopped on B, the leading tone, instead of resolving to C. The rule is therefore about tonal resolution, not about forcing every song into major.

Every production prompt must:
- allow major, minor, or modal writing when it fits the concept;
- preserve a coherent tonal center and mode unless a modulation is intentionally part of the concept;
- bring the final melody to the tonic/home note in a natural register, often the same or a higher octave;
- land the final harmony on the tonic/home chord appropriate to the established mode;
- in ordinary major/minor tonality, prefer a clear authentic cadence such as V–I or V–i;
- for a genuinely modal piece, use an equally stable cadence back to the modal tonic;
- let the final tonic/home harmony ring naturally;
- not end on the leading tone, a note one semitone below the tonic, the dominant, or another obviously unresolved tendency tone;
- not introduce an abrupt major/minor/modal shift only at the ending unless the concept explicitly requires it;
- avoid deceptive cadences, unresolved suspensions, and ambiguous fades as the default ending.

The important quality gate is “this feels finished and back home,” not “this must be major.”

## Concept and energy rotation

New singles must not collapse into only quiet meadow/road ambience. Use `data/aether_single_lanes.json` as the production concept pool and rotate across different travel energies.

Required lanes include:
- quiet road / town / rest themes;
- skybound flight and floating-island travel;
- open-sea sailing and harbor departure;
- diving, underwater ruins and deepwater exploration;
- traveler/caravan/festival marches;
- triumphant homecoming and celebratory return;
- faster frontier exploration with a heart-racing sense of discovery;
- reflective night, aurora, farewell and reunion themes.

In a rolling 8-single window, aim for at least 3 high-motion concepts and at least 2 traversal concepts (flight, sailing, diving or frontier movement). Do not schedule more than 2 calm concepts in a row. These are editorial rotation rules, not measured audio-energy claims.

Energetic tracks may use a clear pulse, rhythmic guitar/bass, string ostinati, light snare or frame drum, and optional warm horns/brass. They must remain fantasy travel music: no battle groove, military aggression, EDM drop, or trailer-style percussion wall.


### Cover full-bleed and typography contract

Generated cover backgrounds must fill the 16:9 frame edge-to-edge. The cover worker rejects top or bottom regions that behave like dark letterbox bands by sampling luminance from both edges against the center. Prompts explicitly forbid black bands, cinematic frames, borders, dark title panels, and edge vignettes that collapse into bars. Night and underwater scenes must still retain visible color and environmental detail at every edge.

The title overlay is deterministic and local. The main title uses a larger 72 px Baskerville/serif treatment in light champagne ivory (`#F2E8D5`) while the small `Aether Inn` branding and restrained line/diamond ornament remain matte gold. A subtle dark shadow is always present and becomes slightly stronger only when the selected background region is bright. Placement is contrast-adaptive: the worker samples several candidate regions, penalizes bright/warm sunset areas and low-contrast texture, prefers a readable position in the upper part of the frame, and may move away from the upper-left when that area would swallow the title. No black backing panel or metallic logo effect is allowed. Background generation may retry up to three times when letterboxing is detected; an accepted Lyria music candidate is never regenerated merely because a cover attempt failed.

## YouTube playlist curation

Aether Inn uses six public YouTube playlists managed idempotently by `scripts/aether_playlists.py`: the complete archive, open-road/skybound travel, lantern towns/cozy inns, forests/rivers/ancient ruins, starlit rest/quiet farewells, and uplifting adventures/grand returns. A track may belong to multiple thematic playlists when its title, catalog style, or single-lane metadata supports that classification. Tracks without sufficient thematic evidence are kept in the complete archive rather than forced into an inaccurate category.

Run `python3 -B scripts/aether_playlists.py --execute` after a new Aether single upload and during the daily Aether reconciliation pass. The sync must use only the `aether_inn` YouTube profile, reuse exact existing playlist titles, avoid duplicate playlist items, and insert new matching tracks at position 0 so newer releases remain near the top. Public legacy uploads are classified from the catalog where available; durable single jobs may supply title/style/lane metadata for published, scheduled, or provider-processing videos. Forced-private, rejected, blocked, or uncertain/reconcile-required jobs must not be added merely because they have a video ID.

## Originality and quality

The 65-track catalog in `data/aether_catalog.json` is metadata history, not proof of musical originality. Use it to reject repeated title/style concepts, especially overused structures such as “Beyond…”, “The Road…”, “Where…”, and “Morning…”. File hashes detect exact duplicates only; they do not establish melodic originality.

## Publication boundary

A successful Lyria response is only the music-generation stage. Public upload still requires an accepted candidate, valid Aether cover, validated 1920×1080/30fps/H.264/yuv420p/AAC 256 kbps render, explicitly bound Aether Inn YouTube credentials, durable upload/reconciliation handling, and actual public-state verification. Never report `publication_complete` from Lyria generation alone.

## End-to-end single worker

The new-single production path is implemented in `scripts/aether_single.py`.

Dry readiness check:

    python3 -B scripts/aether_single.py readiness

Production invocation:

    python3 -B scripts/aether_single.py worker --slot YYYY-MM-DD --lane skybound_flight --title "Sails Above the Cloud Sea" --style "Buoyant nostalgic JRPG flight theme with warm guitar and strings" --execute --publish

### Existing catalog WAV backlog

Missing legacy catalog uploads use a separate no-Lyria path so a canonical master is never regenerated merely to publish it. `backlog-worker` accepts only the six currently missing recovery titles registered in `scripts/aether_single.py`; `A Fantasy Still Breathing` was removed after its existing public Aether Inn upload was confirmed. Before a publish run touches MYBOX, the worker searches the verified Aether Inn channel and verifies matching candidate video status; an already-public matching title returns `already_public` without creating a job or reading the WAV. It resolves a genuinely missing master from the Unicode-normalized MYBOX `개인 폴더/Aether Inn/01_Audio_Master/<TITLE>.wav` path, copies that WAV into the private durable single job, verifies its SHA-256 and measured duration against the catalog, and records `source_kind=backlog_wav`. A visible File Provider placeholder is allowed to materialize through that verified copy even when macOS still reports `SF_DATALESS`; the flag alone is not a failure. When a backlog master is `SF_DATALESS`, the worker first wakes the installed MYBOX app in the background so its File Provider can service the read without requiring Finder interaction. A missing cloud item fails as `aether_single_backlog_wav_not_synced`, while a placeholder that cannot actually be read/copied fails as `aether_single_backlog_wav_unavailable`. Neither condition may fall back to Lyria.

Before MYBOX access, the worker may reuse a complete retained `source/master.wav`
from an existing canonical backlog job for the exact title. Reuse requires the
existing Aether commercial-use attestation, matching original filename and job
identity, a nonsymlink local path, and the queue's exact SHA-256. Dataless or absent
copies are skipped; unsafe records, changed bytes and conflicting masters fail
closed. The copied bytes are checked against that SHA again before the normal
duration and offline signal-quality gates. This only supplies source bytes to a
new eligible slot; it never rewrites, revives or reschedules the previous job.
Public-title reconciliation, per-title cover approval, render, upload and 09:00
publication contracts still apply. A retained WAV does not establish readiness
of a future upload or authorize replacing another missing master.

On an eligible Tuesday/Saturday slot, publish one recovery item with:

    python3 -B scripts/aether_single.py backlog-worker --slot YYYY-MM-DD --title "Beyond the Road of Falling Petals" --execute --publish

Backlog jobs bypass new-concept duplicate and lane-rotation gates because the titles are already registered catalog masters, but they retain the same Aether-only YouTube binding, exact 09:00 Asia/Seoul schedule, durable upload/reconciliation, current cover generation/branding, render validation and thumbnail gates. Existing MP4 files are derivatives and are never source masters. The existing-master path performs a local decoded-PCM signal-quality review and records its SHA-bound outcome. It does not invoke Gemini or claim a human musical listening assessment.

The durable worker performs these stages in order:
1. Verify the explicitly bound Aether Inn YouTube connection before paid generation.
2. Call Lyria 3 Pro under the locally approved candidate count and music spend cap.
3. Reject missing, malformed, exact-repeat, or out-of-range audio candidates. Apply the local zero-cost PCM signal-quality check to each valid candidate (level, silence, clipping, hard-cut and basic temporal variation), reject failures, then choose the best accepted candidate. The offline gate does not claim to judge melodic memorability, genre fit, emotional development or harmonic resolution; the former Gemini reviewer remains disabled under the no-paid-API policy.
4. Import the separately approved and SHA-bound existing 16:9 landscape background for that exact title; paid Gemini cover generation remains forbidden.
5. Apply the current contrast-adaptive 72 px champagne-ivory Baskerville/serif title plus small matte-gold Aether Inn branding and line/diamond ornament through a local SVG overlay, without a black title panel.
6. Render the single at 1920×1080, 30 fps, H.264, yuv420p, AAC 256 kbps.
7. Create a 1280×720 thumbnail from the same branded cover.
8. Upload with the Aether Inn OAuth profile only, AI-generated disclosure enabled, Music category, durable resumable state, and fail-closed public approval policy.
9. Reconcile the same upload/video ID after uncertain provider states and set the thumbnail on that same video.
10. Report `publication_complete` only after the video is observed public and the thumbnail API confirms success.

A failed later stage does not regenerate an already-paid Lyria candidate. The job keeps the music and cover hashes and resumes from the missing stage on the next run.

The current automatic candidate gate analyzes actual decoded PCM locally without a paid API and saves SHA-bound signal quality findings. It is not a human/Gemini musical listening review or a copyright, genre-fit, tonal-resolution or melodic-originality certification. Exact hashes can reject identical files, but the system does not claim that a generated melody is legally or musically unique.

## Explicit manual publication request — 2026-11-04

The owner explicitly requested `기존 누락곡의 공개 완료해`, following the request
to complete production and publication of the missed November 3 single. This
interactive release concerns only `The Pass Beyond the Racing Plains`, existing
job `1f5cf414734a3a362b4db5cc`. It does not change unattended execution or schedules.

`scripts/aether_manual_release.py record-request` records that instruction in
one private immutable job/prompt/project-bound receipt, valid for two hours.
It preserves the original slot and prior rejection; it never renews an expired
receipt, deletes prior charges or creates another queue job. `publish` calls the
canonical single worker for that exact job. The source/price/model/count/cover,
complete owned-inventory, PCM quality, render integrity and one-use charged-request
checks all remain. The receipt supplies this explicitly requested manual window;
ordinary Tuesday/Saturday generation and PRIVATE + 09:00 scheduling are unchanged.

Actual publication uses the canonical uploader's manual public approval, bound
to the completed render and metadata, with no past publishAt. Same-video/session
reconciliation remains mandatory; accepted or processing uploads are not public
completion. Set its thumbnail and separately synchronize the canonical playlists.
The daily ChatGPT reporting task must never call this interactive command.

165 focused tests passed before production, including same-job idempotency,
immutable/expiring requests, project/prompt binding, one charged request,
uncertain-result preservation and unchanged scheduled/hosted-operation behavior.
These tests are not a production or publication receipt.
