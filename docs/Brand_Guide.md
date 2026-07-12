# ONNELLAB Brand Guide

## Purpose

This guide keeps ONNELLAB visual assets consistent across the homepage, generated blog pages, social cards, and publishing automation.

## Wordmark

ONNELLAB is currently a text wordmark.

Use the existing site typography and spacing for the full `ONNELLAB` wordmark. Do not turn the full wordmark into a favicon because it is not readable at 16px or 32px.

## Favicon

Use the shared ONNELLAB `OL` monogram favicon for the main site and pages under `https://onnellab.github.io/`.

Favicon assets:

```text
favicon.svg
favicon-32x32.png
apple-touch-icon.png
site.webmanifest
```

The favicon background should remain transparent. The icon itself should carry the visible brand mark.

Current cache version:

```text
20260712-transparent
```

Use versioned favicon URLs in page heads:

```text
/favicon.svg?v=20260712-transparent
/favicon-32x32.png?v=20260712-transparent
/apple-touch-icon.png?v=20260712-transparent
/site.webmanifest?v=20260712-transparent
```

## Colors

Core colors:

```text
Ink:       #282723
Accent:    #b9d7ea
Surface:   #f8f4ec
```

Use `Ink` for primary favicon strokes and high-emphasis brand marks.

Use `Accent` sparingly for a small recognisable brand detail.

Use `Surface` for theme color, page surfaces, and social card background systems. Do not bake `Surface` into the favicon background unless a specific platform requires an opaque icon.

## App Icons

App detail pages should keep using each app's own icon inside the page UI.

Do not create app-specific favicons for pages that live under the main ONNELLAB GitHub Pages site.

Recommended structure:

```text
Browser favicon: ONNELLAB shared OL monogram
App detail hero/card/icon: individual app icon
PWA manifest for a standalone app: app icon, only when the app has its own installable web surface
```

App-specific favicon variants are only appropriate when:

* an app has a separate domain or subdomain
* an app is a standalone installable PWA
* users are expected to keep multiple ONNELLAB app web surfaces open and need tab-level app distinction

## Social Cards

Social cards should use the ONNELLAB brand system but remain article-first.

Current social card assets use:

```text
generated/assets/blog/{language}/{slug}/social-card.svg
generated/assets/blog/{language}/{slug}/social-card.png
```

Keep the ONNELLAB wordmark small and secondary on social cards. The article title and category should remain the primary information.

## Automation Rules

The content engine owns favicon generation for generated HTML previews.

The homepage repo owns the production Astro layout.

Publishing automation must keep favicon assets synchronized into the homepage repo `public/` directory:

```text
public/favicon.svg
public/favicon-32x32.png
public/apple-touch-icon.png
public/site.webmanifest
```
