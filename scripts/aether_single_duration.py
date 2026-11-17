"""New-single editorial duration contract; never alters historical job prompts."""
MIN_DURATION_SECONDS = 160.0
MAX_DURATION_SECONDS = 210.0
TARGET_DURATION_SECONDS = 184.0

# Google describes 184 seconds as a maximum, not a guaranteed output length.
# Applied only when choosing an unused new scheduled concept. Existing jobs,
# manifests, receipts, sleep compositions and backlog styles are not rewritten.
NEW_SINGLE_DURATION_DIRECTION = (
    " Compose a complete 180-184-second instrumental (about 3 minutes), not a short cue. "
    "Develop the music through at least 02:40, then resolve naturally by 03:04. "
    "Keep musical development active until the final cadence; do not substitute "
    "silence, repeated audio, or an early fade for the requested duration."
)
