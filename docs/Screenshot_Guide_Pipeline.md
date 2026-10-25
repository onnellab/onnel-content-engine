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

## Reviewed Melivra Favorites guide — 2026-10-11

`data/screenshot_guides/melivra-favorites-20261012.json` is a second, independent
allowlisted contract. It uses only English Android screenshots 1 and 4 from
`onnellab/melivra` commit `6314b685a41c690e8ccd9a080c095078ebb0db10`.
Exact source paths and SHA-256 hashes are pinned in the manifest and immutable
`MELIVRA_CONTRACT`. Every manifest field, including copy, source limitations,
rights, Android-only CTA and KST target, must match. This does not make arbitrary
Melivra screenshots or future dates automatically eligible.

These are actual Android emulator captures with repository-authored demonstration
tracks, original procedural covers, seeded favorites/ratings and silent WAV data.
Capture source is 1.0.6+142; public Android 1.0.7 was checked live on October 11.
The reviewed source differs only in version/build constants across the app code
and capture harness. Do not call the screenshots exact signed-release-build
captures. No playback, import, conversion, save result or performance is shown.
Public iOS availability is unconfirmed and is excluded.

The full 1080×2400 screenshots are uniformly fitted to 621×1380 without cropping,
retouching or simulated interaction. The visible persistent disclosure reads
“Still-screen guide · Demo library”. The output contains no narration or music.
The encoder is bounded to two threads and 180 seconds. Frame-rate filtering and
an explicit frame limit produce exactly 450 frames at 30 fps; ffprobe checks
15.000-second duration, H.264/yuv420p, 1080×1920 and absence of audio. Existing
Quivra validation and all managed-recording gates remain separate and intact.
Never rerender an existing uploaded video or replace its durable upload hashes.

Run `python3 -B -m unittest discover -s tests -p 'test_screenshot_guide*.py'`.
The Melivra tests cover exact contract matching, changed source/copy/claims,
wrong app/channel/platform/link, type confusion, asset hash/path/symlink and
geometry rejection, unchanged output preservation, bounded encoder arguments,
and rejection of 449/451-frame, wrong-fps or wrong-pixel-format output.
Actual frame/byte verification is separate from mocked encoder unit tests.
The preparation packet records historical blockers; the reviewed manifest and
render evidence record completed production checks. Neither file is an upload
receipt. Persist hash-bound intent and reconcile live Studio before selecting
any upload file, then persist the assigned ID and actual scheduling result.


## Reviewed ClipNest search guide — 2026-10-13

The owner approved applying the same free dot-cloud Python, ffmpeg and ffprobe
production and verification workflow to one ClipNest search guide for
2026-10-14 09:00 Asia/Seoul. The earlier preparation pause was the narrow
Melivra-only execution authorization, not an encoder or Studio outage. No new
Work/Codex task, paid API/credits, desktop or legacy publisher is involved.

The independent exact contract is
`data/screenshot_guides/clipnest-search-20261014.json`. It uses English iPhone
simulator screenshots `assets/store_promo/raw/en/iphone_medium/01.png` and
`02.png` from `onnellab/clipnest` commit
`5db2441e1cff466012a020717c856aa357ba6cc7`, verified against their full SHA-256.
The selected PNGs were introduced in commit
`33baceb79cc19d090d09f5d6c298da6cd1474afb` (source version 1.0.4+97), and are
unchanged in current 1.0.5+98 sources. App Store public 1.0.5 and main-app text
search were checked live on October 13. The relevant production HomeScreen and
search presentation remain unchanged; intervening lib changes are formatting,
trailing commas and static scanner comments. This is source/release parity
evidence, not an attestation of an exact signed-release capture build.

The capture harness renders actual production screens with FakeClipsStore,
original repository-written example clips and fake purchase/keyboard bridges.
The guide explains where search is and how to review the visible Project match.
It does not show typing, clipboard capture, saving, pasting, speed or background
monitoring. The still-screen/demo-text disclosure remains visible throughout.
Full source screenshots are uniformly fitted without cropping or retouching.
No music or narration is used. Do not reuse the old July screenshots or add
keyboard/purchase/privacy claims to this contract.

Preserve the existing Quivra and Melivra contracts, receipts and uploaded media.
The complete ONNELLAB Studio inventory must be rechecked immediately before
hash-bound intent and a single upload. No private draft counts as scheduled.
Persist the assigned video ID, selected timezone and actual schedule readback;
verify public state after the approved release time. A missing or ambiguous
upload result requires reconciliation of the existing video before any retry.



## Reviewed Melivra Albums guide — 2026-10-19

`data/screenshot_guides/melivra-albums-20261021.json` is an independent exact
contract for the October 21, 09:00 Asia/Seoul slot. It uses only Android English
`2.png` from the same genuine emulator capture set as the earlier Favorites
guide, with a different screen and question: how to browse the album library.
The selected PNG hash is independently pinned; original Favorites, Quivra,
ClipNest and Aligna manifests and receipts are unchanged.

All 240 lib files and the capture harness were compared between capture source
1341678a676ce9a2dc34888f271f1e4809182851 and reviewed release source
6314b685a41c690e8ccd9a080c095078ebb0db10. Only app_env version/build
defaults differ (1.0.6+142 to 1.0.7+144). Live Google Play About this app showed
public 1.0.7 on October 19. This is source parity, not signed-binary attestation.

