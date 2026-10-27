# Aether Inn — Lyria 3 Pro Production

## Current scoped Lyria 3 Pro authorization (2026-10-27 safety clarification)

The owner explicitly authorized **one** Lyria 3 Pro music candidate within
**$0.08 total per eligible single, including taxes and all mandatory costs**.
The base-price estimate is not proof of that total. The existing Mac configuration has
`enabled=true`, `candidate_count=1`, and `max_usd_per_run=0.08`.
Only `lyria-3-pro-preview` has a paid API exception, and a durable charge
intent must be recorded before the call. The Gemini cover-image API,
paid Gemini audio review, and **all other paid providers remain disabled**.
An uncertain result never authorizes a second charged call.

On Tuesday/Saturday the launchd worker always reconciles and finishes the
registered WAV backlog first, *without* Lyria. Only after all six canonical
backlog titles are confirmed public may it consider a new song, with an
owner-approved, hash-verified local cover and enough time before 09:00.
The new Lyria call must start before 08:00 KST. Missing approved cover or
rights, unresolved upload, invalid audio or unready credentials blocks
without a speculative generation charge. Existing masters and
[approved single covers](Aether_Inn_Existing_Covers.md) use local
rendering. Audio signal quality is checked locally without requiring
per-song owner listening approval; this is not music-aesthetic certification.

## Purpose

Aether Inn uses Google Lyria 3 Pro for new instrumental singles. The public /ops/ page never stores Google credentials. The worker Mac authenticates with Google Cloud Application Default Credentials (ADC).

## Fixed provider settings

- Model: `lyria-3-pro-preview`
- Location: `global`
- Official endpoint: `POST https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/interactions`
- Local setup: `python3 -B scripts/lyria_connect.py open`
- Generator: `python3 -B scripts/lyria_generate.py`
- Private config: `~/Library/Application Support/ONNELLAB/content-engine/lyria/config.json`
- Private generated audio: `~/Library/Application Support/ONNELLAB/content-engine/aether-inn/lyria/`

## One-time Mac authentication

Do not copy OAuth tokens, ADC JSON contents, or access tokens into Git, /ops/, prompts, logs, or dashboard fields.

    gcloud auth application-default login
    gcloud auth application-default set-quota-project PROJECT_ID

Then open https://onnellab.com/ops/ and choose **Lyria 3 Pro 연결 · 자동화 설정**. Keep candidate count at exactly 1 and the existing USD cap at $0.08; only the Tuesday/Saturday enable switch applies. The sole producer remains the existing Mac `com.onnellab.aether-daily-local` at 06:20 Asia/Seoul. New Lyria calls must begin before 08:00 and uploads are scheduled private with YouTube `publishAt` for exactly 09:00 Asia/Seoul on each single day. Do not add a cloud producer, reset same-day records, or make catch-up posts.

The local console checks ADC readiness without making a paid music-generation call.

## Paid-generation safety

Paid generation requires all of the following:
1. Local Lyria configuration exists and automatic generation is explicitly enabled.
2. ADC can produce a valid access token.
3. The exact model is `lyria-3-pro-preview`, with **one** candidate.
4. Both the existing configuration/coarse allowance and the SHA-bound current gross-cost/rights proof described below permit the request. Missing proof means zero paid calls, not a presumed tax-free $0.08 total.
5. The launchd-owned Aether worker has finished the WAV backlog, selected a fresh Tuesday/Saturday slot before 08:00, and verified a separately owner-approved local cover for this exact title; never spend only to discover a known downstream blocker.
6. No existing uncertain paid request or active upload may be duplicated. A durable `prepared` intent binds the slot, prompt, model and proof hash; `request_started` and a one-use dispatch claim are persisted before POST. All Aether single-job manifests, including stale/rejected jobs, and the legacy standalone Aether Lyria directory are checked. Unknown/malformed legacy manifests HOLD; they are not automatically deleted or declared charged.
7. Only the existing durable single worker supplies the current slot for execution. Without execution, the generator returns a static base-price plan explicitly marked `paid_authorized=false`; it does not authenticate or verify billing. The old standalone `--execute` example is not an authorized alternate producer and now fails without a slot-bound request.

Dry run:

    python3 -B scripts/lyria_generate.py --title "Beyond the Silent Stone Gate" --style "Warm guitar, gentle piano, nostalgic JRPG frontier theme"

Never retry a paid generation blindly after an uncertain network result. Preserve returned candidates and manifests.

### Gross-cost and commercial-use evidence (no active proof supplied by code)

`scripts/aether_paid_guard.py` reads only the separately reviewed private file:

