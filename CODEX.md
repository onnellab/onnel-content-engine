# CODEX.md

# ONNELLAB Content Engine

## Purpose

This repository is the content automation engine for ONNELLAB.

Its purpose is to generate, organize, and publish high-quality educational content that supports ONNELLAB products.

This repository does not exist to produce advertisements.

It exists to answer real user questions.

---

# Highest Priority

The primary objective is:

> Help users solve problems first.

Only after providing a useful answer should ONNELLAB products be introduced naturally.

Content must never feel like an advertisement.

---

# Repository Scope

This repository is responsible for:

* Blog article generation
* Knowledge article generation
* Educational content
* SEO optimization
* AEO optimization
* GEO optimization
* Infographic planning
* Content publishing workflow
* Topic management

This repository is **not** responsible for:

* Product development
* Landing page implementation
* Store metadata
* Application source code
* Marketing campaigns
* Paid advertising

---

# Core Philosophy

Every article must answer a real question.

Never begin with:

"Our app..."

Instead begin with:

"The user's problem."

The product is the solution.

Not the topic.

---

# Content Philosophy

Every article should provide value even if the reader never installs an ONNELLAB application.

Readers should leave with useful knowledge.

Installing an app should feel like an optional next step.

---

# Brand Philosophy

ONNELLAB does not compete by shouting louder.

It competes by explaining better.

Every article should feel:

* calm
* structured
* trustworthy
* practical
* timeless

Avoid exaggerated marketing language.

---

# Product Mentions

Applications should only appear when they genuinely solve the problem discussed.

Never force product placement.

Natural recommendations are preferred over direct promotion.

---

# Writing Order

Every article should follow this structure.

1.

Problem

↓

2.

Explanation

↓

3.

Possible solutions

↓

4.

ONNELLAB solution (when appropriate)

↓

5.

Further reading

---

# Automation Rules

Content generation should remain deterministic whenever possible.

The engine should separate:

Topic

↓

Research

↓

Article

↓

Images

↓

Publishing

Each stage should remain independent.

---

# Repository Operating Rules

Codex must run `git pull` before starting repository work.

When remote and local history conflict, Codex must rebase and keep the better implementation according to the project documents.

Codex must commit and push after each completed task.

After every 10 completed tasks, Codex must reread the instruction Markdown files before making further implementation decisions.

The main GitHub Pages homepage repository is:

```text
https://github.com/onnellab/onnellab.github.io.git
```

The local clone for the main GitHub Pages homepage repository is:

```text
C:\dev\onnellab.github.io
```

In WSL, use:

```text
/mnt/c/dev/onnellab.github.io
```

Do not use a temporary `/tmp` clone for homepage work when this local clone is available.

ONNELLAB publishing targets should treat `https://onnellab.github.io/` as the canonical website root unless a project document explicitly says otherwise.

Instruction Markdown files include:

* CODEX.md
* README.md
* docs/Phase_Lock.md
* docs/Workflow.md
* docs/Content_Guide.md
* docs/SEO_Guide.md
* docs/AEO_Guide.md
* docs/GEO_Guide.md
* docs/Image_Guide.md
* docs/Publishing_Guide.md
* docs/GitHub_Actions.md
* docs/Topic_Guide.md
* docs/Knowledge_Graph.md
* docs/topics.csv
* docs/apps_registry.csv

---

# Repository Outputs

Possible outputs include:

* Blog articles
* Markdown
* HTML
* Social summaries
* Newsletter summaries
* Image specifications
* Publishing metadata

One source should support multiple destinations.

---

# Quality Rules

Every generated article should satisfy the following.

* Technically accurate
* Helpful
* Search friendly
* AI-friendly
* Easy to scan
* Long-term useful

Avoid producing content that exists only to target keywords.

---

# Relationship to ONNELLAB

This repository supports every ONNELLAB product.

Knowledge flows toward products.

Products do not dictate the educational content.

---

# Future Expansion

Future publishing targets may include:

* GitHub Pages
* RSS
* Newsletter
* X
* LinkedIn
* Reddit

The content source should remain unified.

---

# Final Principle

Teach first.

Recommend second.

Sell last.

Implementation follows documentation. Documentation does not follow implementation.
