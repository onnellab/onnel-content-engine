# ONNELLAB Content Engine

## Purpose

The ONNELLAB Content Engine is a long-term content automation project designed to support the entire ONNELLAB ecosystem.

Its purpose is to create useful educational content that helps people solve real problems while naturally introducing ONNELLAB products when they are genuinely relevant.

This repository is not a marketing campaign.

It is a knowledge production system.

---

# Mission

The mission of this project is simple:

> Create content that deserves to exist even without the products.

Every article should educate first.

Products appear only when they provide a meaningful solution.

---

# Core Philosophy

Content should answer questions.

Not advertise applications.

Readers should finish every article with:

* a better understanding of the topic
* a practical solution
* trust in ONNELLAB

Product awareness should emerge naturally from useful information.

---

# Design Principles

The Content Engine follows these principles.

## 1. Problem-first

Every article begins with a user problem.

Never begin with a product introduction.

---

## 2. Educational value

Every article must remain valuable even if the reader never downloads an ONNELLAB application.

Knowledge always comes first.

---

## 3. Long-term relevance

Articles should remain useful for years whenever possible.

Avoid writing content that becomes obsolete after a few weeks unless covering product updates.

---

## 4. Product neutrality

Products are introduced only after the problem has been fully explained.

The reader should never feel forced toward a download.

---

## 5. Multi-channel publishing

One source article should support multiple publishing destinations.

Examples include:

* Blog
* Homepage
* Newsletter
* Social media
* Documentation

The original content should remain the single source of truth.

---

# Repository Structure

```text
onnel-content-engine/

CODEX.md
README.md

docs/
    Workflow.md
    Content_Guide.md
    SEO_Guide.md
    AEO_Guide.md
    GEO_Guide.md
    Image_Guide.md

topics/
    reading.csv
    music.csv
    productivity.csv
    media.csv
    craft.csv
    games.csv
    research.csv

templates/
    blog/
    social/
    newsletter/

generated/
    markdown/
    html/
    images/
    social/

scripts/

.github/
    workflows/
```

---

# Workflow

Every piece of content follows the same pipeline.

```text
Topic

↓

Research

↓

Outline

↓

Article

↓

Image Specification

↓

Illustration / Infographic

↓

Review

↓

Publishing

↓

Archive
```

Each stage should remain independent.

This makes the system easier to automate and maintain.

## Repetition Fix

When the manual publishing dashboard reports social repeated phrase warnings, run:

```bash
python3 scripts/fix_social_repetition.py
```

The command applies the existing social repetition reducer, rechecks the warnings, and rebuilds the manual publishing dashboard.

## Store Review Replies

Synchronize App Store and Google Play reviews, then rebuild the dashboard:

```bash
python3 scripts/sync_store_reviews.py
python3 scripts/build_manual_publish_site.py
```

The dashboard's **Store review connection** panel accepts a newly issued Apple
Key ID, Issuer ID, and `.p8` private key, then prepares the local env and GitHub
Actions secret-sync commands. The private key is not embedded in the generated
dashboard and is cleared from the form on refresh.

The dashboard shows synchronized reviews and creates Korean or English reply
drafts from the repository-managed templates. Every draft requires human review
and manual publication. See `docs/Store_Review_Response_Guide.md`.

---

# Content Categories

The repository organizes articles by user problems rather than by products.

Current categories include:

* Reading
* Music
* Productivity
* Media
* Craft
* Games
* Research

A single article may naturally reference multiple ONNELLAB applications.

---

# Publishing Strategy

The primary publication target is the official ONNELLAB website.

Additional channels may receive adapted versions of the same content.

Examples include:

* Blog
* RSS
* Newsletter
* X
* LinkedIn
* Reddit

The original article always remains the canonical version.

---

# Relationship to ONNELLAB Products

Products are outcomes.

Content is infrastructure.

Applications should never dictate the educational content.

Instead, educational content should naturally guide readers toward the appropriate application when relevant.

---

# Automation Philosophy

Automation should remove repetitive work.

Automation should never reduce quality.

Human review remains available whenever necessary, but the system should be capable of producing publish-ready drafts with minimal intervention.

---

# Success Criteria

The project succeeds when:

* Readers consistently find useful answers.
* ONNELLAB becomes recognized as a trustworthy knowledge source.
* Products are discovered naturally through educational content.
* The publishing workflow remains scalable across dozens of applications.

---

# Long-term Vision

The Content Engine should eventually become the central publishing infrastructure for every ONNELLAB product.

Rather than maintaining separate marketing workflows for each application, a single knowledge system should support the entire ecosystem.

---

# Final Statement

Solve real problems.

Share useful knowledge.

Let the products speak through their usefulness.
