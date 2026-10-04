# YouTube activation handoff — Windows N, 2026-10-04

This is an operator handoff, not evidence that YouTube is connected or Shorts are
running. This audit read repository code and official documentation only. It did
not open an authorization screen, access the Mac, read/export tokens, create a
client, change grants, or activate a schedule.

## Current connection boundary

The expected app-demo channel is **ONNELLAB, `UCXyRedrldRBl9Y35nyWoTLg`**.
Aether Inn is a separate profile and must never supply app-video credentials.
The earlier inspected N process had none of the four required environment values;
this does not establish that no credentials exist anywhere on the machine.

The interactive setup shipped in this repository is **Mac-only**:

- `scripts/install_youtube_connect.py::install` requires `darwin` and builds an
  AppleScript application. Installing it on N is not a supported setup path.
- `scripts/short_video_connect.py::open_console` requires macOS Keychain; it also
  imports `fcntl`. WSL does not supply macOS Keychain or make this helper portable.
- `scripts/short_video_credentials.py::resolve_credentials` supports an explicit
  `environment` source on Windows. It consumes an already authorized complete
  bundle; it does not enroll an account, obtain consent, or securely persist a new
  Windows connection. No Windows interactive enrollment/store is implemented.

For N, first have the owner identify an **existing approved local** credential
provisioning mechanism for the scheduled process. It would supply
`ONNELLAB_YOUTUBE_CREDENTIAL_SOURCE=environment` and the four names
`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`,
`YOUTUBE_CHANNEL_ID` without exposing values. If none exists, a separately reviewed
Windows setup/storage implementation and user consent are prerequisites. Do not
copy Mac Keychain secrets, paste tokens into chat, use a public callback page, or
treat the environment adapter as a ready-made setup wizard.

## Exact scope contract: two, three, and the current four

All scope suffixes below have prefix `https://www.googleapis.com/auth/`.

| Path | Scopes | Meaning for activation |
| --- | --- | --- |
| Existing upload credential contract, `SCOPES` / `validate_bundle` | `youtube.upload`, `youtube.readonly` | Existing valid two-scope grants remain accepted for upload and exact channel verification. No Analytics reconnect is needed merely to restore this worker. |
| Upload plus Analytics reporting | The above plus `yt-analytics.readonly` | Additional report access needs the owner's consent. This is the historical three-scope documentation, not the current setup UI. |
| Current local manager, `SETUP_SCOPES` / `SetupServer` | All three plus `youtube.force-ssl` | Both connect and reconnect request all four. There is no scope-selection UI for upload-only or Analytics-only enrollment. |

