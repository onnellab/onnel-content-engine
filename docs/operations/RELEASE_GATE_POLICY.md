# Release gate policy

Public release publication is never triggered by a push. It requires a manual
workflow dispatch with the exact `RELEASE` confirmation. Before dispatch, the
operator must confirm a human-approved merge, QA Release Gate PASS, release
artifact availability, version/tag consistency, and release notes accuracy.
If any condition is unknown, do not dispatch the release workflow.

Store warnings, rejections, and policy deadlines are recorded with the
**Record Store Policy Alert** manual workflow. It stores only a sanitized
summary and an official reference URL, then creates an evidence-only review
task. It never submits a response, appeal, metadata update, or release.
