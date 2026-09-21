#!/bin/sh
# Operator configures these in the service environment; no eval or shell snippets.
set -eu
: "${VIDEO_REPO:?Set VIDEO_REPO}"
: "${VIDEO_ASSETS:?Set VIDEO_ASSETS}"
: "${VIDEO_STATE:?Set VIDEO_STATE}"
: "${VIDEO_BROWSER:?Set VIDEO_BROWSER}"
exec "${VIDEO_PYTHON:-python3}" -B "$VIDEO_REPO/scripts/short_video.py" \
  --asset-root "$VIDEO_ASSETS" --state-root "$VIDEO_STATE" --browser "$VIDEO_BROWSER" \
  worker --once --inbox "$VIDEO_REPO/data/video_briefs" --upload --execute
