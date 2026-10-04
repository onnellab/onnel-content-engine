#!/usr/bin/env bash
set -euo pipefail

CONTENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="/tmp/onnel-content-supply.lock"
LOG_DIR="/tmp/onnel-content-supply-runs"
mkdir -p "${LOG_DIR}"
RUN_LOG="$(mktemp "${LOG_DIR}/$(date +%Y%m%d-%H%M%S)-XXXXXX.log")"
exec > >(tee -a "${RUN_LOG}") 2>&1
WORK_ROOT=""
finish() {
  result=$?
  echo "content supply exit=${result}; log=${RUN_LOG}"
  if [[ -n "${WORK_ROOT}" ]]; then
    rm -rf -- "${WORK_ROOT}"
  fi
}
trap finish EXIT
echo "content supply preflight; source=${CONTENT_ROOT}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "content supply run skipped: another run holds ${LOCK_FILE}"
  exit 0
fi

# Check both the temporary clone volume and the Windows system volume under WSL.
for volume in /tmp /mnt/c; do
  [[ -d "${volume}" ]] || continue
  available_kib="$(df -Pk "${volume}" | awk 'NR == 2 {print $4}')"
  if [[ ! "${available_kib}" =~ ^[0-9]+$ ]] || (( available_kib < 10485760 )); then
    echo "content supply refused: ${volume} requires at least 10 GiB free"
    exit 1
  fi
done

# Never pull, reset, stash, or write into the installed checkout (which may be dirty).
ORIGIN="$(git -C "${CONTENT_ROOT}" remote get-url origin)"
WORK_ROOT="$(mktemp -d /tmp/onnel-content-supply-work-XXXXXX)"
git clone --quiet --single-branch --branch main -- "${ORIGIN}" "${WORK_ROOT}/repo"
cd "${WORK_ROOT}/repo"
BASE_HEAD="$(git rev-parse HEAD)"
echo "content supply isolated origin/main=${BASE_HEAD}"
if python3 scripts/check_content_supply.py --require-healthy --minimum-ideas 8; then
  echo "content supply already healthy; Codex usage not required"
  exit 0
fi
LOGIN_STATUS="$(codex login status 2>&1)"
if [[ "${LOGIN_STATUS}" != *"Logged in using ChatGPT"* ]]; then
  echo "content supply refused: ChatGPT subscription login required"
  exit 1
fi
codex --search \
  --sandbox workspace-write \
  --ask-for-approval never \
  --cd "${PWD}" \
  exec --ephemeral \
  - < prompts/codex_content_supply.md

# Reject commits, unexpected paths, and changes to existing publication records/assets
# before running any scripts the agent could have modified. NUL paths handle spaces.
python3 - "${BASE_HEAD}" <<'PY'
import csv
import io
from pathlib import Path
import subprocess
import sys

base = sys.argv[1]
def git(*args):
    return subprocess.check_output(['git', *args])
def refuse(message):
    raise SystemExit('content supply refused: ' + message)
if git('rev-parse', 'HEAD').decode().strip() != base:
    refuse('agent must not commit')
# The agent's index is not an output channel. Drop any hidden staged blobs in
# this disposable clone, then validate and stage the actual working tree only.
git('reset', '--mixed', base)
allowed = ('data/topics.csv', 'topics/topics.csv', 'generated/markdown',
           'generated/images', 'generated/assets/blog', 'generated/metadata', 'generated/reviews')
changed = set(filter(None, (git('diff', '--name-only', '-z', base) +
                           git('ls-files', '--others', '--exclude-standard', '-z')).decode().split('\0')))
protected_slugs = set()
for name in ('data/topics.csv', 'topics/topics.csv'):
    if not git('ls-tree', '--name-only', base, '--', name).strip():
        continue
    before = list(csv.DictReader(io.StringIO(git('show', f'{base}:{name}').decode())))
    current = Path(name)
    if not current.is_file() or current.is_symlink():
        refuse(f'topic table removed or linked: {name}')
    after = list(csv.DictReader(io.StringIO(current.read_text(encoding='utf-8'))))
    ids = [row['id'] for row in after]
    if len(ids) != len(set(ids)):
        refuse(f'duplicate topic IDs: {name}')
    by_id = {row['id']: row for row in after}
    old_ids = {row['id']: row for row in before}
    for row in before:
        if row['status'] in ('published', 'scheduled', 'archived'):
            if by_id.get(row['id']) != row:
                refuse(f'protected topic changed: {row["id"]}')
            protected_slugs.add(row['slug'])
    for row in after:
        if row['status'] in ('published', 'scheduled') and old_ids.get(row['id']) != row:
            refuse(f'publication transition forbidden: {row["id"]}')
for name in changed:
    if not any(name == prefix or name.startswith(prefix + '/') for prefix in allowed):
        refuse(f'unexpected path: {name}')
    path = Path(name)
    if any(part.is_symlink() for part in (path, *path.parents)):
        refuse(f'symlink path: {name}')
    if name.startswith('generated/') and any(slug in path.parts or path.stem == slug for slug in protected_slugs):
        refuse(f'protected publication asset changed: {name}')
PY

python3 scripts/validate_topics.py
python3 scripts/validate_foundation.py
python3 scripts/check_content_supply.py --require-healthy --minimum-ideas 8
python3 -m unittest tests.test_publication_automation tests.test_publishing

ALLOWED_PATHS=(data/topics.csv topics/topics.csv generated/markdown generated/images generated/assets/blog generated/metadata generated/reviews)
if git diff --quiet "${BASE_HEAD}" -- "${ALLOWED_PATHS[@]}" && [[ -z "$(git ls-files --others --exclude-standard -- "${ALLOWED_PATHS[@]}")" ]]; then
  echo "content supply already healthy; no content commit required"
  exit 0
fi
git add -- "${ALLOWED_PATHS[@]}"
git diff --cached --check
git commit -m "Replenish bilingual content supply"
# A concurrent update must cause a non-fast-forward failure, never a blind rebase
# after validating against a different version of the repository.
git push origin HEAD:main
echo "content supply committed and pushed successfully"
