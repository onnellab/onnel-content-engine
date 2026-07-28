# Release gate policy

Public release publication is never triggered by a push. It requires a manual
workflow dispatch with the exact `RELEASE` confirmation. Before dispatch, the
operator must confirm a human-approved merge, QA Release Gate PASS, release
artifact availability, version/tag consistency, and release notes accuracy.
If any condition is unknown, do not dispatch the release workflow.
