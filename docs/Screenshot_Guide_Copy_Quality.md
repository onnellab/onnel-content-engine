# Screenshot-guide copy and layout quality

This is a production-preparation improvement, not a new publisher, format
allowlist, AI service, or permission to regenerate an existing upload.
The reviewed per-guide source, rights, hash, release, disclosure and scheduling
contracts in `Screenshot_Guide_Pipeline.md` remain authoritative.

## Editorial sequence for the next independently reviewed guide

1. Choose one concrete user question supported by a released app's visible UI.
   Put the question in the title; avoid vague benefit claims or keyword lists.
2. Give the direct answer in the opening caption and first description sentence.
   Example: "On Playlists, find New Playlist." This identifies a control; it
   does not claim the video demonstrates a tap or successful playlist creation.
3. Show the genuine, source-verified app screenshot and explain only visible
   controls or reviewed facts. Keep the whole screenshot and persistent
   still-screen/demo-data disclosure. Do not simulate typing, taps, playback,
   saving, conversion or performance, and do not replace UI with stock footage.
4. End with the correct app/platform and a short description-link direction.
   Preserve the exact verified store URL in metadata. A URL saved as text is
   not proof that YouTube makes it clickable. Do not claim an unverified release.

These are editorial roles, not a requirement to add a fourth slide or alter
the current 15-second / three-slide contracts. Each topic needs a materially
different useful explanation. Human review must judge whether the opening
actually answers the question; a keyword or question-mark check cannot do that.

## Implemented checks and their limits

The existing renderer now checks changing heading + caption copy before
allocating the output or invoking the encoder. The conservative English-only
house threshold is 20 characters/second (including the separating space) and
at least two seconds per slide. These are authoring heuristics, not universal
accessibility standards or proof of comprehension. Existing contracts retain
their reviewed five seconds per slide. Persistent branding and disclosure are
not counted again in this changing-copy heuristic and still need visual review.

Actual font glyph bounds must remain inside the existing canvas margins and
at least eight pixels clear of the full screenshot border and other labels.
No automatic font shrinking, truncation, repositioning or screenshot cropping
is introduced. Text and screenshot pixels remain unchanged for accepted legacy
contracts. The render evidence records the timing heuristic and layout checks.
It explicitly leaves `player_overlay_verified=false`: these canvas margins
are NOT a guarantee against YouTube's device-dependent controls or captions.
Inspect the complete rendered video and the player presentation separately.

`prepare_caption_lines` is a draft-only helper accepting an actual-font pixel
measurement callback. It wraps at words into at most two lines by default,
rejects overlong words or excessive lines, and never rewrites a manifest.
Use it to prepare shorter copy alternatives. The current fixed renderer still
expects a single line for each heading/caption. A multiline production layout
requires a new reviewed layout/contract and visual validation; do not paste
newlines into an existing guide or silently modify an already scheduled video.

Run the existing screenshot-guide tests, including
`tests/test_screenshot_guide_copy_quality.py`. Unit tests with fixture images
or mocked encoders are not evidence of actual app pixels, an encoded final
video, source rights, Studio scheduling or public release. Full-frame review,
exact original-image checks and existing ffprobe checks remain required.

## Scope, cost and reference

MoneyPrinterTurbo was reviewed as a workflow reference:
https://github.com/harry0703/MoneyPrinterTurbo
No dependency, provider integration, external request, subscription login,
automatic uploader or third-party implementation is added by this change.
The original project is MIT, but its service and media licenses are separate.
If code is copied later, preserve its required copyright/license notice.

Narration and background music remain inactive. Adding either needs verified
rights, cost, an updated reviewed format contract and actual audio QA. Do not
infer commercial rights from a service being labelled free. Existing silent
outputs and the one browser scheduling path are preserved, including durable
intents, duplicate reconciliation, video IDs and uncertain-upload handling.

YouTube policy references (reviewed 2026-11-08):
- https://support.google.com/youtube/answer/1311392
- https://support.google.com/youtube/answer/14328491

Repeated low-value templates are not made monetization-eligible by automation
or a stock-media license. AI-assisted scripts and captions do not by themselves
require the same disclosure as realistic synthetic scenes. Keep factual
still-screen disclosures independent from YouTube's AI-use setting.
