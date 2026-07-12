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
X_BEARER_TOKEN
```

The adapter posts generated text with the canonical URL. X website cards are expected to render from the canonical page's Open Graph and Twitter card metadata.

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

Required for the real Hashnode adapter:

```text
HASHNODE_TOKEN
HASHNODE_PUBLICATION_ID
```

Hashnode requires publication-level configuration before posting and creates drafts through the GraphQL API.

### Medium

Medium is export-only.

Do not add a real Medium API adapter unless the platform provides a supported publishing API again.

---

## Rule

Credential checks must run before any non-mock adapter posts content.
