# Publishing Guide

## ONNELLAB Content Engine

---

# 1. Purpose

This document defines the permanent publishing rules for the ONNELLAB Content Engine.

Its purpose is to ensure that every publication follows the same workflow, quality standards, and branding regardless of the publishing platform.

Publishing should be predictable, consistent, and scalable.

---

# 2. Core Philosophy

Publishing is the final step.

It should never become the primary goal.

Knowledge is created first.

Publishing simply delivers it.

---

# 3. Canonical Source

Every article has exactly one canonical source.

The canonical version is:

```text id="pubcanonical"
Markdown
```

Every other format is generated from this source.

Never edit secondary formats directly.

---

# 4. Publishing Pipeline

Every publication follows the same process.

```text id="publishflow"
Markdown

↓

Images

↓

Metadata

↓

Build

↓

Publish

↓

Archive
```

Publishing should remain deterministic.

---

# 5. Primary Destination

The official ONNELLAB website is the primary publication destination.

Every article should be published there first.

Other platforms receive adapted versions.

The main GitHub Pages homepage repository is:

```text
https://github.com/onnelakin/onnelakin.github.io.git
```

The canonical website root is:

```text
https://onnelakin.github.io/
```

The local clone for homepage publishing work is:

```text
C:\dev\onnelakin.github.io
```

In WSL, use:

```text
/mnt/c/dev/onnelakin.github.io
```

Do not use a temporary `/tmp` clone for homepage publishing work when this local clone is available.

Other ONNELLAB sites are connected from this main homepage.

Brand assets and favicon rules are defined in:

```text
docs/Brand_Guide.md
```

Each public post must be published in both supported languages:

* English
* Korean

Publishing only one language is incomplete.

The English and Korean versions should share the same slug when they represent the same article.

---

# 6. Secondary Destinations

Possible future destinations include:

* RSS
* Newsletter
* X
* LinkedIn
* Reddit

These are distribution channels.

They are not canonical sources.

The publishing pipeline may generate platform-specific distribution drafts after the canonical website build.

Current social draft targets:

* X
* LinkedIn
* Bluesky

Generated social drafts are stored under:

```text
generated/social/{platform}/{language}/{category}/{slug}.txt
```

Generated social approval metadata is stored at:

```text
generated/social/manifest.json
```

Each manifest item should keep operational posting fields:

* `status`
* `template_id`
* `template_path`
* `is_variant`
* `approved_by`
* `approved_at`
* `post_id`
* `posted_url`
* `posted_at`
* `last_attempt_at`
* `error`
* `retry_count`
* `impressions`
* `clicks`
* `engagements`
* `last_metrics_at`

Generated social card assets are stored with blog assets:

```text
generated/assets/blog/{language}/{slug}/social-card.svg
generated/assets/blog/{language}/{slug}/social-card.png
```

These drafts may be reviewed, copied manually, or passed to a later API adapter.

Do not edit them as source content.

If a platform API is connected later, the API layer must publish from these generated drafts, not directly from hand-written social copy.

Website pages should include Open Graph and X card metadata so shared article links can render platform-native previews when supported.

The Open Graph and X image URL should point to the generated PNG social card asset, not the in-article workflow diagram.

Template quality is evaluated in:

```text
docs/Social_Template_Evaluation.md
```

Before API posting, validate social drafts with:

```text
scripts/validate_social_posts.py
```

Evaluate template quality with:

```text
scripts/evaluate_social_templates.py --output generated/social/evaluation.json
```

Review posting state with:

```text
scripts/social_post_report.py
```

Post approved drafts through the mock adapter with:

```text
scripts/post_social_drafts.py --adapter mock
```

Before using any non-mock adapter, check credentials with:

```text
scripts/check_publishing_credentials.py
```

Run live authentication preflight without posting:

```text
scripts/check_publishing_credentials.py --live
```

Print one consolidated dry-run report for approved social and syndication items:

```text
scripts/publishing_dry_run_report.py
```

Add `--live-credentials` to include live authentication checks in the consolidated report.

Publishing adapter requirements are defined in:

```text
docs/Publishing_Credentials.md
scripts/publishing_adapters.py
```

Preview approved drafts without changing the manifest with:

```text
scripts/post_social_drafts.py --dry-run
```

Approve individual drafts with:

```text
scripts/approve_social_post.py TOPIC-0001 x en --approved-by editor
```

Variant drafts are generated under:

```text
generated/social/variants/{template_id}/{language}/{category}/{slug}.txt
```

Variant drafts must not be approved unless the approval command is run with `--allow-variant`.

