#!/usr/bin/env bash
# Produce one read-only diagnosis from one pending Doctor finding.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
finding_id="${1:-}"
execute="${2:-}"
if [[ -z "$finding_id" || "$execute" != "--execute" ]]; then
  echo "Usage: $0 FINDING_ID --execute" >&2
  exit 2
fi
packet="$(mktemp "${TMPDIR:-/tmp}/codex-doctor.XXXXXX.json")"
report="$(mktemp "${TMPDIR:-/tmp}/codex-doctor-report.XXXXXX.json")"
trap 'rm -f "$packet" "$report"' EXIT
python3 "$root/scripts/prepare_ai_doctor_context.py" "$finding_id" --output "$packet"
app_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_path"])' "$packet")"
codex exec -s read-only -C "$app_path" -o "$report" \
  "Read '$packet' and '$root/prompts/codex_diagnose.md'. Read the listed app entry rules first. Inspect the candidate files and relevant recent commits without editing anything. Return only the required JSON object."
python3 -m json.tool "$report" >/dev/null
python3 "$root/scripts/record_ai_doctor_diagnosis.py" "$finding_id" --report "$report"
