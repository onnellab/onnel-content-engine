# ONNELLAB Draft PR QA

For an approved AI-Coder task and its draft PR, run the app repository's
relevant unit/integration tests, production build, and static analysis. Write
`qa_report.json` with: `task_id`, `repository`, `pr_url`, `tests`, `build`,
`static_analysis`, `risk`, and `rollback`. Use `passed` only with actual output.
Do not merge, deploy, weaken tests, or mark a skipped check as passed. Validate
with `python3 scripts/validate_ai_qa_report.py qa_report.json` from this repo.
