# Aether Inn existing single covers

Singles use approved existing artwork and local image processing. They do not
fall back to paid image generation when art or approval is missing. This preserves
the fantasy JRPG/MMORPG identity and does not authorize a new logo or brand style.

## Private staged source and approval

Stage the exact existing artwork under the private Aether `assets` directory.
The original MYBOX file is never modified by the importer. Record its relative
path and actual SHA-256 in `assets/single_cover_approvals.json`. Do not commit the
private approval file, source media or account data.

Each entry is for one exact song title. Neither a previous upload, model name,
paid subscription nor a compilation-theme approval establishes per-song rights or
quality. Only record true approval flags when supported by the owner's actual
rights and quality confirmation. This example is intentionally not publishable:

```json
{
  "schema_version": 1,
  "profile": "aether_inn",
  "test_only": false,
  "covers": {
    "Exact Song Title": {
      "title": "Exact Song Title",
      "path": "single-covers/exact-song-title.png",
      "sha256": "<actual 64-character SHA-256>",
      "commercial_use_confirmed": false,
      "quality_accepted": false,
      "kind": "finished_cover"
    }
  }
}
```

Use `finished_cover` for approved art that already contains the right title and
branding; the local importer only normalizes its 16:9 output to 1920×1080 and
does not overlay another title. Use `unbranded_background` only for a clean
approved background; it uses the existing local adaptive serif/gold branding.

## Fail-closed checks

The importer requires explicit true rights and quality flags, the Aether profile,
`test_only=false`, the exact title and source hash. It rejects missing files,
symlinks, traversal, unsupported formats, images above 32 MiB, undersized/non-16:9
art and detected letterbox bands. The copied bytes are rehashed before image
processing. Production output must be 1920×1080. Stored provenance includes the
source hash, approval-file hash, approved title and resulting cover hash. The
persisted approved cover is rehashed before a later render retry as well.

Missing records are blockers, not permission to fabricate approvals. The importer
does not certify copyright, originality, listening quality or monetization
eligibility. Offline fixtures test behavior without paid APIs, actual rendering
or YouTube publication. A real source must still pass the runtime image checks.

## Preserved upload contracts

Only new imported-cover records receive the existing-cover provider policy.
Historical generated-cover approval hashes stay unchanged. Uploaded jobs keep
their exact video IDs and hash-bound rendered assets; missing original music or
cover files do not trigger regeneration. Corrupt/missing final video or thumbnail
assets remain blocked/retry-required under existing integrity gates.
