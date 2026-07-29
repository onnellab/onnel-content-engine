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
python3 scripts/triage_store_reviews.py
python3 scripts/build_manual_publish_site.py
```

The dashboard's **Store review connection** panel accepts a newly issued Apple
Key ID, Issuer ID, and `.p8` private key plus a Google Play service account
JSON and the Play lifetime review reports URI (`gs://pubsite_prod_.../reviews/`), then
prepares the local env and GitHub Actions secret-sync commands. The reports
bucket is required because the reviews API only exposes the previous week. The
private credentials are not embedded in the generated dashboard and are
cleared from the form on refresh.

The hosted form encrypts these values with the repository's GitHub Actions
public key and can save them directly to Actions Secrets before dispatching the
review sync workflow.

The dashboard shows synchronized reviews and creates Korean or English reply
drafts from the repository-managed templates. It also creates a deterministic
triage snapshot with risk flags, approved facts, repeated-review counts, and
approval-only GitHub issue drafts. Every draft requires human review and manual
publication. See `docs/Store_Review_Response_Guide.md`.

## Approved AI-Coder tasks

After a task has been approved through **Approve AI Coder Task**, a signed-in
local Codex environment can create exactly one audited Draft PR:

```bash
scripts/run_codex_approved_coder_task.sh TASK_ID --execute
```

The runner clones the approved repository into a new temporary workspace,
creates a dedicated branch from `origin/main`, blocks changes outside the
ticket's approved paths, runs the repository quality gate, and only then
pushes a Draft PR. The temporary clone is deleted after the run, so a failed
patch cannot contaminate a long-lived app checkout. It never merges, deploys,
publishes, or changes store settings. The generated PR must still pass the QA
and human merge gates.

The approval workflow can continue automatically on a dedicated self-hosted
runner only when repository variable `AI_CODER_RUNNER_ENABLED` is exactly
`true`. The runner must carry the `onnellab-ai-coder` label, have Codex already
signed in, and receive the scoped `AI_CODER_GITHUB_TOKEN` secret. Missing
configuration fails before app mutation; the default disabled state records
approval without queueing Coder work. A successful run commits the Draft PR
URL, branch, and commit back to the task audit ledger.

All Coder executions share the `ai-coder-global` concurrency group, so the
dedicated runner processes exactly one patch at a time even when different
tasks are approved together. Every task must record the symptom, reproduction,
expected result, allowed and prohibited paths, verification commands,
performance baseline, completion criteria, and explicit `GREEN`, `YELLOW`, or
`RED` risk class. `RED` is never executable. `YELLOW` requires the separate
plan-approval checkbox before any repository is cloned.

Install `@openai/codex-security` on the dedicated runner. Unless repository
variable `AI_CODER_SECURITY_SCAN_ENABLED` is explicitly `false`, the runner
scans only the uncommitted patch with `codex-security scan --working-tree`
after the app quality gate. High/critical findings, incomplete coverage, or a
scanner error stop the run before commit and PR creation. This optional gate
requires Node.js 22 or later and an authenticated Codex Security installation;
scan artifacts remain in a private temporary directory outside the app clone
and are deleted after the run. The gate uses the runner's authenticated Codex
account; disabling it requires an explicit repository-variable change.

When an app was created from `onnellab-flutter-template`, the runner uses its
`tool/quality_gate.sh` instead of the basic analysis/test fallback. That keeps
formatting, patch-note, and app-specific safety rules in the app repository as
the source of truth.

All local Codex Coder, QA, and policy-assessment runners read template app
entry rules (`AGENTS.md`, `CODEX_BOOT.md`, `CODEX.md`, and the skill index)
when present. Those app-level constraints override the engine's generic task
prompt.

Apps declaring `.onnellab-template-version` are checked by the App QA Gate for
their required template entry rules, quality-gate scripts, and Korean/English
patch-note/store-copy documents. Apps without the marker remain supported as
legacy apps rather than being falsely treated as template compliant.

For a template-based app, **Propose App Template Quality Gate Sync** creates a
Draft PR containing only `.github/workflows/ci.yml`, `tool/quality_gate.sh`,
and `tool/verify_patch_notes.sh` from a selected template ref. It requires the
explicit `TEMPLATE_SYNC` confirmation, creates no PR when those files already
match, and never merges or deploys.

For a recorded Draft PR, generate the detailed read-only Codex QA report:

```bash
scripts/run_codex_qa_report.sh TASK_ID
```

It runs Flutter analysis and tests, then asks Codex to emit the required
evidence-only QA JSON. A missing objective iOS/device fact produces `STOP`,
which correctly prevents the merge gate from passing.

The GitHub **Run App QA Gate** follows the Flutter template's portable gates:
format verification, analyze, tests, template patch-note validation when
provided by the app, the app-owned `tool/performance_gate.sh`, Android debug
APK, and Android release AAB. A missing or failing performance gate is
recorded and blocks merge rather than being treated as a pass. A newly created
audited Draft PR automatically dispatches this portable QA workflow. iOS
archive and device verification remain a macOS/Codemagic gate rather than a
Linux substitute.