`~/Library/Application Support/ONNELLAB/content-engine/aether-inn/lyria-paid-evidence/proof.json`

It never writes that proof, looks up credentials, accepts terms, changes billing,
or invents an account's country/tax treatment. Keep its directory private and
proof at mode 0600. Tests create clearly fictional temporary fixtures only.
An evidence SHA proves file integrity, **not factual accuracy or owner approval**.
The reviewer must verify the referenced source bytes and applicability first.

Schema version 1 requires these exact sections (see the validator for types):

- Identity: `profile=aether_inn`, `provider=google_cloud`, exact `project_id`,
  `model=lyria-3-pro-preview`, `location=global`, integer `candidate_count=1`.
- Review: UTC `checked_at` / `expires_at` ending in `Z`, at most 24 hours apart,
  not future-dated or expired; `reviewer=dot` and a real `authority_reference`.
  A trace key is not an authenticated owner-message ID. Do not record user
  listening approval, exclusivity, originality or indemnity from these fields.
- `pricing`: `unit=song`, three-letter `currency`, decimal-string `unit_price`,
  and a hash-verified official current pricing `source`.
- `billing`: two-letter billing `country`, matching `currency`, confirmed
  decimal-string `tax_rate`, `mandatory_fee_per_song`,
  `rounding_usd_upper_bound`, `usd_per_currency_upper_bound`,
  `all_mandatory_costs_confirmed=true`, and redacted account-applicable `source`.
  USD requires conversion 1 and `fx_source=null`; another currency requires
  actual hash-verified `fx_source` supporting a conservative USD upper bound.
- `rights`: verified `commercial_use_allowed`, `output_distribution_allowed`,
  `existing_agreement_confirmed`, a traceable `agreement_reference`, plus
  hash-verified official `model_source` and `terms_source`. This records review
  of already applicable terms; it does not accept a new agreement.
- Every source descriptor has only relative `path`, actual `sha256`, and
  `reference` (official URL, or a private redacted billing/FX evidence reference).
  No symlink, path traversal, account/card number, tax ID or credential belongs
  in the proof. Do not commit private billing sources to Git.

The exact, high-precision upper bound is
`(unit_price + mandatory_fee_per_song) * (1 + tax_rate) * usd_per_currency_upper_bound + rounding_usd_upper_bound`.
No rounding down, anticipated tax recovery, promotional credit, unknown tax or
unverified conversion may make a request fit the $0.08 ceiling. Fees are
conservatively included in the taxable base. A positive amount above the cap
HOLDs; broad approval to fix blockers does not increase the spending limit.

As checked 2026-10-27 UTC, the official
[Cloud price page](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing?hl=en)
lists Lyria 3 Pro at $0.08 per song; non-USD accounts use their currency SKU.
[Cloud tax documentation](https://docs.cloud.google.com/billing/docs/resources/vat-overview)
says SKU prices exclude tax and Korean customers are subject to 10% VAT.
If applicable, $0.08 times 1.10 is $0.088 before any other costs and fails this
cap. This is conditional, not a finding about this account's billing country.
The current [model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/lyria/lyria-3)
permits commercial/production use and third-party output disclosure subject to
the applicable agreement. [Service terms](https://cloud.google.com/terms/service-terms)
do not establish musical uniqueness or universal non-infringement. These dated
research links alone are not an active per-account cost/rights proof.

### Final request boundaries and reconciliation

After token acquisition and intent fsync, the adapter rechecks current
enabled/project/count/cap, the unchanged proof and source hashes, and the same
Tuesday/Saturday slot before 08:00 KST immediately before its one paid POST.
An exception after entering transport leaves `request_started` uncertain, even
if the client did not receive audio. It cannot dispatch again. A process that
fails a final preflight before entering transport records `not_sent` with
`dispatch_started=false`; it preserves the intent/claim and does not retry it.

Before generation and a first single upload, the verified owner's complete
uploads playlist is read with the existing `youtube.readonly` scope. Public,
private, scheduled, unlisted and processing title collisions HOLD for
reconciliation; permission failure, missing videos or incomplete pagination
are not proof of absence. The API does not supply the source WAV/MP4 SHA, so
this check does not claim remote byte equality. Known upload sessions/IDs keep
their existing local render-SHA and channel bindings and are never replaced.

The Aether first-upload adapter rechecks its approved publish time after hash
calculation and durable intent save, immediately before `videos.insert`.
Existing session probes and accepted-ID observations remain possible after
09:00; they are not new uploads. Neither the same-day guard nor launchd timing
is changed. Newly prepared covers do not themselves mean generation, scheduling,
or publication succeeded.

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
