#!/usr/bin/env bash
set -euo pipefail

CONTENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="/tmp/onnel-content-supply.lock"
LOG_DIR="/tmp/onnel-content-supply-runs"
PROMPT_FILE="${CONTENT_ROOT}/prompts/codex_content_supply.md"

mkdir -p "${LOG_DIR}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "content supply run skipped: another run holds ${LOCK_FILE}"
  exit 0
fi

cd "${CONTENT_ROOT}"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "content supply run refused: repository has uncommitted changes" >&2
  exit 1
fi

git pull --rebase origin main
if python3 scripts/check_content_supply.py --require-healthy --minimum-ideas 8; then
  echo "content supply already healthy; Codex usage not required"
  exit 0
fi
codex login status 2>&1 | grep -q "Logged in using ChatGPT"

RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_LOG="${LOG_DIR}/${RUN_STAMP}.log"
codex --search \
  --sandbox workspace-write \
  --ask-for-approval never \
  --cd "${CONTENT_ROOT}" \
  exec --ephemeral \
  - < "${PROMPT_FILE}" | tee "${RUN_LOG}"

python3 scripts/validate_topics.py
python3 scripts/validate_foundation.py
python3 scripts/check_content_supply.py --require-qualified-pair
python3 -m unittest tests.test_publication_automation tests.test_publishing

ALLOWED_PATHS=(
  data/topics.csv
  topics/topics.csv
  generated/markdown
  generated/images
  generated/assets/blog
  generated/metadata
  generated/reviews
)

UNEXPECTED="$(git status --porcelain | awk '{print $2}' | while read -r path; do
  allowed=false
  for prefix in "${ALLOWED_PATHS[@]}"; do
    if [[ "${path}" == "${prefix}" || "${path}" == "${prefix}/"* ]]; then
      allowed=true
      break
    fi
  done
  if [[ "${allowed}" == false ]]; then
    echo "${path}"
  fi
done)"
if [[ -n "${UNEXPECTED}" ]]; then
  echo "content supply run refused unexpected changes:" >&2
  echo "${UNEXPECTED}" >&2
  exit 1
fi

if git diff --quiet -- "${ALLOWED_PATHS[@]}" && [[ -z "$(git ls-files --others --exclude-standard -- "${ALLOWED_PATHS[@]}")" ]]; then
  echo "content supply already healthy; no content commit required"
  exit 0
fi

git add "${ALLOWED_PATHS[@]}"
git diff --cached --check
git commit -m "Replenish bilingual content supply"
git pull --rebase origin main
git push origin main
echo "content supply committed and pushed successfully"