Use **Run App Release Candidate Gate** after the detailed QA report passes. It
runs on macOS and records Flutter dependency resolution, analysis, tests,
Android release AAB, and iOS `--no-codesign` release build results. It does not
sign, upload, submit, or deploy anything, and it is not a substitute for an
iOS real-device gate.

On a signed-in macOS QA machine, run a real-device integration test with:

```bash
scripts/run_ios_device_qa.sh TASK_ID IOS_DEVICE_ID --execute
```

The runner rejects simulators, requires a recorded Draft PR, and stores a
`PASS`, `FAIL`, or `STOP` evidence report. If no integration test exists, it
records `STOP` instead of treating an unsigned build as device verification.
It refuses a dirty engine worktree and commits the resulting evidence report
before returning, including `FAIL` and `STOP` results.

For iOS apps, the local Codex QA packet now includes that physical-device
report. Without a recorded device `PASS`, the iOS device-risk check must stay
`STOP`, which blocks the final merge gate.

## Sentry crash collection

Add each app's Sentry organization/project and platform to
`data/sentry_crash_sources.json`, then store a read-only `SENTRY_AUTH_TOKEN`
in GitHub Actions secrets. The daily collector imports unresolved issues into
the crash ledger and regenerates Doctor, Coder, and Manager outputs. Without a
token it records `token_missing` and exits successfully; it never silently
uses a personal browser session.

Firebase Crashlytics can use the same ledger through
`data/crashlytics_crash_sources.json` and a short-lived
`FIREBASE_CRASHLYTICS_ACCESS_TOKEN` secret. It imports issue metadata only,
never crash stack traces or user reports. The collector uses Firebase's
official Crashlytics REST API and records `not_configured` or `token_missing`
until a dedicated read-only OAuth integration is available.

The daily **Collect GitHub Issues** workflow reads open Issue metadata from
every app repository in `data/app_release_config.csv`. It excludes pull
requests and deliberately stores no issue body, author, comment, attachment,
or log content. Open/closed observations are preserved in
`data/github_issues.json`; the monitor cannot edit or close an app issue.

## Local Codex Scout schedule

On a Linux/WSL machine where Codex is already signed in, install the daily
draft-only timer manually:

```bash
scripts/install_local_ai_scout_timer.sh
```

It runs at 09:15 local machine time, refuses a dirty worktree, creates only
review draft packets, validates them, and commits only those allowed files.
It never approves or publishes replies, creates issues, runs Coder tasks,
merges PRs, submits builds, or deploys.

The same local cycle prepares bounded code context for pending high-risk
Doctor findings and runs Codex in read-only mode. It records recent commits,
candidate code paths, reproduction evidence, and a `DIAGNOSED` or `STOP`
result. Only `DIAGNOSED` findings may become proposed Coder tasks; diagnosis
still grants no permission to edit code or create a PR.

## Store submission gate

Public binary releases require a passing detailed QA report and a human
**Approve Store Submission** workflow confirmation before they can become
submission candidates. `evaluate_store_submission_readiness.py` records the
exact blocking reason. This gate never uploads an AAB/IPA, changes store
metadata, submits a review, or releases an app; provider connections remain
disabled until separately configured.

## Manager notification

The daily Manager report can update one GitHub issue instead of creating
repeated alerts. GitHub Issue notification is disabled because this repository
is public; enable it only after selecting a private operations repository. The
report summarizes pending Coder approvals, Draft PRs, portable QA
passes/blocks, and private-test/store gates, then links to existing human
approval workflows. It is informational and cannot authorize any action.

For Slack, Discord, or a generic HTTPS webhook, enable
`data/ai_manager_webhook_config.json` and set the
`OPS_MANAGER_WEBHOOK_URL` Actions secret. Only the Manager summary is sent;
credentials, review text, telemetry, and approval controls are never sent.

