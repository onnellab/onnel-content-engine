# GitHub Actions

## ONNELLAB Content Engine

---

# 1. Purpose

This document defines the GitHub Actions workflows for the ONNELLAB Content Engine.

GitHub Actions exists to run the publishing pipeline predictably.

It must not bypass validation.

It must not publish incomplete content.

---

# 2. Publishing Workflow

Workflow file:

```text
.github/workflows/publishing.yml
```

Pipeline order:

```text
Validate

↓

Generate Markdown

↓

Generate image specifications

↓

Generate image assets

↓

Generate internal link metadata

↓

Evaluate articles

↓

Schedule ready articles

↓

Publish due articles

↓

Build

↓

Deploy
```

Every stage depends on the previous stage succeeding.

If validation fails, the workflow stops immediately.

---

# 3. Validate

The validation stage runs:

```text
scripts/validate_topics.py
scripts/validate_apps_registry.py
scripts/validate_app_releases.py
scripts/validate_foundation.py
```

No generation, build, or deployment step may run after a validation failure.

---

# 4. Create GitHub App Releases

The app release stage runs before content generation:

```text
scripts/create_github_releases.py
```

It processes only `ready` rows from:

```text
data/app_releases.csv
```

The workflow creates draft GitHub Releases by default and uploads only release artifacts that pass `scripts/validate_app_releases.py`.

Debug, dev, internal, and test artifacts are blocked before upload.

The store version snapshot stage runs after the release upload preview/creation:

```text
scripts/check_store_versions.py
```

It writes:

```text
data/store_versions.csv
```

App Store rows can be marked `new`, `unchanged`, or `updated`. Google Play rows are recorded as `manual_check` with the package ID because this workflow does not use Play Store scraping as a release source of truth.

Updated store snapshots are then converted into planned release candidates:

```text
scripts/prepare_app_release_rows.py
```

Candidate rows are committed as `planned` rows in `data/app_releases.csv`. They do not create GitHub Releases until a real release artifact and checksum are added and the row is marked `ready`.

The release artifact fill stage then checks:

```text
data/app_release_config.csv
```

The config is validated during the initial validation stage:

```text
scripts/validate_app_release_config.py
```

and runs:

```text
scripts/fill_ready_app_releases.py
```

It promotes a planned row to `ready` only when exactly one matching `*-release.*` artifact exists.

The release report stage then writes:

```text
generated/reports/app_releases.md
```

using:

```text
scripts/generate_app_release_report.py
```

The attention issue stage then creates, updates, reopens, or closes one fixed GitHub Issue:

```text
scripts/sync_app_release_issue.py
```

For cross-repository releases, configure this secret:

```text
ONNELLAB_RELEASE_TOKEN
```

---

# 5. Generate Markdown

The Markdown stage runs:

```text
scripts/generate_all_markdown.py
```

This stage generates Markdown drafts only from approved topics.

It does not generate images.

It does not publish.

---

# 5. Generate Image Specifications

The image specification stage runs:

```text
scripts/generate_all_image_specs.py
```

This stage creates `image_spec.json` files only.

It does not publish.

---

# 6. Generate Image Assets

The image asset stage runs:

```text
scripts/generate_all_image_assets.py
```

This stage creates deterministic article image assets from approved image specifications.

It does not use external image generation.

---

# 7. Generate Internal Links

The internal link stage runs:

```text
scripts/generate_all_internal_links.py
```

This stage generates recommendation metadata for:

* related articles
* related applications
* related guides

It must not modify article text.

---

# 8. Evaluate Articles

The evaluation stage runs:

```text
scripts/evaluate_all_articles.py
```

An article may be scheduled or published only when its review score is greater than:

```text
9.0 / 10
```

A score of exactly `9.0` is not enough.

The review score includes:

* article structure
* metadata readiness
* article title and blog card title consistency
* ONNELLAB brand spelling consistency
* internal links
* image existence
* image quality
* workflow diagram availability for social card generation
* translation quality

---

# 9. Schedule Ready Articles

The scheduling stage runs:

```text
scripts/schedule_ready_articles.py --threshold 9.0 --interval-days 3 --publication-time 09:00
```

