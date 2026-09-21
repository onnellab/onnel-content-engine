# Durable video brief inbox

Commit production JSON briefs here only after reviewing the real local footage.
See `video/brief.schema.json` and `docs/Short_Video_Pipeline.md`. No sample JSON is
automatically enqueued. Relative media paths refer to the persistent worker's
private asset root. Never commit media, credentials, tokens, sessions or state.
Reusing an idempotency key with different content fails. Retain processed briefs;
re-reading identical files is a no-op. Editing a brief requires a new key.
