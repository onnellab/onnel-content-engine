# Approved screenshot guides

On 2026-10-08 the owner approved adding real-app-screenshot guides to restore
ONNELLAB's English YouTube Shorts schedule using dot cloud tools, without a new
Work/Codex task, paid generation, synthetic UI, or simulated interaction.

This is a distinct content contract, not a relaxation of the managed-recording
pipeline. `video_publish_policy.json`, `short_video_policy.py`, the recorder and
Windows scheduled worker remain unchanged. A screenshot guide must never be
inserted into their recording index or described as an execution demonstration.

## First reviewed guide

`data/screenshot_guides/quivra-file-list-20261009.json` uses only Quivra's English
raw screenshots 01 and 02 from source commit
`d3b7ad5e5dcd0412daae55caee657431c6237f5b`. Their exact SHA-256 values are pinned in
both the manifest and the separate validator. The actual pixels and screenshot
harness were reviewed. These are the real app presentation layer populated with
repository-owned demonstration filenames. The harness mocks transcoding, so
conversion-progress and saved-result screenshots 03–05 are intentionally excluded.
No runtime conversion, successful output, or performance claim is made.

Source pubspec is 1.0.10+85; the live App Store page showed public 1.0.10 on
2026-10-08. This is source/release evidence, not an invented exact capture-build
attestation. Source image paths, commit, file hashes, provenance limitations and
rights basis remain in the manifest. Source files are not changed or committed
to this repository.

## Offline preparation

Materialize the two exact repository files into a private local `ASSETS` folder.
Do not use screenshot previews, thumbnails, generated lookalikes, other apps,
or an unverified latest asset under the old hash. Run:

```sh
python3 -B -m unittest discover -s tests -p test_screenshot_guide.py
python3 scripts/screenshot_guide.py verify --manifest data/screenshot_guides/quivra-file-list-20261009.json --assets ASSETS
python3 scripts/screenshot_guide.py render --manifest data/screenshot_guides/quivra-file-list-20261009.json --assets ASSETS --output NEW_OUTPUT
```

Requires existing Pillow, ffmpeg/ffprobe and DejaVu Sans. The script installs
nothing, contacts no provider, runs no app or emulator, and invokes no AI.
It uses two encoder threads, a 180-second timeout, and refuses existing output
directories. It produces a 15-second 1080x1920 H.264/yuv420p/30fps silent MP4,
three reviewable frames and render evidence bound to manifest/image/video hashes.
Source screenshots are uniformly scaled in their entirety; no crop or retouch,
fake taps, progress animation, conversion result, or fabricated app behavior.
The screenshot-format disclosure appears throughout. Verify all three frames
and ffprobe output, then verify that the owned encoder process has exited.

## Copy and discovery

Use a genuine how-to search intent, answer it early in plain English, and keep
ASO/SEO/AEO wording consistent with actual visible controls and current app facts.
The first title is "How to Choose Files in Quivra | Media Converter Screenshot
Guide". Metadata connects to verified App Store and Google Play destinations.
Do not keyword-stuff, claim conversion success/speed, imply a live tutorial, or
describe unreleased functionality. No voice or music is required.

The pilot is deliberately allowlisted. A future app/topic or changed source,
image, copy, or geometry requires a new reviewed manifest and validator coverage;
do not replay this video under new dates to fill the cadence. Format-level owner
approval does not remove the factual/provenance checks for each new guide.

## Portfolio selection, including newer apps

Read the current `data/apps_registry.csv` every run; do not freeze the six-app
list from the old recording strategy. As of 2026-10-08, all eight released,
content-eligible products are candidates: Quivra, TagWeaver, VaultXT, Segra,
ClipNest, Aligna, Melivra and Papira. New eligible registry rows enter the same
candidate review rather than requiring a manually maintained legacy list.
`data/screenshot_guides/catalog-review-20261008.json` records this review.

Candidate inclusion is not publication readiness. Check live platform/store
availability, current actual screenshot/version provenance, rights and visible
feature support separately. A disabled runtime recording scenario does not
exclude an independently verified screenshot guide. Conversely, a public store
listing alone does not prove that a source screenshot depicts the released app.
Melivra is currently public on Android; do not recommend its unconfirmed iOS
release. Papira is public on both iOS and Android; the older iOS-only notes are
superseded by the public Google Play check on 2026-10-08 and October 7 store data.

Prefer a useful distinct question with verified assets, then balance verified
recent channel exposure across apps. Melivra/Papira have no public app-guide
Shorts in the inventory checked on 2026-10-08 and should be reviewed early, ahead
of repeating the just-scheduled Quivra guide. Do not manufacture exact engagement
scores, promote an unverified platform, or fill a slot with a near-duplicate.
If no candidate passes, record the specific blocker without relabeling the whole
catalog as ineligible. The parent-owned schedule coordinates one publisher only.

## Single-publisher browser scheduling

The parent owns the one dot production schedule. The old ChatGPT automation
`6ab0e555efc88191a4f8f1b1767fe767` was observed paused on 2026-10-08 and must remain
paused. The repository's Windows coordinator also remains disabled; this work
does not certify that all independently installed local services are absent.
Never start a second publisher or claim `legacy_writer_fencing=true` without
evidence. Aether Inn is a separate profile and is untouched.

1. Inspect ONNELLAB Studio and verify channel `UCXyRedrldRBl9Y35nyWoTLg`.
2. Read the existing guide receipt. Any upload intent without a terminal result
   requires Studio reconciliation; never select the file again blindly.
3. Check all current videos/Shorts for the exact guide/title, then durably record
   the upload intent, manifest/video hash, and desired KST schedule before upload.
4. Upload the verified MP4 once through the existing signed-in Studio session.
   Persist the video ID as soon as Studio assigns it. Never store cookies,
   credentials, resumable-session URLs, or private account data in Git.
5. Apply reviewed title/description, not-made-for-kids and accurate synthetic-media
   disclosure. Schedule 2026-10-09 09:00 Asia/Seoul for the first guide. Explicitly
   inspect the timezone; do not interpret the cloud computer's local zone as KST.
6. Completion requires Studio's scheduled confirmation with matching video ID,
   channel and date/time. `uploaded`, `processing`, or a private draft is not
   scheduled. Persist only observed evidence; public status is checked after due.
7. If blocked, preserve the same draft/video ID, explain the blocker, and continue
   permitted preparation. Do not invent publication receipts, re-upload, or
   transfer local secrets. Captcha/security/new access confirmations follow the
   normal approval rules.

Saving code or rendering a file never itself authorizes an upload. This first
guide's upload/schedule is covered by the owner's explicit restoration and
screenshot-format approval. Future runs remain bounded to the approved channel,
format, fact checks, one due slot and the one parent-owned schedule.
