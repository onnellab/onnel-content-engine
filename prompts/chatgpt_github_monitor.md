# ONNELLAB GitHub automatic-patch monitor

Run this task in the current chat once per hour. Use the connected GitHub tool
and inspect only `onnellab/onnel-content-engine` plus app repositories named by
`data/chatgpt_monitor_snapshot.json`.

1. Read `data/chatgpt_monitor_snapshot.json` from `main`.
2. Treat `notification_key` as the deduplication key. Keep keys already reported
   in this scheduled chat and report only new keys or a changed key for the same
   task.
3. Check GitHub Actions runs created during the configured lookback window for
   failed or cancelled AI-Coder, App QA, release-candidate, rework, or discard
   workflows. Deduplicate an Actions finding by its run ID.
4. For a new Draft PR item, open the PR and summarize the observed problem,
   changed files and behavior, objective verification results, QA state, and
   risk class. Do not infer a pass from a missing check.
5. Include direct links for the PR and the audited GitHub workflows for merge,
   rework, and discard. These links request human action; never merge, close,
   approve, rerun, edit, or dispatch anything from this monitoring task.
6. If the snapshot is older than two hours, report one `monitor_stale` warning.
7. If there are no new notification keys, no new failed/cancelled run IDs, and
   no stale warning, return exactly `NO_UPDATE` with no additional text.

For an alert, write concise Korean in this order: app/task, problem, change,
verification, risk, current state, and links. Never include credentials, issue
bodies, user logs, crash stack traces, or personal data.
