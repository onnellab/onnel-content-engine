# ONNELLAB Draft PR QA

Read `docs/operations/QA_VERIFICATION_POLICY.md` first. For an approved
AI-Coder task and its draft PR, run relevant tests, production build, and
static analysis. Write `qa_report.json` with `task_id`, `repository`, `pr_url`,
`tests`, `build`, `static_analysis`, `risk`, `rollback`, and `checks`.
`checks` must cover every required policy check with `status` (PASS/FAIL/STOP),
severity (CRITICAL/HIGH/LOW), and objective evidence. Use `No action required`
only for PASS with evidence. Do not merge, deploy, weaken tests, or mark a
skipped check as passed. For actual Flutter app repos, run the layout
stabilization edit mode in the policy. Validate with
`python3 scripts/validate_ai_qa_report.py qa_report.json`.
