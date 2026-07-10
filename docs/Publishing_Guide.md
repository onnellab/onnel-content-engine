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

---

# 7. Publication Frequency

The publishing schedule should remain consistent.

Preferred schedule:

* One article every three days

Consistency is more important than volume.

Avoid long inactive periods followed by large bursts of content.

Generation work may happen ahead of publication.

Article generation, image asset generation, and internal link recommendation may be prepared in advance.

Publication itself must still follow the three-day schedule.

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
* Images exist.
* Text-containing images exist separately for English and Korean.
* Metadata is complete.
* Internal links work.
* External links are valid.
* Category is correct.
* Related applications are accurate.
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
