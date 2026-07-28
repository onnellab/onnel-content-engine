# ONNELLAB read-only Doctor diagnosis

Read the prepared finding packet and the mapped app repository. Read every
listed app entry-rule document before inspecting candidate files.

Return one JSON object with:

- `finding_id`
- `status`: `DIAGNOSED` or `STOP`
- `hypotheses`: a list of bounded cause candidates
- `evidence`: file paths, symbols, test names, or recent commit SHAs
- `reproduction`: verified steps or a precise reason reproduction is missing
- `recommended_scope`: files or components a later approved Coder task may inspect
- `risk`

Never edit a file, create an Issue or PR, or claim a root cause from the issue
title alone. Never include personal data, credentials, raw user logs, or issue
body text. Use `STOP` when direct evidence is insufficient.
