# Aether Inn and ONNELLAB — independent media operations

## User-approved scope, 2026-09-21

The user approved two separate YouTube brands, channel statistics and listener
comments, Aether Inn single-track production, and periodic approximately 30-minute
compilations. Preserve the existing educational article phases and the ONNELLAB
English app-demo Shorts worker. Per-video human approval is not a requirement.

## Implementation and activation are separate

ONNELLAB keeps its existing verified-channel OAuth provider. The attempted change
to the credential/OAuth/upload core was blocked by the tool security check and was
not applied or worked around. Aether Inn therefore MUST NOT use that provider,
its environment variables, queue, OAuth helper or resumable upload sessions.
Aether publication remains blocked until independently implemented and tested
profile-bound credentials and upload routing are available.

The new public dashboard section is navigation and documented workflow state only.
Private analytics and comments belong to the worker Mac, never generated public
pages or Git. Unconnected/unavailable metrics are null, not invented zeroes.
Channel totals and reporting-period data are distinct. Subscriber totals returned
by Data API can be rounded; reporting periods can lag. Comment keyword tags are
heuristics, not measured sentiment or evidence that a comment represents all users.

## Music source of truth

The supplied Library list(4).txt contains titles, style prompts and displayed
lengths. Preserve those strings (including the historical title ending in Style:).
These are NOT audio measurements, commercial-rights evidence or proof of a public
YouTube upload. Compare candidate titles/styles against every catalog row, but do
not represent text similarity as melodic originality or copyright clearance.

Master audio, artwork and rights metadata must be supplied through a private asset
manifest. The historical Windows path N:\개인\Aether Inn is not assumed to exist
on the Mac. No actual audio was located during initial repository inspection.

## Scheduled workers

The one-shot Aether worker keeps a durable private intent and bounded status record.
A single-track intent may be planned but cannot create paid Suno/image requests
until their official API contract, credentials and spending limits are configured.
A provider account login page is not enough to infer endpoints or a request schema.
No unofficial cookie scraping, CAPTCHA bypass or invented success records.

Compilations require complete local masters, artwork and explicit rights metadata.
Select whole tracks by a common theme. Target 30 minutes with a 60-second tolerance;
never stretch, loop or cut a song merely to hit 30:00. Two-second crossfades are
included in duration and chapter-start arithmetic. Recompute from actual ffprobe
measurements before rendering; catalog lengths are estimates only.

Render 1920x1080, 30 fps, H.264, yuv420p and AAC 256 kbps. Use at most two encoder
threads, bound the process lifetime, and stop only process groups owned by this run.
A completed local render is not a YouTube publication. Keep the publication gate
closed and report the exact unmet dependency. Never use the app Shorts uploader.

## Data and operational rules

Use ~/Library/Application Support/ONNELLAB/content-engine/aether-inn for private
state and assets. Never put media, credentials, comments or analytics snapshots in
Git. Source catalog metadata may be tracked. Do not delete, reset or reschedule
other development jobs. Scheduled runs may not have Remote Desktop available;
in that case report blocked rather than claiming the Mac worker ran.

Sources checked 2026-09-21:
- https://platform.suno.com/ (official API platform, authentication required)
- https://developers.google.com/youtube/analytics/channel_reports
- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/youtube/v3/docs/channels
