# Publishing Credentials

## Purpose

This document defines the environment variables required before real external publishing adapters are enabled.

Mock adapters do not require credentials.

---

## Social Platforms

### Bluesky

Required for the real Bluesky adapter:

```text
BLUESKY_HANDLE
BLUESKY_APP_PASSWORD
```

The adapter posts text, clickable URL facets, and external website card embeds.

### X

Required for the real X adapter:

```text
X_CLIENT_ID
X_CLIENT_SECRET
X_REFRESH_TOKEN
```

The adapter refreshes an OAuth 2.0 access token before posting generated text with the canonical URL. X website cards are expected to render from the canonical page's Open Graph and Twitter card metadata.

`X_ACCESS_TOKEN` may be kept locally for debugging, but long-running automation should rely on `X_REFRESH_TOKEN`.

Optional for local schedulers:

```text
X_REFRESH_TOKEN_FILE
```

When X returns a rotated refresh token, the adapter writes it to this file. Keep the file outside git or under `.tokens/`.

### LinkedIn

LinkedIn real API posting is intentionally unsupported for now.

Keep LinkedIn in manual or mock mode until account type and permission scope are decided.

---

## Syndication Platforms

### Dev.to

Required for the real Dev.to adapter:

```text
DEVTO_API_KEY
```

The adapter creates unpublished drafts only.

### Hashnode

Hashnode is export-only by default.

Do not configure `HASHNODE_TOKEN` or `HASHNODE_PUBLICATION_ID` unless the publication is upgraded to a paid plan with GraphQL API access. Without that plan, upload the generated Hashnode Markdown draft manually.

### Medium

Medium is export-only.

Do not add a real Medium API adapter unless the platform provides a supported publishing API again.

---

## Rule

Credential checks must run before any non-mock adapter posts content.

---

## Store Review Synchronization

The review dashboard accepts an App Store Connect API key and generates a
short-lived JWT at runtime:

```text
APP_STORE_CONNECT_KEY_ID
APP_STORE_CONNECT_ISSUER_ID
APP_STORE_CONNECT_PRIVATE_KEY_BASE64
GOOGLE_PLAY_ACCESS_TOKEN
```

`APP_STORE_CONNECT_TOKEN` remains available as a temporary runtime override.
The Google token must use the `androidpublisher` scope and reads Google Play
reviews.

These values are read-only inputs for `scripts/sync_store_reviews.py`. Do not
store them in the generated dashboard or commit them to the repository.

Review reply publication remains manual even though both stores expose reply
APIs. See `docs/Store_Review_Response_Guide.md`.
