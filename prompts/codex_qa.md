# ONNELLAB Draft PR QA

Read `docs/operations/QA_VERIFICATION_POLICY.md` first. For an approved
AI-Coder task and its draft PR, run relevant tests, production build, and
static analysis. Write `qa_report.json` with `task_id`, `repository`, `pr_url`,
`qa_profile`, `tests`, `build`, `static_analysis`, `performance`, `risk`,
`rollback`, and `checks`. `qa_profile` must exactly reproduce the packet value.
`performance` must reproduce the prepared app-specific
`tool/performance_gate.sh` result; a missing gate is `not_configured`, never a
pass.
`checks` must cover every required policy check with `status` (PASS/FAIL/STOP),
severity (CRITICAL/HIGH/LOW), and objective evidence. Use `No action required`
only for PASS with evidence. Do not merge, deploy, weaken tests, or mark a
skipped check as passed. For actual Flutter app repos, run the layout
stabilization edit mode in the policy. Validate with
`python3 scripts/validate_ai_qa_report.py qa_report.json`.

When `qa_profile` is `flutter_riverpod_firestore_autosave_v1`, also read
`docs/operations/FIRESTORE_AUTOSAVE_QA_PROFILE.md` and include every blocking
profile check. Treat the app's committed rules as the source of truth for exact
debounce duration, save-button policy, status tone, and listener budget. Do not
apply that profile to unrelated apps and do not provide replacement source code
in a read-only QA report.

When the input packet says `ios_device_required: true`, a `PASS` for
`ios_device_risk` requires an attached physical-device report whose status is
`PASS`. A missing, `FAIL`, or `STOP` device report requires `STOP`; static
inspection and unsigned iOS builds cannot replace this evidence.
