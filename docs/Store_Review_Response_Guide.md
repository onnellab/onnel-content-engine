# Store Review Response Guide

## Purpose

The dashboard can show App Store and Google Play customer reviews and create a
reply draft from the repository-managed templates.

The workflow is:

1. Synchronize reviews from the official store APIs.
2. Run `python3 scripts/triage_store_reviews.py` to create the fact-grounded
   action snapshot.
3. Rebuild the dashboard.
3. Open **Store review replies**.
4. Select **Generate reply draft**.
5. Verify the facts and tone, edit if needed, and copy the reply.
6. Publish the reply in App Store Connect or Google Play Console.

Reply publication is manual by default. A generated draft must not be posted
without either a specific human approval or an explicit owner-approved standing
automation policy.

### Owner-approved scheduled reply exception

On 2026-09-24 the owner authorized the daily operations automation to reply
automatically to newly synchronized text reviews. This standing approval applies
only to concise public developer replies that follow the existing ONNELLAB reply
tone and the fact-grounding rules in this guide. The automation must use the
review language where practical, may consult prior developer replies for the same
app and issue type as tone precedents, and must ground product or pricing claims
in the current repository facts. It must not invent a fix, cause, release date,
refund result, entitlement, price, or future feature.

Rating-only records are never auto-replied. Security, privacy, billing-dispute,
data-loss, or otherwise case-specific reviews may receive only a factual
acknowledgement and safe support direction unless repository evidence supports
more. The automation must never delete, hide, moderate, or alter the review.
Each automatic reply still uses the durable approval/publisher audit path and
must record that it was approved by the owner standing policy. After publication,
reviews are synchronized again so the dashboard reflects the store-observed
developer reply. Any uncertain publication result is retried only through the
same durable record; never create a duplicate reply record to escape uncertainty.

Selecting **Approve & queue** in the dashboard records the exact edited reply,
review ID, platform, timestamp, and approval actor in
`data/store_review_approvals.json`. This requires the dashboard GitHub token
and creates a repository commit. It does **not** publish the reply: queued
records remain a deliberate boundary until the separate store publisher is
implemented and enabled.

## Publishing one approved reply

The publisher is deliberately one-at-a-time. Dispatch **Publish Approved Store
Review Reply** and enter the exact `approval_id` plus `PUBLISH`. It publishes
only a `queued` record, then changes that record to `published` with the store
response ID. Running the script without `--confirm-publish` is always a dry
run. Google Play replies are limited to approximately 350 characters.

`data/store_review_triage.json` is an audit snapshot. It groups repeated
reports, cites the applicable `docs/operations/*_FACTS.md` lines, and may
create an unverified GitHub issue draft. It never writes to GitHub, a store,
or a deployment system. Approve and create any issue in the relevant app
repository after verifying reproduction and privacy-safe wording.

## Custom AI drafts

Run `python3 scripts/generate_ai_review_drafts.py` to create a review packet,
then give it to Codex with `prompts/codex_review_replies.md`. Codex writes the
tailored drafts to `data/store_review_ai_drafts.json`; they still require the
normal approval queue. This uses the ChatGPT/Codex subscription workflow and
does not require an API key.

For a non-Korean review, the approval dashboard shows both the localized
review/reply and their Korean translations. Both translations are required
before **Approve & queue** is enabled. They are approval context only: the
approval queue and store publisher receive only the localized `reply`, never
either Korean translation.

## Credentials

For Apple, provide a newly issued App Store Connect API key:

```text
APP_STORE_CONNECT_KEY_ID
APP_STORE_CONNECT_ISSUER_ID
APP_STORE_CONNECT_PRIVATE_KEY_BASE64
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64
GOOGLE_PLAY_REPORTS_BUCKET
```

The dashboard converts the pasted PEM to single-line Base64 so the ignored env
file and GitHub Actions can transport it safely. `sync_store_reviews.py` decodes
it in memory and creates a 19-minute ES256 JWT at runtime. It also accepts
`APP_STORE_CONNECT_PRIVATE_KEY` directly and `APP_STORE_CONNECT_TOKEN` as a
temporary override. Do not commit tokens, API private keys, service-account
JSON, review exports, or temporary authentication files.

