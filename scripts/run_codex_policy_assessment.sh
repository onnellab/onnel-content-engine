#!/usr/bin/env bash
# Run exactly one approved policy assessment without allowing app-code edits.
set -euo pipefail
engine_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_id="${1:-}"
[[ -n "$task_id" ]] || { echo "Usage: $0 TASK_ID" >&2; exit 2; }
packet_path="$(python3 "$engine_root/scripts/generate_policy_assessment_packet.py" "$task_id")"
app_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_path"])' "$packet_path")"
result="$(mktemp "${TMPDIR:-/tmp}/codex-policy-assessment.XXXXXX.json")"
trap 'rm -f "$result"' EXIT
codex exec -s read-only -C "$app_path" -o "$result" "Read '$packet_path' and '$engine_root/prompts/codex_policy_assessment.md'. First read AGENTS.md, CODEX_BOOT.md, CODEX.md, and SKILLS/00_SKILL_INDEX.md when they exist; app rules override this prompt. Do not edit any file. Return only JSON: {task_id, status, evidence:[{reference, detail}], conclusion, patch_authorized:false}. status must be PASS, FAIL, or STOP."
python3 -m json.tool "$result" >/dev/null
python3 "$engine_root/scripts/record_store_policy_assessment.py" "$task_id" "$result"
echo "Recorded read-only policy assessment for $task_id; no patch is authorized."
