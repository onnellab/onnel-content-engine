# AI operations source refresh

Run the manual **Refresh AI Operations Sources** GitHub Actions workflow to
refresh the gate using the existing configured provider credentials. It runs
`scripts/refresh_ai_operations.py`, persists source outcomes even when a source
fails, and commits the refreshed records. It does not send notifications, reply
to reviews, invoke models, start builds, or submit store releases.

The refresh collects public store versions, authenticated store reviews, app
GitHub issues, official OS/store-policy page changes, configured policy
mailboxes, configured crash sources, and existing private-build/store-processing
states. It then regenerates review triage, Doctor, internal feedback findings,
Coder proposals, OS/policy impact tasks, submission readiness, and the manager
report in dependency order.

`data/ai_operations_refresh_status.json` distinguishes successful collection,
not-applicable sources, unavailable sources, and failures. Manual approvals,
QA/device results, and test feedback remain recorded evidence; inspecting these
ledgers does not run a new test or authorize a release. A zero count must not be
interpreted as fresh provider evidence when collection was unavailable.

OS and policy watchlists compare complete page hashes. A changed page requests
review; it does not establish an API change, a violation, or app compatibility.
Submission readiness describes this repository's automation/configuration and
approvals, not the provider's live review verdict.

After the workflow completes, rebuild and validate the dashboard with
`scripts/build_manual_publish_site.py --homepage-repo <homepage checkout>` and
`scripts/validate_manual_publish_site.py generated/manual-publish/index.html`,
then publish the generated artifact through the existing homepage deployment.
