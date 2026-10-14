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

## Notify-first policy (2026-10-14)

The owner's 2026-10-14 instruction supersedes the 2026-09-24 standing scheduled
reply exception. All new reviews are first presented to the owner in their
existing assistant chat, with app, store, rating, original review text, and date.
A generated draft, a legacy queued/failed record, a positive rating, or any
standing policy is **not** approval. Do not publish any reply until the owner
explicitly approves that exact review and reply text.

Review collection, triage, unrelated operations, and schedules remain enabled.
The daily worker prepares a durable notification outbox and never dispatches
**Publish Approved Store Review Reply**. The compatibility command
`python3 scripts/queue_standing_store_review_replies.py` always returns an empty
`queued` list. It quarantines pending legacy approvals as
`awaiting_owner_approval`, retaining all earlier audit fields. Published history
is unchanged. Failed or uncertain publication attempts are never auto-retried.

### Delivering owner notifications

Read `data/store_review_notifications.json` and the current synchronized review
snapshot. Send only still-current `pending` items to the owner's existing chat.
Each notification ID binds the store/app/review and review content. Changes to
review content create a new ID; removed, superseded, or replied records are not
new pending notifications. The outbox and the daily result are preparation
receipts, not evidence that the owner has been notified.

After an accepted user-message send, verify the returned owner-chat message
(`channel=chatgpt`, assistant author) and record its exact message ID:

```sh
python3 scripts/queue_standing_store_review_replies.py \
  --ack-notification NOTIFICATION_ID --delivery-reference OWNER_CHAT_MESSAGE_ID
```

A connector-based reporter may equivalently change only the matching row to
`status=notified`, set `notified_at`, `delivery_channel=chatgpt` and
`delivery_reference`, and update the
outbox `updated_at`, using a content-SHA lease. Retain all other rows and fields.
Commit the receipt before the next reporting pass. Search existing owner-chat
messages by review/notification identity after an interrupted or uncertain send;
never blindly resend or mark a prepared notification as delivered. This receipt
is not a reply approval. Do not email the reviewer or contact any third party.

### Publishing one owner-approved reply

Read the referenced owner-chat message and verify `channel=chatgpt`, human owner
author, and explicit approval of the exact review and localized reply. The reference
must be the tool-returned `Sentinel_` message ID or its unchanged canonical room
reference. Local logs, job/workflow IDs, draft IDs, or assistant-authored messages
are not owner approval. Syntax/hash validation is only a safety check and cannot
authenticate a message; the operator must verify it through the messaging source. Then:

```sh
python3 scripts/store_review_approvals.py REVIEW_ID \
  --reply "Exact owner-approved reply" --approver "owner_explicit_chat_approval" \
  --approval-reference OWNER_APPROVAL_MESSAGE_ID
```

The command records a new approval type, source reference, timestamp, reviewed
content hash, and a SHA-256 binding of the exact target and reply. Old dashboard
queue records and standing-policy records deliberately do not satisfy this
contract. Until the dashboard supports this new evidence contract, use the
approval CLI after verified owner confirmation; its legacy button alone cannot
publish a reply. Never fabricate an approval reference or treat it as a token.

Dispatch **Publish Approved Store Review Reply** manually with the new exact
`approval_id` and `PUBLISH`, or run the publisher with `--confirm-publish`.
The publisher validates owner evidence and current review content before even
loading credentials and validates again at each Android/iOS write boundary.
Changed review content, changed reply text, missing proof, legacy approvals,
already-replied reviews, and failed/published records fail closed. Google Play
replies must be at most 350 characters. A successful store receipt changes only
that approval to `published`; synchronize the store again to verify the reply.

`data/store_review_triage.json` remains an audit snapshot. It never authorizes a
reply, issue, pull request, code change, merge, or deployment by itself.

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
APP_STORE_CONNECT_READ_KEY_TYPE
APP_STORE_CONNECT_READ_KEY_ID
APP_STORE_CONNECT_READ_ISSUER_ID
APP_STORE_CONNECT_READ_PRIVATE_KEY_BASE64
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64
GOOGLE_PLAY_REPORTS_BUCKET
```

The dashboard converts the pasted PEM to single-line Base64 so the ignored env
file and GitHub Actions can transport it safely. `sync_store_reviews.py` decodes
it in memory and creates a 19-minute ES256 JWT at runtime. Set the key type to
`individual` (the Ops default) or `team`. Individual requires Key ID and private
key and uses `sub=user` without `iss`; any issuer is ignored. Team additionally
requires Issuer ID and uses `iss` without `sub`.

Ops uploads only `APP_STORE_CONNECT_READ_*` secrets, including Issuer ID only
for Team. Read jobs fall back to legacy `APP_STORE_CONNECT_KEY_ID`,
`APP_STORE_CONNECT_ISSUER_ID`, and `APP_STORE_CONNECT_PRIVATE_KEY_BASE64` or raw
`APP_STORE_CONNECT_PRIVATE_KEY` only when READ configuration is absent. A partial
READ configuration fails without borrowing legacy fields. Release/upload secrets
remain separate. Individual keys cannot use Provisioning, Sales & Finance, or
notaryTool; the internal processing-status collector retains release credentials
because its build lookup uses `/bundleIds`. `APP_STORE_CONNECT_TOKEN` remains a
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

The local daily worker dispatches `sync-store-reviews.yml`; it can also be started from
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