Only `approved` manifest items may be posted.

Items with `status: posted` must not be posted again by default.

Real X, Bluesky, and LinkedIn adapters must update the same manifest fields used by the mock adapter:

* `status`
* `post_id`
* `posted_url`
* `posted_at`
* `last_attempt_at`
* `error`
* `retry_count`

Bluesky uses the same social manifest and posting flow as X and LinkedIn.

The X adapter posts generated draft text to `https://api.x.com/2/tweets`:

* requires `X_CLIENT_ID`, `X_CLIENT_SECRET`, and `X_REFRESH_TOKEN`
* refreshes an OAuth 2.0 access token through `POST https://api.x.com/2/oauth2/token`
* sends `Authorization: Bearer <refreshed_access_token>`
* keeps the canonical URL in the post text
* relies on the canonical page Open Graph and Twitter card metadata for website card rendering

The X app must request `tweet.write`, `tweet.read`, `users.read`, and `offline.access`. `offline.access` is required so the content engine can refresh short-lived access tokens during scheduled automation.

For local scheduled runs, set `X_REFRESH_TOKEN_FILE=.tokens/x-refresh-token` so a rotated refresh token can be persisted outside git. In GitHub Actions, update the `X_REFRESH_TOKEN` repository secret if a run reports that X returned a rotated refresh token.

Inspect the X payload without posting:

```text
scripts/post_social_drafts.py --adapter x --platform x --dry-run --verbose
```

The Bluesky adapter posts text with clickable link facets and website card embeds:

* creates a session with `com.atproto.server.createSession`
* uploads the generated 1200x630 social card PNG with `com.atproto.repo.uploadBlob`
* posts an `app.bsky.feed.post` record with `com.atproto.repo.createRecord`
* adds `app.bsky.richtext.facet#link` facets for URLs in the draft
* attaches an `app.bsky.embed.external` website card using the canonical URL, draft title, draft description, and uploaded thumbnail blob

Before the first real Bluesky post, run:

```text
scripts/check_bluesky_connection.py
```

To inspect the exact approved Bluesky payload without posting, run:

```text
scripts/post_social_drafts.py --adapter bluesky --platform bluesky --dry-run --verbose
```

Failed social posts may be retried only after an explicit reset:

```text
scripts/reset_failed_social_post.py TOPIC-0001 bluesky en bluesky
```

Long-form syndication platforms must stay separate from social drafts.

Generated syndication drafts are stored under:

```text
generated/syndication/{platform}/{language}/{category}/{slug}.md
```

Generated syndication metadata is stored at:

```text
generated/syndication/manifest.json
```

Evaluate syndication drafts with:

```text
scripts/evaluate_syndication_drafts.py --output generated/syndication/evaluation.json
```

Dev.to real draft posting is supported:

* requires `DEVTO_API_KEY`
* sends `POST https://dev.to/api/articles`
* uses the `api-key` request header
* sends `published: false` from the generated Dev.to frontmatter
* preserves the canonical URL from the manifest

Inspect the Dev.to payload without posting:

```text
scripts/post_syndication_drafts.py --adapter devto --platform devto --dry-run --verbose
```

Hashnode is export-only by default because GraphQL API access now requires a paid publication plan.

Generated Hashnode drafts still include:

* canonical URL as `originalArticleURL`
* generated social card URL as `coverImageOptions.coverImageURL`
* normalized tags
* a `publication_id` placeholder for future paid API use

Inspect the Hashnode payload without posting:

```text
scripts/post_syndication_drafts.py --adapter hashnode --platform hashnode --dry-run --verbose
```

Validate syndication drafts with:

```text
scripts/validate_syndication_drafts.py
```

Review syndication posting state with:

```text
scripts/syndication_report.py
```

Approve individual syndication drafts with:

```text
scripts/approve_syndication_draft.py TOPIC-0001 devto en --approved-by editor
```

Post approved Dev.to, Hashnode, or Medium drafts through the mock adapter with:

```text
scripts/post_syndication_drafts.py --adapter mock
```

Current syndication draft targets:

* Dev.to
* Hashnode
* Medium

Syndication drafts must include a canonical link back to the ONNELLAB article.

Dev.to drafts should remain unpublished by default and use normalized tags.

Hashnode drafts should include a `cover_image` field pointing to the generated social card PNG and a blank `publication_id` placeholder until a publication is configured.

Hashnode Markdown should be copied into the Hashnode editor manually unless the publication is upgraded to a paid plan with GraphQL API access.

