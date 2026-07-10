# Workflow

## ONNELLAB Content Engine

---

# 1. Purpose

This document defines the permanent content production workflow for the ONNELLAB Content Engine.

Every article, infographic, and published asset must follow this workflow.

The purpose of this document is to guarantee consistency, scalability, and automation readiness.

---

# 2. Core Philosophy

The workflow exists to separate thinking from publishing.

Every stage has a single responsibility.

No stage should perform the work of another.

Knowledge should become content.

Content should become assets.

Assets should become publications.

---

# 3. Complete Workflow

```text id="workflow_pipeline"
Topic

↓

Research

↓

Outline

↓

Article

↓

Image Planning

↓

Image Production

↓

Review

↓

Publishing

↓

Archive
```

Each stage produces an output for the next stage.

No stage should be skipped.

---

# 4. Phase 1

## Topic Selection

### Goal

Identify a real question that users are actively asking.

Topics should originate from:

* User problems
* Frequently asked questions
* Product documentation
* Feature requests
* Community discussions
* Search intent

Never create articles solely to promote products.

---

### Output

One approved topic.

Example:

```text id="topic_example"
How to organize MP3 metadata correctly
```

---

# 5. Phase 2

## Research

### Goal

Collect objective information needed to answer the topic.

Research should answer:

* What is the problem?
* Why does it happen?
* What solutions exist?
* Which solution is most appropriate?

Product references are intentionally excluded during this phase.

---

### Output

Structured research notes.

---

# 6. Phase 3

## Outline

### Goal

Transform research into a structured article outline.

Every outline should include:

* Introduction
* Problem
* Explanation
* Solution
* Practical advice
* Product recommendation (optional)
* Related articles

The outline should define structure, not wording.

---

### Output

Article outline.

---

# 7. Phase 4

## Article Writing

### Goal

Write the complete article.

Every article should:

* solve the user's problem
* remain technically accurate
* be easy to scan
* be easy to understand
* remain useful over time
* be prepared in both English and Korean before public publication

Product recommendations must appear only after the educational content.

---

### Output

Markdown article.

---

# 8. Phase 5

## Image Planning

### Goal

Determine which visuals improve understanding.

Images should explain.

Not decorate.

Possible image types:

* Workflow diagrams
* Before / After
* Comparison tables
* Architecture diagrams
* Process illustrations
* UI examples

Every image must support the article.

---

### Output

Image specification document.

---

# 9. Phase 6

## Image Production

### Goal

Create the planned visuals.

Visual style should follow the ONNELLAB Design System.

Images should maintain consistent:

* typography
* spacing
* colors
* icons
* layout

Every infographic should be recognizable as ONNELLAB content.

If an image contains readable text, English and Korean versions must be produced separately before publication.

---

### Output

Publish-ready images.

---

# 10. Phase 7

## Review

### Goal

Verify quality before publication.

Review checklist:

* Technical accuracy
* Grammar
* Structure
* Readability
* Product references
* Internal links
* Image quality
* Image layout and language-specific image text
* English and Korean counterparts
* Translation quality
* Article review score greater than `9.0 / 10`

Publishing should never bypass review.

An article that scores `9.0 / 10` or lower remains in review.

---

### Output

Approved publication package.

---

# 11. Phase 8

## Publishing

### Goal

Publish the article.

Possible destinations:

* ONNELLAB Blog
* RSS
* Newsletter
* Social platforms
* Future publication targets

The original Markdown remains the canonical source.

---

### Output

Published article.

---

# 12. Phase 9

## Archive

### Goal

Store all production assets.

Every publication should preserve:

* Markdown
* Images
* Metadata
* Publishing date
* Category
* Related applications

No published asset should be lost.

---

# 13. Automation Boundaries

The workflow is designed for automation.

Automation is encouraged for:

* Topic scheduling
* Draft generation
* Image generation
* Metadata creation
* Internal link recommendation
* Publishing
* Archiving

Automation may prepare article drafts, image assets, and internal link recommendations ahead of the publication date.

Publication automation must still enforce the review threshold and the three-day publication interval.

---

# 14. Failure Handling

If any phase fails:

* Stop the pipeline.
* Record the reason.
* Return to the previous completed stage.
* Never publish incomplete content.

Automation should fail safely.

---

# 15. Future Expansion

Additional workflow stages may be inserted.

Existing stages should not change order.

The overall production philosophy must remain stable.

---

# 16. Completion Criteria

A workflow cycle is complete only when:

* The article has been published.
* Supporting assets have been archived.
* Metadata has been updated.
* The topic has been marked as completed.

---

# Final Principle

Questions become knowledge.

Knowledge becomes content.

Content becomes trust.

Trust builds the ONNELLAB ecosystem.
