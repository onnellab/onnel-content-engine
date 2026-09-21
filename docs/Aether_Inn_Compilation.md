# Aether Inn — curated-master compilation worker

## Scope and actual readiness

This worker combines already approved existing masters. It is NOT a Suno generator,
a new-image generator, or a model that can certify musical originality. The metadata
planner remains clearly distinguished from actual audio measurements. Registered
masters must have explicitly confirmed commercial-use permissions and previous
quality acceptance. Neither of these flags may be inferred from a file name, a paid
account's existence, the source model version, or a planned upload schedule.

The default private root is:
`~/Library/Application Support/ONNELLAB/content-engine/aether-inn`

## Private asset registration

Place masters and prepared 16:9 theme covers under `assets/` and register them in
`assets/manifest.json` with this schema. Values below are explanatory placeholders,
not a working or approved production manifest:

```json
{
  "schema_version": 1,
  "profile": "aether_inn",
  "test_only": false,
  "tracks": {
    "<catalog track ID>": {
      "path": "masters/<track>.wav",
      "sha256": "<actual SHA-256>",
      "commercial_use_confirmed": true,
      "quality_accepted": true
    }
  },
  "covers": {
    "open_roads": {
      "path": "covers/open-roads.png",
      "sha256": "<actual SHA-256>",
      "commercial_use_confirmed": true
    }
  }
}
```

Catalog IDs are produced by `python3 -B scripts/aether_planner.py catalog`.
Keep paths relative to `assets`, use actual file hashes, and never commit this
private manifest or media. The worker rejects missing/unconfirmed/hash-mismatched
assets, symlinks, traversal and unsupported media. Historical displayed durations
are replaced with ffprobe measurements before selection. Exact normalized decoded
PCM repeats are rejected; this is not a melodic-plagiarism or copyright classifier.

## One-shot commands

```sh
python3 -B scripts/aether_compilation.py readiness
python3 -B scripts/aether_compilation.py worker --theme open_roads --execute --publish
python3 -B scripts/aether_compilation.py reconcile --execute
```

Without `--execute`, no render or upload occurs. Without `--publish`, a completed
render remains local. `reconcile` only resumes already requested publications and
never creates a new job, including on non-compilation days. The private queue binds
slot, track selection, render hash, policy hash and resumable upload evidence. An
uncertain upload must not be replaced by a new insert. Repeated runs for the same
slot reuse the same durable job and video. A test-only manifest/render cannot publish.

## Selection, rendering and upload

Supported themes: open_roads, lantern_towns, starlit_rest, woodland_water. Select
whole compatible tracks, avoid the last two collections' tracks and duplicate track
sets, and target 1800 seconds with a 60-second tolerance. Every crossfade is included
in the measured duration and chapter timestamps. Never stretch, loop or clip a song
to force 30:00. Three to twenty distinct tracks are allowed; insufficient coherent
material blocks the run instead of mixing unrelated tracks.

The renderer emits 1920x1080, H.264, 30 fps, yuv420p and AAC 256 kbps. It uses a
prepared static landscape cover, restrained two-second crossfades, loudness
normalization, a two-thread encoder and a bounded owned process group. The current
shared upload adapter caps video size at 256 MiB; larger artifacts are rejected,
not partially uploaded. Thumbnail integrity and size are checked separately.

The upload client must be explicitly Aether Inn, verify the independently configured
expected Channel ID, and pass production provenance/render checks. Videos use Music
category 10 and the AI-generated disclosure. The thumbnail is set on the same owned
durable video ID. `publication_complete` is true only after public publication is
observed and the thumbnail API confirms success. Processing, forced-private,
reconciliation-needed and thumbnail-retry statuses remain distinct. Google account
consent and API-project public-upload eligibility are separate activation checks.

## Verification and limitations

A real 62-second technical fixture render passed 1080p/30fps/H.264/yuv420p/AAC checks,
crossfade chapter starts and duplicate decoded-audio rejection. This was not the
owner's music or a production 30-minute compilation. Fake-provider tests verify
same-slot idempotence and exact profile binding; no live upload has occurred.
No actual master/cover manifest or Aether OAuth grant was present at the readiness
check. Those must be supplied before producing the first real collection. New Suno
tracks, new AI cover generation and audio-originality assessment remain unfinished;
connecting YouTube alone does not complete the single-production pipeline.