Rights review inspected the harness: cover art is original procedural circles
and horizon paths; names are original demo metadata; WAV fixtures are valid
zero-filled PCM silence. The video has no audio stream. The full screenshot is
fitted uniformly to 621x1380, with no crop, UI retouch, motion or fake taps.
It only identifies titles/covers and displayed track counts/total lengths.
Existing still-screen disclosure, exact 450-frame encoding and bounded two-thread
renderer are retained. Every manifest leaf is fail-closed and covered by tests.

Papira was checked first but held: live Apple public 2.0.1 versus pinned fresh
capture source 2.0.3+10, with visible reading-style card/header changes and no
verified released-screen parity. Its capture integrity is not release approval.
Segra's current manifest still explicitly describes test-host renders rather
than genuine emulator/simulator captures. Neither is silently substituted into
the approved genuine-capture format. No Papira upload intent was created.

Before upload, the parent must reconcile the complete target-channel inventory
for this exact topic/title and preserve the same hash-bound intent across retries.
Prepared media and a planned slot are not a scheduled receipt.

## Papira home-screen guide (2026-10-23)

`papira-start-20261023.json` is an independent exact Papira contract, not a
replacement for any managed-recording or prior screenshot-guide gate. It uses
only `assets/store_promo/raw/android/en/01.png` at reviewed Papira commit
`dcfd66693b4bc283356907574c59f90026dacbe7`, SHA-256
`497e31dc4f2ed3db0295b79da8bddbe42616babb1f112e3a039c313bdc04fa7a`.
The 1080x2400 real Android emulator home screenshot is uniformly fitted in full.
The capture fixture records this empty home before injecting a sample project;
there are no user manuscripts, photographs, third-party artwork, or audio.

The source identity is 2.0.3+10 at
`f347cefeb75f83752d0d449d039912a5d7479984`. Comparison to the reviewed commit
shows no runtime `lib/` or selected Android PNG changes. The October 20 store
snapshot records public Android 2.0.3; the October 20 live Play inspection
confirms the ONNELLAB purchase listing, October 16 update, and current features,
but did not expose a version number. These are distinct evidence sources.
The iOS listing remains 2.0.1 and is not promoted by this Android-only guide.
No exact signed-public-build capture attestation is claimed.

The guide explains Create a book versus Convert TXT without showing a tap,
conversion, output, or speed demonstration. The source and final frames must be
reviewed; persistent disclosure, Android-only CTA, 15 seconds/450 frames,
1080x1920 H.264/yuv420p, and no audio are required. Rendering uses only existing
free cloud Python/Pillow/ffmpeg/ffprobe, two encoder threads and a 180-second
encoder timeout. CLI validation does not authorize upload. Publication requires
independent review, current duplicate reconciliation, durable intent, and a
separate actual Studio scheduling receipt; a render is not a scheduled video.


## Reviewed TagWeaver Extra Tags and VaultXT snapshot dates — 2026-10-25

The owner approved existing free dot-cloud Python/Pillow/ffmpeg/ffprobe for the
October 26 and 28 09:00 Asia/Seoul slots only. No installs, paid services,
separate Work/Codex task, user computer or legacy publisher is involved.
`tagweaver-extra-tags-20261026.json` and `vaultxt-snapshot-dates-20261028.json`
are separate exact contracts with exhaustive leaf-mutation tests. Existing
contracts, published media and managed-recording gates remain unchanged.

TagWeaver uses actual Android Extra Tags raw 04 from capture source
826031a5d36044ba38b96c1a69807257682c5281 (2.5.4+98), retained at reviewed
8e813af546731dbcf893b4ca1d7f0b4c47faeff6. The independently reviewed unchanged-screen
reuse record targets product source 0592417612d222306d37e374136e51706444fd46,
2.5.6+100. Live Play About showed public 2.5.6 on October 25. Explain the
field names and sample values only; demo ISRC/copyright values are not evidence
of rights to a recording. No navigation, edits, deletion or saved result is shown.

VaultXT uses actual Android raw 04 from capture source
f17646a0a9452a3dd16510e42b1498db49e80a41 (2.0.2+68), retained at reviewed
e5909c0f81eb6072a6aa419d4d8c52f0938b20d4. All 128 VaultXT lib files, Android
runtime, dependency lock and capture test are unchanged. Shared text-engine
context-menu code changed, but the selected SnapshotListSheet and its displayed
state did not; no context toolbar is shown. This is independently reviewed
screen-specific parity, not signed-release-binary equivalence. Live Play About
showed public 2.0.2. The original repository sample and two seeded snapshots
contain no user data. Explain creation-date metadata only, not a preview of
older content or completed restoration. Preserve the original green border.

Both original 1080x2400 images are uniformly fitted in full at 621x1380, with
persistent still-screen/demo disclosure, no audio, synthetic taps or crop.
Output remains 15 seconds, 450 frames, H.264/yuv420p, 1080x1920 at 30 fps.
Two encoder threads and a 180-second timeout remain enforced. Actual decoded
frames and source-region equality require checks in addition to independent
visual/claims review. A preparation or render is never a publication receipt.
Save final videos to Library, reconcile all target-channel content, durably
record manifest/video hashes before a single browser upload, and separately
read back channel, video ID and Seoul schedule. Uncertain outcomes must be
reconciled before retry. No new login/security/external-link verification is
included in this exception.

