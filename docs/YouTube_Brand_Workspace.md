# YouTube brand workspace — 2026-09-21

## Implemented

The public dashboard separates ONNELLAB app demos and Aether Inn music. The
existing installed launcher opens the local channel manager. Select the intended
brand there BEFORE importing a Desktop OAuth client and the independently obtained
UC-prefixed channel ID. Both profiles have separate Keychain items, loopback ports,
CSRF tokens, OAuth state/PKCE attempts and session files. Switching brands creates
at most one additional in-process loopback context. No OS launcher change or new
background daemon is required. Closing the root helper closes both contexts.

`python3 -B scripts/short_video_connect.py open --profile aether_inn` also opens the
Aether-specific local console. Existing launcher URLs remain unchanged. The local
manager requests upload, channel read and analytics read scopes. Legacy grants
without analytics can still serve the existing upload worker; reconnect in the
local manager to grant the reporting scope. Failed OAuth never overwrites a valid
credential bundle. Complete Google login and consent personally; do not paste keys
or tokens into chat or Git. Enable both YouTube Data API v3 and YouTube Analytics API.

The local dashboard displays real channel totals, reporting-period views, watch
hours, subscriber gains/losses, top-100 video metrics, and up to 100 latest top-level
comments. Reply counts are shown, not full reply bodies. These are bounded reports,
not exhaustive comment collection. No automated replies or moderation is enabled.

## Scheduled read-only collection

Run once per profile on the same authorized worker Mac:

```sh
python3 -B scripts/youtube_report_run.py --profile onnellab sync
python3 -B scripts/youtube_report_run.py --profile aether_inn sync
```

The worker uses the shared verified-channel provider, not new OAuth/token exchange
code. The reporting module accepts an already-verified profile client and only
performs allowlisted GET requests. Authentication and foreign-channel failures
block the report. Missing Analytics permission or disabled comments produce partial
results, never fabricated zeroes. Requested reporting dates use YouTube's Pacific
reporting timezone; the last actual reported day is shown separately. Subscriber
counts may be rounded by the API. No precise live count is inferred from deltas.

Reports stay under `~/Library/Application Support/ONNELLAB/content-engine/youtube-reports`
with 0700 directories and 0600 files, one file per profile. Standard output contains
status only, not comments or credentials. Reports expire after 24 hours; reading an
expired report removes it. Failed refreshes and disconnection clear the affected
profile only. Successful reconnection also clears its old report. The public static
page does not automatically receive private analytics. Use the local manager on the
Mac, or its existing in-tab file import; no public report or token is committed.

## Deployment regression repair

The previous deployment mixed stale homepage/site and pricing snapshots into a UI
change. The affected embedded `site-data` and `pricing-data` were restored without
reverting the music workspace or other homepage changes. For YouTube-only UI work,
use `scripts/refresh_youtube_workspace.py <current-dashboard.html>` rather than
rebuilding all unrelated state from an outdated local homepage checkout. The helper
replaces only the single workspace span. Regression tests preserve other data blocks
byte-for-byte. Pull and inspect both repositories before deployment.

## Still separate from reporting

Profile-bound reporting and connection UI do not prove public upload eligibility.
The existing-master compilation renderer and durable Aether-only uploader are now
implemented in `aether_compilation.py`; see `Aether_Inn_Compilation.md`. New Suno
generation, new AI artwork generation and calibrated audio-originality evaluation
are still unimplemented and must not be substituted with metadata similarity. Never use
app-Shorts job schemas or default ONNELLAB credentials for music. No Suno API schema
has been inferred from its login page. No paid generation call has been made.

Official references checked 2026-09-21:
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/youtube/analytics/channel_reports
- https://developers.google.com/youtube/v3/docs/commentThreads/list
- https://developers.google.com/youtube/v3/docs/channels
- https://developers.google.com/youtube/terms/developer-policies


## Final local verification

The focused suite passed 182 tests: 143 existing short-video tests, 16 brand
workspace tests, eight report-query/cache tests, seven compilation tests and eight
dashboard-integrity tests. A real local Mac manager was opened without Google
sign-in and inspected with Chrome at 390, 768 and 1280 px. Brand round-trip,
Korean/English state, unavailable metrics and layout passed with zero JavaScript
or resource errors. Both local contexts and the test browser were closed.
The provider report tests use offline fixtures, not live account analytics.
A final real FFmpeg fixture run also passed after media-format allowlisting, with
62 seconds of 1080p/30fps H.264/yuv420p/AAC output and 0/20/40-second chapters.
The duplicate decoded-audio guard rejected a repeated master. Test media stayed
in a temporary directory, were upload-ineligible, and were removed afterward.