Medium is export-only by default because its public API documentation is archived and no longer recommended for new integrations.

Medium drafts must remain `status: draft` unless explicitly tracked as a manual action.

---

# 6-1. Product Release Destinations

GitHub Release is not a general educational distribution channel.

It may be used only when all of the following are true:

* `source_type` is `release_note`
* a related ONNELLAB application exists
* a version or tag is known
* the Markdown contains a changelog or release summary section
* the release is tied to a real repository artifact or tag

Education-first articles must not be converted into GitHub Releases.

---

# 7. Publication Frequency

The publishing schedule should remain consistent.

Preferred schedule:

* One article every three days

Core distribution schedule:

* ONNELLAB canonical article: every three days at `09:00` KST
* X: same day as the canonical article
* Bluesky: one day after the canonical article
* Dev.to: two days after the canonical article

This creates a three-day distribution window per article and avoids posting the same article to every automated channel at once.

Consistency is more important than volume.

Avoid long inactive periods followed by large bursts of content.

Generation work may happen ahead of publication.

Article generation, image asset generation, and internal link recommendation may be prepared in advance.

Publication itself must still follow the three-day schedule.

Distribution drafts are approved automatically only for English primary drafts on the core automated channels. Variants, LinkedIn, Hashnode, and Medium remain manual/export-only unless explicitly approved.

The core automated posting command is:

```text
scripts/post_core_distribution.py
```

It attempts X, Bluesky, and Dev.to independently so one platform failure does not prevent the remaining due platforms from being attempted.

---

# 8. Categories

Every article must belong to one primary category.

Available categories:

* Reading
* Music
* Productivity
* Media
* Craft
* Games
* Research

Categories describe the problem domain.

Not the product.

---

# 9. Metadata

Every published article should include:

* title
* slug
* publication date
* last updated date
* category
* tags
* related applications
* related articles

Metadata should remain complete and consistent.

---

# 10. URL Policy

URLs should remain:

* short
* descriptive
* permanent

Preferred:

```text id="urlgood"
blog/read-large-txt-files
```

Avoid changing published URLs.

If changes are unavoidable, use redirects.

---

# 11. Internal Linking

Every article should include:

* related articles
* related applications
* official documentation

Internal links should improve navigation.

Never insert links solely for SEO.

---

# 12. Product References

Applications should appear only after the educational content.

Readers should always understand:

* why the application is relevant
* which problem it solves

Avoid product-first publishing.

---

# 13. Image Publishing

Every published article should include at least one meaningful visual.

Preferred order:

1. Workflow diagram
2. Comparison
3. Screenshot
4. Supporting illustration

Images should always support understanding.

---

# 14. Publication Validation

Before publishing, confirm:

* Markdown is valid.
* English and Korean article counterparts both exist.
* Article title and blog card title are consistent.
* ONNELLAB brand spelling is preserved in every language.
* Images exist.
* Text-containing images exist separately for English and Korean.
* Image quality checks pass.
* A workflow diagram source exists for social card generation when the article uses generated blog imagery.
* Metadata is complete.
* Internal links work.
* External links are valid.
* Category is correct.
* Related applications are accurate.
* Translation quality checks pass.
* The article review score is greater than `9.0 / 10`.

Publishing should fail if validation fails.

Publishing should also fail when the review score is `9.0 / 10` or lower.

---

# 15. Archive Policy

After publication, archive:

* Markdown
* Images
* Metadata
* Generated HTML
* Publication log

Published content should remain reproducible.

---

# 16. Update Policy

Articles may be updated when:

* technical information changes
* products evolve
* explanations improve
* screenshots become outdated

Minor improvements should preserve the original URL whenever possible.

---

# 17. Automation

Publishing should eventually become fully automated.

Possible automated tasks include:

* metadata generation
* image optimization
* sitemap updates
* RSS generation
* deployment
* publication logging

Human approval may remain optional.

GitHub Pages deployment must preserve the Astro homepage repository.

The content engine must not delete or replace the homepage repository root with generated HTML output.

Approved Markdown is exported into:

```text
src/content/blog/{en,ko}/{slug}.md
```

The homepage repository owns HTML, RSS, sitemap, and GitHub Pages output generation through its Astro build.

---

# 18. Success Criteria

A successful publication:

* reaches readers consistently
* strengthens the ONNELLAB knowledge ecosystem
* naturally introduces relevant applications
* remains valuable long after publication

Publishing should increase the value of previous publications.

---

# Final Principle

Publish consistently.

Preserve quality.

Let every article strengthen the ecosystem.
