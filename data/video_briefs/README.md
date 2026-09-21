# Durable video brief inbox

Commit production JSON briefs here only when the automated authoring pass has grounded them in real local footage and repository facts; no per-video human review is required.
See `video/brief.schema.json` and `docs/Short_Video_Pipeline.md`. No sample JSON is
automatically enqueued. Relative media paths refer to the persistent worker's
private asset root. Never commit media, credentials, tokens, sessions or state.
Reusing an idempotency key with different content fails. Retain processed briefs;
re-reading identical files is a no-op. Editing a brief requires a new key.

The one-shot upload worker applies `data/video_publish_policy.json`, creates a hash-bound automatic attestation, and publishes only when all fail-closed gates pass. Uncertainty stays blocked.