For Google Play, paste the service account JSON into the dashboard. The form
converts the complete JSON to single-line Base64. At runtime the sync script
creates a one-hour OAuth assertion with the `androidpublisher` and
`devstorage.read_only` scopes and exchanges it for an access token.
`GOOGLE_PLAY_ACCESS_TOKEN` remains available as a temporary override.

The reviews API only returns reviews created or modified during the previous
week. The lifetime report bucket is therefore required for dashboard syncs.
Copy the Play Console review report URI (`gs://pubsite_prod_.../reviews/`) into the
dashboard's **Play lifetime review reports bucket** field. The service account
needs the account-level **View app information and download bulk reports
(read-only)** permission (`CAN_VIEW_NON_FINANCIAL_DATA_GLOBAL`), not only
per-app review access. Google notes that permission changes can take up to 48
hours to propagate. The sync then merges every monthly review CSV in that
bucket with the recent API response. A sync without this bucket, or without
permission to read it, fails with the exact missing permission instead of
silently publishing a partial review list. Local diagnostics may explicitly
opt into a partial sync with `--allow-recent-only`.

The dashboard's **Store review connection** panel can save all five required
connection values
directly to GitHub Actions Secrets. It obtains the repository's Actions public
key, encrypts each value in the browser with libsodium sealed-box encryption,
and sends only the ciphertext to GitHub's Secrets API. Plaintext credentials
are never sent as workflow inputs or written to generated HTML, CSV, or Git.

The GitHub token connected to the dashboard must have repository access for:

- Actions: read and write
- Contents: read and write
- Secrets: read and write

Select **Encrypt and save to GitHub Secrets**, or enter all credentials and
select **Sync reviews now** to save the encrypted secrets and dispatch the
workflow in one step.

The local env and CLI sync remain available as a fallback:

```bash
python3 scripts/run_with_local_env.py -- python3 scripts/sync_store_review_secrets.py
```

Run after all five values are configured:

```bash
python3 scripts/sync_store_reviews.py
python3 scripts/build_manual_publish_site.py
```

The Apple key needs access to customer reviews in App Store Connect. The Google
service account must be linked in Play Console and have permission to view
reviews for the target apps.

The `sync-store-reviews.yml` workflow runs daily and can also be started from
the dashboard with **Sync reviews now** after the GitHub token is connected.
The workflow fails clearly when any required store secret is missing instead of
silently reporting success with every store skipped.

Official API references:

- Apple App Store Connect API: Customer Reviews and Customer Review Responses
- Google Play Developer API: `reviews.list`, `reviews.get`, and `reviews.reply`

## Reply policy

- Thank the reviewer without copying their full review into the response.
- Acknowledge a problem without claiming it is fixed before verification.
- Do not promise a release date, refund, or feature.
- Do not ask for email addresses, account identifiers, order numbers, document
  contents, tokens, or other personal data in a public review.
- Direct case-specific investigation to the official support channel.
- Keep replies concise and use the review language when Korean or English is
  available; use English as the fallback.
- Treat every generated response as a draft that requires human review.

## Data

Synchronized reviews are stored in `data/store_reviews.csv`. This is operational
dashboard data, not a credential store. The dashboard does not display reviewer
names and renders review text with `textContent` rather than HTML.

## Current review reconciliation

`data/store_reviews.csv` is the current authenticated review snapshot, not an
append-only history or the store's aggregate star-rating count. Google monthly
reports discover review IDs (including modern `?reviewId=` links); the recent
API is only an additional discovery source. Every known real Google review ID
is refreshed with `reviews.get`, including old reviews absent from the last-week
list. The current response body and developer reply replace cached values.
Apple pages are fully exhausted before reconciling its snapshot.

Google 404/410 responses remove the record from the current snapshot but do not
establish who removed it or why. Historical report-only rows with no current ID
are **unverified**, not declared deleted. Removed records and superseded aliases
are retained in `data/store_reviews_archive.json`; they do not feed pending reply
drafts. Archived real Google IDs are rechecked and can reappear. 403, rate limits,
transient failures or malformed responses abort before writing a new snapshot.
`data/store_review_sync_status.json` records per-store checks, source coverage,
review counts and the CSV checksum. Not-released apps are explicitly skipped.

For a read-only investigation, run **Audit Store Review State** from GitHub
Actions. It uses the existing store secrets and uploads a three-day audit
artifact; it never posts replies or changes dashboard data. Do not put tokens,
private keys, service-account JSON or reviewer identities into audit output.
