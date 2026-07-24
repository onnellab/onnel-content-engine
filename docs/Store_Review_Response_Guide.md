# Store Review Response Guide

## Purpose

The dashboard can show App Store and Google Play customer reviews and create a
reply draft from the repository-managed templates.

The workflow is:

1. Synchronize reviews from the official store APIs.
2. Rebuild the dashboard.
3. Open **Store review replies**.
4. Select **Generate reply draft**.
5. Verify the facts and tone, edit if needed, and copy the reply.
6. Publish the reply in App Store Connect or Google Play Console.

Reply publication is intentionally manual. A generated draft must never be
posted without human review.

## Credentials

For Apple, provide a newly issued App Store Connect API key:

```text
APP_STORE_CONNECT_KEY_ID
APP_STORE_CONNECT_ISSUER_ID
APP_STORE_CONNECT_PRIVATE_KEY_BASE64
GOOGLE_PLAY_ACCESS_TOKEN
```

The dashboard converts the pasted PEM to single-line Base64 so the ignored env
file and GitHub Actions can transport it safely. `sync_store_reviews.py` decodes
it in memory and creates a 19-minute ES256 JWT at runtime. It also accepts
`APP_STORE_CONNECT_PRIVATE_KEY` directly and `APP_STORE_CONNECT_TOKEN` as a
temporary override. Do not commit tokens, API private keys, service-account
JSON, review exports, or temporary authentication files.

The dashboard's **Store review connection** panel prepares the env block and
commands. It saves only Key ID and Issuer ID in browser storage; the private key
is cleared on refresh. After copying the env block into the gitignored local env
file, synchronize the three Apple values to GitHub Actions:

```bash
python3 scripts/run_with_local_env.py -- python3 scripts/sync_store_review_secrets.py
```

Run:

```bash
python3 scripts/sync_store_reviews.py
python3 scripts/build_manual_publish_site.py
```

The Apple token needs access to customer reviews in App Store Connect. The
Google token needs the `androidpublisher` scope and Play Console permission for
the target apps.

The `sync-store-reviews.yml` workflow runs daily and can also be started from
the dashboard with **Sync reviews now** after the GitHub token is connected.

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
