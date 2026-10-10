# Aether Inn — Lyria 3 Pro Production

## Current scoped Lyria 3 Pro authorization (2026-10-10)

The owner explicitly authorized **one** Lyria 3 Pro music candidate at an
estimated **$0.08** per eligible single. The Mac configuration already has
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

Then open https://onnellab.com/ops/ and choose **Lyria 3 Pro 연결 · 자동화 설정**. Keep candidate count at exactly 1 and maximum estimated USD per run at $0.08; only the Tuesday/Saturday enable switch applies. Production work starts around 07:00–08:00 Asia/Seoul and uploads are scheduled private with YouTube `publishAt` for exactly 09:00 Asia/Seoul on each single day.

The local console checks ADC readiness without making a paid music-generation call.

## Paid-generation safety

Paid generation requires all of the following:
1. Local Lyria configuration exists and automatic generation is explicitly enabled.
2. ADC can produce a valid access token.
3. The exact model is `lyria-3-pro-preview`, with **one** candidate and a $0.08 estimate.
4. Both the local spending cap and the central Lyria-only owner budget gate permit the request.
5. The launchd-owned Aether worker has finished the WAV backlog, selected a fresh Tuesday/Saturday slot before 08:00, and verified a separately owner-approved local cover for this exact title; never spend only to discover a known downstream blocker.
6. No existing uncertain paid request or active upload may be duplicated; a durable `request_started` manifest is written before the API call.
7. The generator uses `--execute`. Without it, the generator returns a dry-run plan.

Dry run:

    python3 -B scripts/lyria_generate.py --title "Beyond the Silent Stone Gate" --style "Warm guitar, gentle piano, nostalgic JRPG frontier theme"

Paid run:

    python3 -B scripts/lyria_generate.py --title "Beyond the Silent Stone Gate" --style "Warm guitar, gentle piano, nostalgic JRPG frontier theme" --execute

Never retry a paid generation blindly after an uncertain network result. Preserve returned candidates and manifests.

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
