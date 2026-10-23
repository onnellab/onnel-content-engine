# Nine-language blog preview

The `Preview nine-language blog candidate` workflow builds the actual current
homepage Astro checkout with a reviewed candidate overlay. It runs the homepage's
locked Playwright dependency against that local build at desktop and mobile
widths and retains screenshots, link/metadata results and exact SHA provenance
for one day. It does not host a preview website or publish a blog article.

## Boundaries

- This workflow uses the public content-engine repository's standard Linux
  runner. Fixtures and Actions artifacts follow that repository's visibility;
  do not put private manuscripts, credentials or user data here.
- Only `contents: read` is granted. Both checkouts disable credential persistence.
- There is no Pages deployment, queue update, distribution, app release, API
  secret or new persistent authentication.
- The active native candidate is `preview/research-source-notes`, outside every publishing queue.
  The existing `prepare_research_preview.py` validates its hash-bound nine-language
  draft in a disposable engine copy and emits `preview-evidence/research-source-notes/candidate.json`.
  Aligna and ClipNest source adapters, closed profiles and regression tests remain
  unchanged; already-published Aligna is not regenerated as a fresh idea.
- The workflow runs research adapter boundary tests as well as the existing preview
  regression suites before native generation. It does not relax any native gate.
- Source SHA256, exact nine-language membership, slug/path identity, size,
  inactive SVG content, absent fabricated dates and destination collisions are
  checked before overlay. Only exact Markdown and blog-asset paths are allowed.
- Existing homepage templates, CSS, scripts and configuration are untouched.
  The existing publisher's brand transformation is reused, including its
  branded workflow-to-1200x675 social-PNG contract.
- Current homepage and content-engine SHAs and overlay file hashes are recorded.
  Screenshots prove only that recorded candidate/build, not later commits.

## Running and reviewing

A main push changing the workflow, candidate or its tests starts this workflow.
The existing publishing workflow also runs on main pushes, but its existing
`DRY_RUN` expression is true for every push. Real publishing, scheduling,
deployment, output commits and external distribution remain skipped.

Use the job's `blog-preview-<sha>` artifact. Confirm all 18 locale/viewport cases
passed, then inspect the actual screenshots for all nine languages. Passing
automatic assertions does not replace manual layout and language review.

The candidate remains unscheduled and has no invented publication date. Add it
to the canonical queue only after all required editorial, source, asset and
actual-page checks pass and a fresh main-conflict check succeeds. The existing
Publishing Pipeline remains the sole publisher.
