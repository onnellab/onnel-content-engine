#!/usr/bin/env bash
# Safe unattended local Codex cycle: review drafts and read-only diagnosis.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
git diff --quiet && git diff --cached --quiet || { echo "refusing scheduled run: worktree has local changes" >&2; exit 1; }
git pull --ff-only origin main
bash scripts/run_codex_review_drafts.sh
mapfile -t doctor_findings < <(python3 - <<'PY'
import json
from pathlib import Path
rows=json.loads(Path("data/ai_doctor_findings.json").read_text()).get("findings",[])
for row in rows:
    if row.get("severity") in {"high","critical"} and row.get("diagnosis_status") == "pending":
        print(row["finding_id"])
PY
)
for finding_id in "${doctor_findings[@]}"; do
  bash scripts/run_codex_doctor.sh "$finding_id" --execute
done
python3 scripts/generate_ai_coder_tasks.py
python3 scripts/generate_ai_manager_report.py
allowed='^(data/store_review_ai_drafts\.json|data/ai_doctor_findings\.json|data/ai_doctor_diagnoses/[^/]+\.json|data/ai_coder_tasks\.json|data/ai_manager_daily_report\.json|generated/review-replies/review_packet\.(json|md))$'
changed="$({ git diff --name-only; git ls-files --others --exclude-standard; } | sort -u)"
if [[ -n "$changed" ]] && ! printf '%s\n' "$changed" | rg -v "$allowed" >/dev/null; then
  git add data/store_review_ai_drafts.json data/ai_doctor_findings.json data/ai_coder_tasks.json data/ai_manager_daily_report.json generated/review-replies/review_packet.json generated/review-replies/review_packet.md
  [[ ! -d data/ai_doctor_diagnoses ]] || git add data/ai_doctor_diagnoses/
  git diff --cached --quiet || git commit -m "Generate local Codex review drafts"
  git push origin HEAD:main
else
  [[ -z "$changed" ]] || { echo "unexpected scheduled-run change; refusing commit" >&2; exit 1; }
fi
echo "Local AI Scout cycle completed; diagnoses and drafts remain non-authorizing."
