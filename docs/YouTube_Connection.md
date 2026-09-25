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

## Operator setup on the worker Mac

The deployed dashboard has a **YouTube · Shorts** panel above search/filter controls.
Choose **이 Mac에서 YouTube 연결** or **연결 상태 · 테스트** on the Mac that will run
recording and uploading. These links open `ONNELLAB YouTube Connect.app` through the
registered `onnellab-content` scheme. A phone/other computer cannot configure this Mac's
Keychain through the public page; the helper belongs to the machine where it is opened.

This Mac has the helper installed in `~/Applications/ONNELLAB YouTube Connect.app`.
For a different Mac, update the repository and run once:

```sh
cd ~/Projects/onnel-content-engine
python3 -B scripts/install_youtube_connect.py
```

The local screen includes the Google Cloud setup links. Enable YouTube Data API v3,
configure the OAuth consent audience, create a Desktop OAuth client, and import its JSON
**only into the local page**. Enter the independently obtained UC-prefixed ONNELLAB channel
ID, not a channel name or @handle. Complete Google login/consent personally. Do not put the
JSON or tokens into chat. The helper verifies the channel before storing the whole bundle;
there is no refresh-token copy/paste step. Keep the original downloaded JSON private.

The **연결 테스트** action refreshes credentials and reads the channel. It does not upload
or prove that Google has lifted a project's private-upload restriction. Testing-mode grant
expiry and YouTube API audit restrictions are separate activation issues. The helper closes
after twenty minutes; the worker does not require its browser page or server to stay open.

## Scheduled execution contract

The existing ONNELLAB Shorts automation remains Monday/Wednesday/Friday around 09:00
Asia/Seoul. Its prompt now calls the shared Keychain provider and performs a connection
check before expensive recording/rendering. It never exports credentials, asks for a
Keychain password, starts interactive OAuth, or silently switches accounts during a run.
A missing/revoked/locked grant reports a safe blocked reason and points to local setup.
It preserves the no-human-per-video-review policy and reconciles uncertain uploads before
creating anything new. Remote Desktop access in a future scheduled run remains a runtime
capability to check, not a completed verification claim. If device ping and file access
succeed but a short direct terminal/filesystem call is absent from the device-side recent
history, treat that event as a transient pre-dispatch failure and retry the smallest
equivalent direct action exactly once before declaring Remote Desktop blocked. Keep
`readiness` and `youtube-check --execute` as separate direct commands. A single recovered
pre-dispatch refusal must not disable the recurring Shorts task or trigger any Desktop
Commander security/configuration change.

Use already configured persistent production asset/queue paths. For a new installation,
the documented defaults are `~/Library/Application Support/ONNELLAB/content-engine/video-assets`
and `~/Library/Application Support/ONNELLAB/content-engine/video-state`, with private access.
Do not use the temporary rendering/proof queues from implementation tests for production.

## Verification and remaining activation checks — 2026-09-21

Native macOS Security.framework verification used a randomly named isolated test Keychain
item, never the production account: create, read, atomic replacement, separate Python
worker-process read, exact-item deletion and absence after cleanup all passed without
printing a credential payload. The actual production credential existence check returned
not configured. The signed launcher installed and opened the custom-scheme local console;
its loopback health instance and 0600 private session file were verified.

Real Chrome testing with an isolated in-memory store and fake Google transport exercised
Desktop JSON selection, PKCE authorization navigation, the callback/redirect, channel status,
read-only recheck and rejected reduced permissions. No request reached Google. Browser
storage remained empty; viewport widths 390, 768 and 1280 had no horizontal overflow;
desktop and mobile screenshots were reviewed. Fake-provider success is not a real account
connection or a live YouTube upload.

Known display-only limitation: after a failed check, changing the local console language
can redraw a previous client-side success label. Reload the local page and press connection
test again to read server state. The server clears its previous verified result on failure,
and the worker does not trust browser labels. A follow-up UI state patch was blocked by the
tool safety check and was not applied; no workaround was used to execute that request.

No ONNELLAB OAuth grant, actual YouTube account verification, or live upload has been
completed without the owner's Desktop client and consent. These are activation steps.


## Superseding dual-brand contract — 2026-09-21

The channel manager now supports ONNELLAB and Aether Inn as independent local
contexts. Use the existing dashboard launcher and select the intended brand at the
top of the local page. Its connection flow now requests the additional Analytics
read scope. Previous singleton/session-path and two-scope descriptions above are
historical. See `YouTube_Brand_Workspace.md` for current session paths, reporting,
cache expiry and isolation. Existing app-video upload grants remain usable without
Analytics; reconnect to enable reports. The prior language-switch display issue
was fixed in dd676396 and must not be represented as a current limitation.