`youtube.force-ssl` is broader than reading reports: it permits changes and
deletion involving videos, ratings, comments and captions. It is not required by
the two-scope upload contract. The current manager rejects a callback missing any
requested scope before saving; unchecking the extra scope is not a supported
upload-only setup workaround. Do not tell the owner that reconnect merely adds
Analytics. Preserve a working upload grant; approve reporting and broader access
separately, or review a narrower setup implementation before reconnecting.
[Official scope descriptions](https://developers.google.com/identity/protocols/oauth2/scopes#youtube)
and [Analytics report authorization](https://developers.google.com/youtube/analytics/channel_reports)
describe those distinct capabilities. No auth code or scope list was changed here.

## Screens the owner must personally inspect

These are instructions for a later explicitly approved setup. No screen was opened
in this audit, and a new client is not automatically needed.

1. In YouTube, use the profile menu to select the ONNELLAB channel. In **Settings →
   Advanced settings**, independently confirm the channel ID above; the channel
   name or handle is insufficient. Google says the primary owner can view these
   IDs. If another channel is selected, stop rather than adapting the expected ID.
   [Find the channel ID](https://support.google.com/youtube/answer/3250431?hl=en).
2. In the intended Google Cloud project, inspect **APIs & Services → Library**
   for YouTube Data API v3. Analytics reporting additionally needs YouTube Analytics
   API. Inspect **Google Auth platform → Branding, Audience, Data Access** for app
   identity, audience/test users, and the intended permission set. Do not enable an
   extra API, expand access, change publication status, or accept new terms as an
   implicit part of this read-only handoff.
   [Google Auth configuration](https://developers.google.com/workspace/guides/configure-oauth-consent).
3. Inspect **Google Auth platform → Clients** for an existing appropriate **Desktop
   app** client. The repository parser requires an `installed` client JSON, not a
   web client/API key. If client creation or download is needed, the owner must
   authorize it separately and keep the file local/private. A future N enrollment
   implementation must preserve the existing PKCE/state and loopback callback
   contract. [Installed-app OAuth](https://developers.google.com/identity/protocols/oauth2/native-app).
4. Only after a supported local setup path and exact scope set are approved,
   personally complete Google account selection, any offered channel selection,
   and consent. Check the app identity and every requested capability. Stop on an
   unexpected app, wrong channel, blocked/unverified flow, or broader permissions;
   do not bypass warnings. The repository's callback then checks
   `channels.list(mine=true)` against the independently supplied ID before saving.
   [Consent flow](https://developers.google.com/identity/protocols/oauth2/native-app)
   and [channel API](https://developers.google.com/youtube/v3/docs/channels/list).

External OAuth projects in **Testing** issue refresh tokens that normally expire
after seven days for these scopes; that is unsuitable evidence of durable unattended
access. Production consent configuration and Google's verification requirements
must be reviewed separately by the owner.
[Refresh-token rules](https://developers.google.com/identity/protocols/oauth2).
Successful channel verification also does not establish public upload eligibility:
uploads from unverified API projects created after 2020-07-28 are restricted to
private viewing until the project passes the required audit.
[YouTube upload restrictions](https://developers.google.com/youtube/v3/docs/videos/insert).

## After connection, before any recording or publication

Use the same credential provider and private state root as the intended scheduled
worker. A local presence/readiness result is not a live channel check. The existing
YouTube verifier refreshes access and reads the exact channel without uploading a
test video; run it only within the approved connection-verification scope.

Follow [Windows Shorts recovery](WINDOWS_SHORTS_RECOVERY.md): verified legacy-writer
fencing, existing-publication history migration, provisioned shared state branch,
private paths, resource ownership and a dry-run are still required. Keep
`data/video_rotation.json` disabled and unfenced until those facts are verified.
The shared ledger coordinates upgraded workers; it cannot stop an old Mac writer.
Connection success does not authorize new cadence, paid generation, or app releases.

## If Mac access and connection are later authorized

No Mac was inspected in this task. After confirming its worker/queue identity and
fencing the legacy schedule, verify its ONNELLAB connection and shared coordination
contract before assigning work. The current setup manager on that Mac still has
the four-scope limitation above; do not reconnect an existing grant casually.

Repository store evidence and scenario registrations currently indicate:

| App | iOS store evidence | Managed iOS scenario |
| --- | --- | --- |
| Quivra | Present | `quivra-conversion-flow` (quarantined: mocked core operation) |
| TagWeaver | Present | `tagweaver-core-edit-flow` (quarantined: mocked core operation) |
| VaultXT | Present | `vaultxt-log-inspection-flow` |
| Segra | Present | `segra-trim-flow` (quarantined: mocked core operation) |
| ClipNest | Present; iOS-only | `clipnest-saved-snippet-flow` |
| Aligna | Present | `aligna-preview-before-apply` |
| Papira | Present; iOS-only | Missing: repository and authentic capture harness must be established. |
| Melivra | None; Android-only | Not an iOS candidate. Android harness is source-prepared on a separate branch; execution and capture remain unverified. |

These registrations are not proof that recording works on a connected Mac. Check
the current store snapshot, source repository, owned simulator, and actual capture
markers before rendering. Do not invent recordings, supported platforms, usage
results, or popularity to fill rotation coverage.

Melivra source preparation: [`d5ad6433`](https://github.com/onnellab/melivra/commit/d5ad64330fa8cd91eefc8ea0cb970ef352d475e3). Its APP_ANCHOR prohibits Flutter/Dart commands on Windows/Linux; use an authorized compatible host with an explicitly selected disposable Android device for the remaining checks. This does not authorize access to the current Mac.

The follow-up [Android source audit](ANDROID_CAPTURE_SOURCE_AUDIT.md) found simulated processing in Quivra, TagWeaver and Segra capture targets. Their registered scenarios are disabled for both platforms. Source presence and UI screenshots do not prove actual conversion, tag writes or trimmed output. VaultXT real-file inspection and Aligna computed-name preview remain source candidates, not verified recordings.
