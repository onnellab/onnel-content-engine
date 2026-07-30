# ChatGPT GitHub monitor

The DigitalOcean runner and GitHub remain the execution and audit systems.
ChatGPT Scheduled is read-only: it polls the normalized snapshot and recent
GitHub Actions runs, explains new findings, and links to human-only workflows.

## Create the scheduled task

Create the task from ChatGPT web or the desktop app in the chat that should
receive future alerts. Connect the GitHub tool with read access to the engine
and app repositories, then use the complete contents of
`prompts/chatgpt_github_monitor.md` as the task prompt.

- Schedule: `RRULE:FREQ=HOURLY;INTERVAL=1`
- Destination: current chat
- Mutation policy: read-only
- Expected quiet result: `NO_UPDATE`

The CLI does not manage ChatGPT Scheduled tasks. Review the first few runs in
**Scheduled**, confirm that GitHub access is available, and keep the task in the
same chat so its reported notification keys remain in context.

The snapshot intentionally contains no issue body, user report, stack trace,
credential, or command output. GitHub remains the single source of truth; the
ChatGPT task must never approve or mutate operational state.
