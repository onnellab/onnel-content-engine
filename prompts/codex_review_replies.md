# ONNELLAB personalized review replies

Read `generated/review-replies/review_packet.json`. Create or update only
`data/store_review_ai_drafts.json` with this exact shape:

```json
{"schema_version":1,"drafts":[{"review_id":"...","reply":"...","source":"codex","facts":[...]}]}
```

Write a distinct, concise reply for every review. Refer to the specific concern
in natural language, but do not copy the review verbatim. Use only supplied
facts. Never claim an unverified cause, fix, release date, refund result, or
future feature. Never ask for personal data in public. Keep the review's
language where practical; otherwise use English. Do not publish, queue, commit,
or edit any other file. Run `python3 scripts/validate_store_review_drafts.py`
before returning the draft file for approval.
