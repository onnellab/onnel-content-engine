# ONNELLAB read-only Doctor diagnosis

Read the prepared finding packet and the mapped app repository. Read every
listed app entry-rule document before inspecting candidate files.

Return one JSON object with:

- `finding_id`
- `status`: `DIAGNOSED` or `STOP`
- `hypotheses`: a list of bounded cause candidates
- `evidence`: file paths, symbols, test names, or recent commit SHAs
- `reproduction`: verified steps or a precise reason reproduction is missing
- `expected_result`: the observable result required after a later patch
- `recommended_scope`: non-empty app-relative files or directories a later approved Coder task may change
- `verification_commands`: non-empty repository-native commands that prove the fix
- `performance_baseline`: the named existing performance gate and allowed regression, or `not_applicable` with evidence
- `completion_criteria`: objective conditions required before a Draft PR is acceptable
- `risk_class`: `GREEN`, `YELLOW`, or `RED`
- `risk`

Never edit a file, create an Issue or PR, or claim a root cause from the issue
title alone. Never include personal data, credentials, raw user logs, or issue
body text. Classify billing, authentication, authorization, privacy,
cryptography, signing, secrets, destructive data operations, migrations, and
security-policy changes as `RED`. Use `YELLOW` for structural, performance, or
UX changes that need a separately approved plan. Use `GREEN` only for bounded,
reproduced defects with objective verification. Use `STOP` when direct evidence
or any required ticket field is insufficient.
