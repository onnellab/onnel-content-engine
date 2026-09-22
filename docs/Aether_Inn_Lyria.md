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

The first Lyria test exposed an unwanted ending that flattened away from an otherwise major-key song. Every production prompt must therefore:
- remain in the original major key;
- use a clear authentic dominant-to-tonic cadence (V–I);
- resolve the final melody note to the tonic;
- finish on the tonic major chord and let it ring naturally;
- not flatten the final melody note;
- use no minor tonic, borrowed-minor/modal-mixture ending, ♭VII ending, deceptive cadence, or unresolved suspended ending.

Do not weaken these rules merely to increase candidate variety.

## Originality and quality

The 65-track catalog in `data/aether_catalog.json` is metadata history, not proof of musical originality. Use it to reject repeated title/style concepts, especially overused structures such as “Beyond…”, “The Road…”, “Where…”, and “Morning…”. File hashes detect exact duplicates only; they do not establish melodic originality.

## Publication boundary

A successful Lyria response is only the music-generation stage. Public upload still requires an accepted candidate, valid Aether cover, validated 1920×1080/30fps/H.264/yuv420p/AAC 256 kbps render, explicitly bound Aether Inn YouTube credentials, durable upload/reconciliation handling, and actual public-state verification. Never report `publication_complete` from Lyria generation alone.
