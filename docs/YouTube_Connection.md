# YouTube connection — ONNELLAB worker identity

## Approved scope

The YouTube settings extension adds connection/setup UI to the existing dashboard.
It does not change article publishing, app release status, rendering rules, upload
frequency, or require per-video human review. Google's initial account login and
consent remain a one-time interactive step; they cannot be replaced with an API key.

## Shared credential provider

`short_video_credentials.py` stores one complete bundle in the current macOS user's
Keychain: service `com.onnellab.content-engine.youtube`, account `onnellab`. Client
ID, client secret, refresh token and independently supplied expected channel ID are
saved atomically only after OAuth scopes and the exact channel are verified. Secrets
never appear in command arguments, logs, generated pages, Git or browser storage.

`YouTube()` and the worker use Keychain by default. A missing/locked/denied/corrupt
Keychain fails closed and never falls back silently to an unrelated channel. Workers
never prompt for a Keychain password or unlock it. Local setup may allow the normal
macOS access prompt in response to the user's explicit connection action.

For intentionally configured Linux/CI environments only, select
`ONNELLAB_YOUTUBE_CREDENTIAL_SOURCE=environment` and provision the existing four
`YOUTUBE_*` values securely. Values are never combined across credential sources.
Tests explicitly inject a fake environment/store and never use production secrets.

Readiness performs an attribute-only existence check. It does not load credentials,
refresh tokens, contact Google, or claim that configuration equals a working upload.
`youtube-check --execute` uses the same provider as publication and verifies access.

## OAuth contract

Import a Google OAuth **Desktop app** client JSON, and supply the ONNELLAB channel
ID from YouTube's advanced account settings. The required scopes are only
`youtube.upload` and `youtube.readonly`. The callback is on `127.0.0.1` at a random
port. PKCE S256, random state, a 10-minute expiry and one-use callbacks are required.
Imported endpoints are never trusted; token/channel calls use fixed Google HTTPS
endpoints without redirects. A denied, expired, replayed, wrong-channel, incomplete
scope or missing-refresh-token attempt cannot overwrite a working connection.

Connection validation is read-only: it does not upload a trial video. A successful
OAuth check does not remove Google's API-project private-upload restriction or prove
that a public upload is possible. Google Cloud consent testing mode may also shorten
refresh-token lifetime. Resolve those project settings before unattended production.

Sources: Google installed-app OAuth documentation at
https://developers.google.com/identity/protocols/oauth2/native-app and YouTube
channel verification at https://developers.google.com/youtube/v3/docs/channels/list.