For a Telegram summary with links to the existing audited GitHub approval
workflows, enable `data/ai_manager_telegram_config.json` and set the
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` Actions secrets. Telegram buttons
open GitHub workflow pages; they never approve, merge, publish, or deploy
through Telegram callbacks.

Before enabling any future Play/App Store upload adapter, run **Check Store
Submission Credentials** with `CREDENTIALS`. It validates only the Secret
shape and never contacts a store API, uploads a binary, or submits a build.

**Submit Internal Store Build** accepts only a `private_test` binary release.
It uploads Android builds solely to Play `internal` and iOS builds solely to
TestFlight. It cannot submit App Review, promote a Play release, or publish to
customers. Configure the per-app package/bundle identifier in
`data/internal_store_submission_config.json` before use.
The workflow resolves the selected release's Codemagic artifact at run time,
calculates and validates its SHA-256 metadata, and does not commit the binary
to this repository.
Run **Check Internal Test Readiness** first to perform those checks plus the
relevant credential-shape check without contacting or uploading to a store.
**Submit Internal Store Build** requires a matching successful preflight,
including the exact SHA-256, before it can upload.
Use **Start Private Test Orchestration** for the one-approval chain. It advances
merge, platform build, readiness, and internal upload only after each recorded
gate succeeds; a dispatched stage that produces no evidence for six hours is
marked failed instead of progressing.
Use **Retry Private Test Orchestration** after fixing a recorded failure. It
resumes from the latest safe evidence and preserves previous attempts. An
ambiguous store-upload outcome cannot be retried until the console is checked.
For that exact timeout, use **Reconcile Internal Store Upload** after checking
the official Play Console or App Store Connect page. Record `uploaded` to close
the orchestration without another upload, or `not_uploaded` to dispatch only
the already-preflighted upload again. Both outcomes require a human approver,
an official console HTTPS evidence URL, and retain a separate reconciliation
audit in `data/internal_store_upload_reconciliations.json`.
For a merged Coder task, **Dispatch Private Test Build** starts exactly one
mapped Codemagic app/workflow/branch build after `BUILD_PRIVATE_TEST` approval.
Set its mapping in `data/codemagic_builds.csv`; the mapped branch must still
resolve to the recorded merge SHA. The approved workflow then creates one
immutable `private-test/...` Git tag and builds that tag; it never submits a
store build.
Each successful upload is recorded in `data/internal_store_submissions.json`
with its workflow-run URL and SHA-256; this audit record does not promote or
publish it.

**Sync Internal Store Processing Status** checks pending uploads hourly through
the official Android Publisher and App Store Connect APIs. It records the
provider state, exact Android version code or Apple build ID, official API URL,
check time, and state-change history in
`data/internal_store_processing_status.json`. The Play API requires a temporary
edit to read the internal track; the collector always deletes that edit and
never commits it. The collector cannot upload, promote, submit for review, or
mark a build available to testers.

After Play/TestFlight processing completes, use **Approve Internal Test
Availability** with console evidence. Only then can **Record Internal Test
Feedback** accept reports for that build.

Use **Record Internal Test Feedback** to log only a short issue summary and
reproduction steps for an uploaded build. Do not enter personal data, passwords,
tokens, logs, or files. Crash, data-loss, and security reports become proposed
reproduction-first Coder tasks and still require a separate human approval.

After testing, use **Approve Internal Test Result** with an HTTPS evidence link.
A PASS is blocked while that build has high/critical internal-test findings.
The result is an audit record only: it cannot promote, submit, or publish a
release.

To require this result before public submission preparation, set `enabled` to
`true` in `data/internal_test_gate_config.json`. An empty `required_apps` list
applies it to every app; otherwise list the app slugs to protect. The gate then
requires a passed private-test build with the same app, platform, and version.

## Store-alert mailbox

`collect_gmail_policy_alerts.py` supports a dedicated Gmail label using OAuth
refresh-token secrets. It reads only message metadata for exact configured
sender and subject mappings. It stores neither email bodies nor addresses;
only a non-reversible message fingerprint and the mapped app/store/kind are
kept. Leave `data/gmail_policy_alert_config.json` disabled until a dedicated
mailbox, label, and exact mapping rules are ready.

Policy tasks require a separate `ASSESS` approval before a local Codex
read-only assessment packet can be generated. That approval does not permit a
patch, store response, appeal, submission, or release.

Run one approved assessment with:

```bash
scripts/run_codex_policy_assessment.sh TASK_ID
```

The runner uses Codex read-only mode and rejects results unless they explicitly
state `patch_authorized: false` with evidence references.

Only a recorded policy `FAIL` can be escalated with **Create Policy Remediation
Task**. It creates a *proposed* AI-Coder task, so the normal separate Draft PR
approval remains mandatory. Restricted security, privacy, billing, auth,
cryptography, migration, signing, and store-metadata changes remain blocked.
The escalation must name an exact remediation scope and app-relative allowed
file paths; the Coder runner rejects every policy-remediation diff outside that
allowlist.

Approved replies are recorded in `data/store_review_approvals.json` before any
publisher may consume them. The approval CLI is useful for audited local use:

```bash
python3 scripts/store_review_approvals.py REVIEW_ID --reply "Approved reply" --approver "your-name"
```

To create personalized drafts without an API, run
`python3 scripts/generate_ai_review_drafts.py`, then give
`generated/review-replies/review_packet.md` to Codex with
`prompts/codex_review_replies.md`.

On a machine signed into the Codex CLI, run the full local draft-only workflow:

```bash
bash scripts/run_codex_review_drafts.sh
```

It permits only the review-draft file and packet outputs, validates the result,
and never publishes, queues, commits, or pushes.

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
