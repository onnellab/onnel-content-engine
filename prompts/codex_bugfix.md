# ONNELLAB constrained bug-fix task

Read one approved task in `data/ai_coder_tasks.json`. Work only in the named
app repository and create a dedicated branch and **draft PR**. Before changing
code, inspect the finding and reproduce the issue or add a failing test.

Never merge, deploy, publish, alter release signing, or access production
secrets. Stop and report if the task affects billing, authentication, privacy,
cryptography, database migrations, or cannot be reproduced. Include the
reproduction evidence, changed files, tests run, risk, and rollback note in the
draft PR body.

After creating the Draft PR, request **Run App QA Gate** with the exact task
ID, repository, branch/commit, and PR URL. Do not request human merge approval
until the QA artifact is complete.

When invoked by `run_codex_approved_coder_task.sh`, do not create the branch,
commit, push, or PR yourself. The runner performs those audited actions only
after checking the resulting diff.
