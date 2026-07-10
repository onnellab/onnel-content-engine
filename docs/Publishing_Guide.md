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

* Two to three articles per week

Consistency is more important than volume.

Avoid long inactive periods followed by large bursts of content.

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
* Images exist.
* Metadata is complete.
* Internal links work.
* External links are valid.
* Category is correct.
* Related applications are accurate.

Publishing should fail if validation fails.

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
