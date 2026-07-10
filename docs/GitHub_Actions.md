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
scripts/validate_foundation.py
```

No generation, build, or deployment step may run after a validation failure.

---

# 4. Generate Markdown

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

It does not generate image assets.

---

# 6. Build

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

# 7. Deploy

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

# 8. Dry-Run Mode

Dry-run mode is used for testing the workflow safely.

In dry-run mode:

* validation runs
* Markdown generation runs in a temporary copy
* image specification generation runs in a temporary copy
* build runs in a temporary copy
* homepage Markdown export is previewed without copying files
* deployment is skipped
* repository files are not modified

Manual workflow dispatch defaults to dry-run mode.

Push events also run dry-run mode by default.

---

# 9. Unsupported Targets

Blogger is not supported.

The ONNELLAB website is the canonical publishing destination.

GitHub Pages is the first deployment target.

---

# Final Principle

Validate first.

Generate only after validation.

Deploy only validated Markdown into the canonical homepage repository.
