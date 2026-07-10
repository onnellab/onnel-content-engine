# Phase Lock

## ONNELLAB Content Engine

---

# 1. Purpose

This document locks the implementation phases for the ONNELLAB Content Engine.

The phase order must not be simplified, renamed, reordered, skipped, or bypassed without updating this document explicitly.

Implementation follows the locked phases.

The locked phases do not follow ad hoc implementation decisions.

---

# 2. Locked Phase Order

## Phase 1

Foundation

✅

---

## Phase 2

Topic Management

✅

---

## Phase 3

Markdown Generator

✅

---

## Phase 4

Image Specification

✅

---

## Phase 5

Internal Linking

✅

---

## Phase 6

Publishing

✅

---

## Phase 7

Automation

✅

---

# 3. Phase Gate Rules

Each phase must remain independently understandable and independently verifiable.

No phase may silently perform the responsibility of another phase.

Validation must stop the pipeline when a required previous phase is invalid.

Automation must not bypass any phase gate.

---

# 4. Ownership Rules

Phase names are canonical.

Phase order is canonical.

New phases may be added only after the locked sequence unless a project document explicitly changes the phase architecture.

---

# Final Principle

Lock the foundation.

Respect the sequence.

Advance only through valid gates.
