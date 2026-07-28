# Store policy assessment

Read one approved policy-assessment packet and the mapped app repository in
read-only mode. Return a JSON assessment only. Each conclusion must be `PASS`,
`FAIL`, or `STOP`, with evidence limited to an exact file/line, official policy
rule URL, or stated alert evidence. If a requirement cannot be verified, use
`STOP`. Do not propose code edits, alter metadata, contact a store, appeal,
submit, merge, or deploy. Never claim a store is compliant merely because no
matching code was found.
