#!/usr/bin/env bash
# Safe unattended local Codex cycle: review drafts only, never publication.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
git diff --quiet && git diff --cached --quiet || { echo "refusing scheduled run: worktree has local changes" >&2; exit 1; }
git pull --ff-only origin main
bash scripts/run_codex_review_drafts.sh
allowed='^(data/store_review_ai_drafts\.json|generated/review-replies/review_packet\.(json|md))$'
changed="$(git diff --name-only)"
if [[ -n "$changed" ]] && ! printf '%s\n' "$changed" | rg -v "$allowed" >/dev/null; then
  git add data/store_review_ai_drafts.json generated/review-replies/review_packet.json generated/review-replies/review_packet.md
  git diff --cached --quiet || git commit -m "Generate local Codex review drafts"
  git push origin HEAD:main
else
  [[ -z "$changed" ]] || { echo "unexpected scheduled-run change; refusing commit" >&2; exit 1; }
fi
echo "Local AI Scout cycle completed; drafts remain pending human approval."
