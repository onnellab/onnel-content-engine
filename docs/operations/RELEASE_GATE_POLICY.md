# Release gate policy

Public release publication is never triggered by a push. It requires a manual
workflow dispatch with the exact `RELEASE` confirmation. Before dispatch, the
operator must confirm a human-approved merge, QA Release Gate PASS, release
artifact availability, version/tag consistency, and release notes accuracy.
If any condition is unknown, do not dispatch the release workflow.

A public binary store-submission approval also requires a passing Release
Candidate report for the linked task. iOS apps additionally require a recorded
physical-device QA `PASS`; an unsigned iOS build cannot substitute for it.

Store warnings, rejections, and policy deadlines are recorded with the
**Record Store Policy Alert** manual workflow. It stores only a sanitized
summary and an official reference URL, then creates an evidence-only review
task. It never submits a response, appeal, metadata update, or release.