Approved review articles are scheduled one at a time at a fixed three-day interval.

The publication time is `09:00` Korea Standard Time.

---

# 10. Publish Due Articles

The due publication stage runs:

```text
scripts/publish_due_articles.py --threshold 9.0 --site-url https://onnelakin.github.io/ --limit 1
```

Only due scheduled articles whose review score remains greater than `9.0 / 10` are promoted to `published`.

Scheduled articles are not included in the website build before this stage promotes them.

---

# 11. Build

The build stage runs:

```text
scripts/build_site.py --site-url https://onnelakin.github.io/
```

The build stage converts Markdown into the canonical website output:

```text
Markdown

↓

HTML

↓

RSS

↓

Sitemap
```

Build output is written to:

```text
generated/html/
```

---

# 12. Generate And Approve Distribution

The distribution draft stage runs after the canonical site build:

```text
scripts/generate_social_posts.py --site-url https://onnelakin.github.io/
scripts/generate_syndication_drafts.py --site-url https://onnelakin.github.io/
scripts/approve_due_distribution.py --approved-by github-actions
```

Core automated cadence:

```text
Day 0: canonical ONNELLAB article + X
Day 1: Bluesky
Day 2: Dev.to
Day 3: next canonical ONNELLAB article + X
```

Only English primary drafts are automatically approved.

LinkedIn remains manual.

Hashnode remains export-only unless its paid API is enabled later.

Medium remains disabled.

---

# 13. Deploy

The deploy stage runs only when dry-run mode is disabled.

The first deployment target is the main GitHub Pages homepage repository:

```text
https://github.com/onnelakin/onnelakin.github.io.git
```

The deployment branch is:

```text
main
```

The canonical website root is:

```text
https://onnelakin.github.io/
```

The workflow requires this secret:

```text
ONNELAKIN_GITHUB_PAGES_TOKEN
```

Deployment does not replace the homepage repository with `generated/html/`.

Instead, it exports approved generated Markdown into the Astro homepage repository:

```text
src/content/blog/{en,ko}/{slug}.md
```

The homepage repository then runs its own Astro build before the Markdown content is committed and pushed.

---

# 14. Post Core Distribution

After deployment succeeds, the workflow posts approved due distribution drafts:

```text
scripts/post_core_distribution.py
```

Required GitHub Actions secrets:

```text
X_CLIENT_ID
X_CLIENT_SECRET
X_REFRESH_TOKEN
BLUESKY_HANDLE
BLUESKY_APP_PASSWORD
DEVTO_API_KEY
```

Posting status is committed back to:

```text
generated/social/manifest.json
generated/syndication/manifest.json
```

The core distribution posting script attempts X, Bluesky, and Dev.to independently. If one platform fails, the remaining platforms are still attempted and the failed manifest item records its error state before the workflow fails.

---

# 15. Scheduled Automation

The workflow runs automatically every day at:

```text
00:00 UTC
```

This is:

```text
09:00 KST
```

Daily execution does not mean daily publishing.

The scheduling and due-publication scripts enforce the three-day publication interval.

Push events run dry-run mode.

Scheduled events run real publication mode.

---

# 16. Dry-Run Mode

Dry-run mode is used for testing the workflow safely.

In dry-run mode:

* validation runs
* Markdown generation runs in a temporary copy
* image specification generation runs in a temporary copy
* image asset generation runs in a temporary copy
* internal link generation runs in a temporary copy
* article evaluation runs in a temporary copy
* scheduling runs in a temporary copy
* due-publication runs in a temporary copy
* build runs in a temporary copy
* distribution draft generation runs in a temporary copy
* due distribution approval runs in a temporary copy
* homepage Markdown export is previewed without copying files
* deployment is skipped
* external distribution posting is skipped
* repository files are not modified

Manual workflow dispatch defaults to dry-run mode.

Push events also run dry-run mode by default.

---

# 15. Unsupported Targets

Blogger is not supported.

The ONNELLAB website is the canonical publishing destination.

GitHub Pages is the first deployment target.

---

# Final Principle

Validate first.

Generate only after validation.

Deploy only validated Markdown into the canonical homepage repository.
