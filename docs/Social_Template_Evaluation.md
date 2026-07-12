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
{{title}}

{{x_summary}}

{{url}}
```

### Evaluation

| Criterion | Assessment |
| --- | --- |
| Platform fit | Good. X needs a short post with one clear link. |
| Link card support | Good, provided the target page includes `twitter:*` and Open Graph metadata. |
| Canonical integrity | Good. The post points back to the article and does not introduce new claims. |
| Brevity | Good. The generator truncates the summary for the 280-character surface. |
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
{{title}}

{{insight}}

{{key_points}}

{{cta}}
{{url}}
```

### Evaluation

| Criterion | Assessment |
| --- | --- |
| Platform fit | Good. LinkedIn benefits from a short professional insight before the link. |
| Link card support | Good, because the canonical page includes Open Graph metadata. |
| Reader value | Stronger than X. It includes a short article insight and selected workflow points. |
| Canonical integrity | Good. Points are extracted from the article, not invented separately. |
| Product neutrality | Good. The template does not force app promotion into the social post. |
| Korean support | Good. The CTA is localized. |
| Risk | Low to medium. The post can become too generic if the article description is weak or workflow bullets are missing. |

### Recommendation

Use LinkedIn for educational framing.

The default post should explain the problem and give two or three useful checks before the article link.

Avoid turning LinkedIn posts into launch announcements unless the article itself is a release note.

---

## Cross-Channel Evaluation

| Dimension | X | LinkedIn |
| --- | --- | --- |
| Primary role | Fast distribution | Professional explanation |
| Ideal length | Very short | Short to medium |
| Main conversion path | Link card click | Insight plus link card click |
| Best source fields | Title, description, URL | Title, short answer, workflow points, URL |
| Image dependency | High | Medium |
| API readiness | Needs platform API response validation | Needs author/account approval workflow |

---

## Required Quality Gates

Before automatic API posting is added, each generated post should pass these checks:

* No unresolved `{{placeholder}}` values.
* The URL points to the canonical published article.
* X posts remain valid under local X weighted character counting.
* LinkedIn posts include a localized CTA.
* The canonical article page includes Open Graph metadata.
* The canonical article page points card metadata at the generated PNG social card asset.
* `generated/social/manifest.json` records each draft with `status: draft`.
* The social post does not introduce claims absent from the article.
* Product mentions remain article-driven, not channel-driven.

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

The X question variant should truncate long questions before posting so the generated draft remains valid under weighted character counting.

Current automated evaluation dimensions include:

* canonical URL presence
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
