# Social Template Evaluation

## Purpose

This document evaluates the current generated social distribution templates.

The templates are not canonical content.

They are deterministic adaptations of published Markdown articles.

Current template files:

```text
templates/social/x.txt
templates/social/linkedin.txt
templates/social/x_question.txt
templates/social/linkedin_short.txt
templates/social/bluesky.txt
templates/social/bluesky_question.txt
```

Current output paths:

```text
generated/social/x/{language}/{category}/{slug}.txt
generated/social/linkedin/{language}/{category}/{slug}.txt
generated/social/bluesky/{language}/{category}/{slug}.txt
generated/social/variants/{template_id}/{language}/{category}/{slug}.txt
generated/social/manifest.json
generated/social/evaluation.json
generated/assets/blog/{language}/{slug}/social-card.svg
generated/assets/blog/{language}/{slug}/social-card.png
```

---

## X Template

```text
{{hook}}

{{x_summary}}

{{cta}}
{{url}}
```

### Evaluation

| Criterion | Assessment |
| --- | --- |
| Platform fit | Good. X needs a short post with one clear link. |
| Link card support | Good, provided the target page includes `twitter:*` and Open Graph metadata. |
| Link integrity | X uses store-install destinations when an article's related app has store URLs; otherwise it uses the canonical article. |
| Brevity | Good. The generator keeps complete blocks under the 240-weighted-character internal target. |
| Korean support | Good. The generator validates weighted length before writing drafts. |
| Risk | Low to medium. The weighted counter is local and should still be checked against platform API responses before unattended posting. |

### Recommendation

Keep the X template minimal.

Do not add multiple bullet points, hashtags, or product-first copy by default.

The website card should carry the image, title, and description.

The generated card asset should be the dedicated `social-card.png`, not an in-article workflow diagram.

The SVG file remains the reproducible source for the PNG card.

---

## LinkedIn Template

```text
{{hook}}

{{lead}}

{{points_block}}

{{cta}}
{{url}}
```

### Evaluation

| Criterion | Assessment |
| --- | --- |
| Platform fit | Good. LinkedIn benefits from a short professional insight before the link. |
| Link card support | Good, because the canonical page includes Open Graph metadata. |
| Reader value | Stronger than X. It includes a short article insight and selected workflow points. |
| Canonical integrity | Required. LinkedIn always points to the canonical article, even when store destinations exist. |
| Product neutrality | Good. The template does not force app promotion into the social post. |
| Korean support | Good. The CTA is localized. |
| Risk | Low to medium. The post can become too generic if the article description is weak or workflow bullets are missing. |

### Recommendation

Use LinkedIn for educational framing.

The default post should explain the problem and give two or three useful checks before the article link.

Avoid turning LinkedIn posts into launch announcements unless the article itself is a release note.

---

## Cross-Channel Link Matrix

The matrix applies equally to primary templates and variants.

| Store destinations available | X | Bluesky | LinkedIn |
| --- | --- | --- | --- |
| Yes | `store_install`; Install CTA; store target(s) | `store_install`; Install CTA; store target(s) | `canonical_article`; Read full article CTA; canonical target; empty `destination_urls` |
| No | `canonical_article`; Read full article CTA; canonical target; empty `destination_urls` | `canonical_article`; Read full article CTA; canonical target; empty `destination_urls` | `canonical_article`; Read full article CTA; canonical target; empty `destination_urls` |

Syndication is outside this matrix and continues to use only the canonical or
platform-original article URL.

## Complete-Block Fitting

No unposted social template output may contain generator-added `...` or `…`.
The generator starts with complete hooks, questions, summaries, leads, and list
points. If an internal target is exceeded, it removes optional complete blocks
in a deterministic order. A primary compact template may select the complete
article title when its complete hook cannot fit. It does not slice a sentence or append an ellipsis.
If required complete blocks still cannot fit, generation fails instead of
silently producing a fragment.

Internal targets are X `<= 240` weighted characters, Bluesky `<= 260`
characters, and LinkedIn `<= 900` characters. `x_question` and
`bluesky_question` begin with the source question, including its question mark.

---

## Required Quality Gates

Before automatic API posting is added, each generated post should pass these checks:

* No unresolved `{{placeholder}}` values.
* Link strategy, target, destinations, and localized CTA match the platform matrix.
* Unposted copy contains neither `...` nor `…`.
* X, Bluesky, and LinkedIn posts remain within their internal targets.
* The canonical article page includes Open Graph metadata.
* The canonical article page points card metadata at the generated PNG social card asset.
* `generated/social/manifest.json` records each draft with `status: draft`.
* The social post does not introduce claims absent from the article.
* Product mentions remain article-driven, not channel-driven.

Posted history is not rescored against current copy, CTA, length, or link-matrix
policy. It must still pass structural metadata, URL consistency, and artifact
validation. Gate scoring includes only actionable non-posted primary drafts;
posted primary items count only for platform coverage, and variants are
excluded from both roles.

---

## Current Verdict

The current templates are suitable for manual review and copy posting.

They are also suitable as inputs to a future API adapter.

The main improvement needed before unattended posting is account-level approval and platform API response validation.

Operational support now includes:

```text
scripts/validate_social_posts.py
scripts/approve_social_post.py
scripts/evaluate_social_templates.py
scripts/social_post_report.py
```

Experimental templates should not replace the defaults until performance data exists.

Use `x_question.txt` for problem-solving articles that benefit from a direct question hook.

Use `linkedin_short.txt` when the default LinkedIn post feels too dense for a lightweight article.

Use `bluesky.txt` as the default Bluesky template.

Use `bluesky_question.txt` for question-led problem-solving articles.

Bluesky drafts should target the internal compact threshold of 260 characters even though the platform limit is higher.

The generated evaluation score should remain at or above `9.5 / 10` before API posting is connected.

The short LinkedIn variant should still include one or two extracted article points so it remains useful as a professional post rather than becoming a bare link share.

The default LinkedIn template should keep the insight section compact, preferably two sentences before the bullet list.

Question-led variants keep the complete source question. If the required question and link block cannot fit, generation fails for review rather than truncating it.

Current automated evaluation dimensions include:

* platform link strategy, target URL, destination URLs, and CTA
* no ellipsis in unposted drafts
* unresolved placeholder checks
* PNG card checks
* template tracking
* approval fields
* metrics fields
* X weighted length
* Bluesky length
* LinkedIn CTA and bullet density

PNG card generation currently requires `rsvg-convert`, either from the system path or from:

```text
.tools/librsvg2-bin/usr/bin/rsvg-convert
```
