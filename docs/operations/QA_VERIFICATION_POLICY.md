# QA verification and release gate policy

All findings require objective evidence: file path, line, test output, platform
rule, or caller/contract reference. Do not report speculation. If evidence is
missing, record `STOP`; Release Gate treats `STOP` as `FAIL`.

## Free local report generation

`scripts/run_codex_qa_report.sh TASK_ID [--review-report REVIEW.json]` is a
compatibility entrypoint for local Flutter analysis, tests, and the app-owned
performance gate. It must not invoke Codex CLI, a paid model/API, or a hosted
review service. Source review remains required, but its producer is not tied
to a paid tool. Supply an independently reviewed JSON report for the same
`task_id`, `repository`, `pr_url`, `qa_profile`, and exact recorded `commit`.

Without supplied review evidence, required review checks are `STOP` and the
unexecuted build is `not_run`. The local exit codes override supplied test,
analysis, and performance claims. Missing profile checks, device evidence, or
source integrity cannot become PASS. Ordinary development may continue while
physical-device checks are deferred; final QA/merge/release criteria remain
blocked until the required objective evidence exists.

A physical-iOS-device report is reusable only when its `task_id` and `commit`
match the recorded task and it includes a device ID, evidence, and `PASS`.
Legacy device reports without a commit remain `STOP`; do not backfill a commit
from the current checkout or infer that an earlier device run covered it.

## Required evidence

Required checks: critical bugs (only crash, data loss, permission/security
boundary), recent-change Spec/Anchor/AGENTS compliance, iOS device risks
(sandbox/path, picker/provider access, security-scoped resources, plist/
entitlements/App Groups, plugin bridges, lifecycle), caller/contract/flow side
effects, unused code, objective quality, APP_ANCHOR user scenarios, Android/
iOS platform audit, and final release gate.

Each check must be `PASS`, `FAIL`, or `STOP`; include evidence. Severity is
only `CRITICAL`, `HIGH`, or `LOW`. A final PASS additionally requires analyze
0 errors, a passing app-owned `tool/performance_gate.sh`, storage integrity,
lifecycle safety, and no Spec/Anchor/AGENTS violation. A missing performance
gate is `not_configured` and blocks merge. Ambiguity is FAIL.

The prepared QA packet selects exactly one `qa_profile`. Reports must reproduce
that value. For `flutter_riverpod_firestore_autosave_v1`, the additional
blocking checks in `FIRESTORE_AUTOSAVE_QA_PROFILE.md` are mandatory. This
conditional profile does not apply to apps without objective Riverpod,
Firestore, and autosave evidence.

For Flutter layout stabilization, perform up to ten actual edit rounds in the
app repository. Prioritize bottom actions, fixed Columns, forms/keyboards,
modal sheets, SafeArea, scrolling, text scale, and hard-coded heights. Fix
only objective overflow risks while preserving UX and Anchor/Spec. Do not pass
without an edit when a fixable structural overflow risk is found.
