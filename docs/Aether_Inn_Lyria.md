# Aether Inn — Lyria 3 Pro Production

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

Then open https://onnellab.com/ops/ and choose **Lyria 3 Pro 연결 · 자동화 설정**. Configure only Project ID, candidate count (1–5), maximum estimated USD per run, and the Tuesday/Thursday/Saturday enable switch.

The local console checks ADC readiness without making a paid music-generation call.

## Paid-generation safety

Paid generation requires all of the following:
1. Local Lyria configuration exists and automatic generation is explicitly enabled.
2. ADC can produce a valid access token.
3. Requested candidate count does not exceed the configured count.
4. Estimated run cost does not exceed the configured per-run cap.
5. The downstream Aether single workflow is ready enough to use the generated audio; do not spend credits just to discover an already-known downstream blocker.
6. The run uses `--execute`. Without it, the generator returns a dry-run plan.

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

The durable worker performs these stages in order:
1. Verify the explicitly bound Aether Inn YouTube connection before paid generation.
2. Call Lyria 3 Pro under the locally approved candidate count and music spend cap.
3. Reject missing, malformed, exact-repeat, or out-of-range audio candidates, then send each technically valid candidate to `gemini-2.5-flash` for fail-closed review of the actual audio. The reviewer checks Aether Inn fit, melody memorability, repeat-listening comfort, arrangement development, ending resolution and technical cleanliness, with explicit critical flags for unresolved endings, EDM/pop energy, trailer bombast and audible artifacts. Select the highest-scoring accepted candidate only.
4. Generate one 16:9 landscape background with `gemini-2.5-flash-image` using the same Google Cloud ADC/project.
5. Keep the generated background text-free, then apply deterministic upper-left matte-gold serif title and small Aether Inn branding through a local SVG overlay, without a black title panel.
6. Render the single at 1920×1080, 30 fps, H.264, yuv420p, AAC 256 kbps.
7. Create a 1280×720 thumbnail from the same branded cover.
8. Upload with the Aether Inn OAuth profile only, AI-generated disclosure enabled, Music category, durable resumable state, and fail-closed public approval policy.
9. Reconcile the same upload/video ID after uncertain provider states and set the thumbnail on that same video.
10. Report `publication_complete` only after the video is observed public and the thumbnail API confirms success.

A failed later stage does not regenerate an already-paid Lyria candidate. The job keeps the music and cover hashes and resumes from the missing stage on the next run.

The automatic candidate gate includes an actual-audio Gemini quality review plus deterministic technical checks. It is still not a copyright or melodic-originality certification. Exact hashes can reject identical files, but the system does not claim that a generated melody is legally or musically unique.
