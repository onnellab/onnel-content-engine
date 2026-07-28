#!/usr/bin/env bash
set -euo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$script_root/scripts/generate_ai_review_drafts.py"

codex exec -s workspace-write -C "$script_root" \
  "Read generated/review-replies/review_packet.md and prompts/codex_review_replies.md. Create or update only data/store_review_ai_drafts.json. Do not commit, push, publish, queue replies, create issues, or edit any other file. Then run python3 scripts/validate_store_review_drafts.py. If it fails, fix only data/store_review_ai_drafts.json and rerun it."

python3 "$script_root/scripts/validate_store_review_drafts.py"

unexpected="$(git -C "$script_root" diff --name-only -- . ':!data/store_review_ai_drafts.json' ':!generated/review-replies/review_packet.json' ':!generated/review-replies/review_packet.md')"
if [[ -n "$unexpected" ]]; then
  printf 'Codex changed files outside the allowed review-draft scope:\n%s\n' "$unexpected" >&2
  exit 1
fi

printf 'Codex personalized review drafts are ready for human review.\n'
