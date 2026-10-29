# Historical blog corrections

The canonical `publishing.yml` workflow remains the only publisher. Its optional
`historical_corrections_only=true` dispatch branch applies the explicitly
allowlisted TagWeaver multi-disc iOS-save correction to all nine existing pages.
It does not generate articles, advance topics, shift publication dates, export
privacy pages, or generate/approve/post other-media content. Normal runs retain
their original behavior and additionally preflight registered corrections before
any homepage export, preventing a two-language partial correction.

## Reviewed sources and authorization

Reuse `preview/tagweaver-multidisc-ios-save` and its existing independent
editorial review. The approved registry binds the proposal and all nine reviewed
manuscripts to exact Git blob hashes. Full reverse substitution must reproduce
the original blobs, protecting every byte outside the approved sentence,
including original dates, URL/frontmatter, links, headings and images.
Authorization: `Sentinel_ac84c2183a70819187456aadfc495b5f`, 2026-10-29
10:12:17 UTC, for the bounded route, free cloud tests and existing-publisher
correction. The manuscript frontmatter is not a new publication receipt.

## Verification and publication

1. Verify current engine/homepage HEADs and all eleven source blobs. Preserve
   unrelated main changes. Commit the route and two corrected canonical engine
   manuscripts together; seven historical translations remain site-only.
2. Run native correction and workflow tests and independent review.
3. Dispatch this same workflow with `historical_corrections_only=true` and
   `dry_run=true`. It applies the exact same nine changes locally, runs the site's
   current `check:i18n-quality` and `build`, then restores all original bytes.
   Dry-run cannot reach Git staging, commit or push. Observe successful CI.
4. Dispatch the same branch with `dry_run=false` only after those checks pass.
   It refuses tracked/staged dirt, pulls fast-forward, validates all nine current
   targets, atomically prepares them with durable rollback, builds, then stages
   only the nine allowlisted paths. No other homepage path is staged.
5. Confirm the actual site commit, Pages deployment status, nine public pages,
   unchanged original dates/canonical/hreflang, replacement text and links. Record
   evidence separately; code push or build success is not public completion.

Engine and homepage commits are **not** cross-repository atomic. A restart after
the engine commit is safe: every site locale is checked before homepage writes,
old or exact-corrected bytes are accepted, and already-corrected content is
idempotent. One stale locale aborts the entire site correction. The transaction
lock rechecks paths (including ancestors) and observed bytes before replacement.
Build failure restores original article bytes. A remote push rejection or uncertain
result is not retried blindly: inspect remote state before deciding the next step.
There is no automatic rebase after validation that could hide concurrent changes.

To add a different correction, obtain its specific scope, review its complete
locale set, and extend the allowlist/tests; this is not an arbitrary payload route.

The fixed hash guard is intentionally persistent. A later legitimate edit to any
of these nine pages must be reviewed as a new complete-locale change or retire
this registry entry in the same coordinated change after confirming all corrected
pages and EN/KO canonical sources. Never auto-refresh baseline hashes or silently
accept arbitrary new bytes. An unexpected later edit fails closed rather than
being overwritten; removing the registry is not a way to apply only two locales.
