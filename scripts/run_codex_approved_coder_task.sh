#!/usr/bin/env bash
# Create one Draft PR from one explicitly approved AI-Coder task.
set -euo pipefail

engine_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_id="${1:-}"
execute="${2:-}"
if [[ -z "$task_id" || "$execute" != "--execute" ]]; then
  echo "Usage: $0 TASK_ID --execute" >&2
  echo "This command can create a branch, commit, push, and Draft PR; it never merges or deploys." >&2
  exit 2
fi

packet="$(mktemp "${TMPDIR:-/tmp}/codex-coder-task.XXXXXX.json")"
workspace="$(mktemp -d "${TMPDIR:-/tmp}/onnel-ai-coder.XXXXXX")"
pr_body="$(mktemp "${TMPDIR:-/tmp}/codex-coder-pr.XXXXXX.md")"
security_root=""
cleanup() {
  rm -f "$packet" "$pr_body"
  rm -rf "$workspace"
  [[ -z "$security_root" ]] || rm -rf "$security_root"
}
trap cleanup EXIT

python3 - "$engine_root" "$task_id" "$packet" <<'PY'
import json, pathlib, sys
root, task_id, output = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
sys.path.insert(0, str(root / "scripts"))
from ai_coder_task_contract import contract_errors
tasks=json.loads((root/'data/ai_coder_tasks.json').read_text(encoding='utf-8')).get('tasks',[])
task=next((item for item in tasks if item.get('task_id') == task_id), None)
if not task or task.get('status') != 'approved_for_draft_pr': raise SystemExit('task must be approved_for_draft_pr')
errors=contract_errors(task)
if errors: raise SystemExit('task intake contract is incomplete: '+'; '.join(errors))
if task.get('risk_class') == 'RED': raise SystemExit('RED tasks cannot run automatic patches')
if task.get('risk_class') == 'YELLOW' and not task.get('plan_approved_at'): raise SystemExit('YELLOW task plan is not approved')
json.dump({'task':task}, output.open('w', encoding='utf-8'), ensure_ascii=False, indent=2)
PY

repository="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task"]["repository"])' "$packet")"
branch="ai/fix-${task_id//[^A-Za-z0-9._-]/-}"
app_path="$workspace/repository"
git clone --filter=blob:none --no-tags "https://github.com/${repository}.git" "$app_path"
git -C "$app_path" switch -c "$branch" origin/main
if git -C "$app_path" ls-remote --exit-code --heads origin "$branch" >/dev/null; then
  echo "Draft branch already exists: $branch" >&2
  exit 1
fi

codex exec -s workspace-write -C "$app_path" \
  "Read '$packet' and '$engine_root/prompts/codex_bugfix.md'. Before inspecting or changing code, read AGENTS.md, CODEX_BOOT.md, CODEX.md, and SKILLS/00_SKILL_INDEX.md when they exist; those app rules override this prompt. Implement only the approved task and only within ticket.allowed_paths. First reproduce the issue or add a failing test. Do not touch anything in ticket.prohibited_paths. Do not commit, push, merge, deploy, publish, or create a PR. Run every ticket.verification_commands entry and report the results."

changed="$({ git -C "$app_path" diff --name-only; git -C "$app_path" ls-files --others --exclude-standard; } | sort -u)"
[[ -n "$changed" ]] || { echo "Codex made no changes; no PR created" >&2; exit 1; }
if ! CHANGED="$changed" python3 - "$packet" <<'PY'
import json, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).resolve().parent))
packet=json.load(open(sys.argv[1], encoding='utf-8'))
task=packet['task']
allowed=task['ticket']['allowed_paths']
changed=[line.strip() for line in os.environ['CHANGED'].splitlines() if line.strip()]
outside=[path for path in changed if not any(path == item.rstrip('/') or path.startswith(item.rstrip('/') + '/') for item in allowed)]
if outside: raise SystemExit('change outside approved ticket paths: '+outside[0])
PY
then exit 1; fi
if printf '%s\n' "$changed" | rg -n '(^|/)(ios/Runner/Info\.plist|android/app/src/main/AndroidManifest\.xml|.*secret.*|.*credential.*|.*migration.*|.*database.*|.*billing.*|.*payment.*|.*auth.*|.*crypto.*)$' -i; then
  echo "protected-path change detected; stopping before commit" >&2
  exit 1
fi

if [[ -x "$app_path/tool/quality_gate.sh" ]]; then
  (cd "$app_path" && bash tool/quality_gate.sh)
else
  (cd "$app_path" && flutter analyze && flutter test)
fi

security_scan="not_enabled"
if [[ "${AI_CODER_SECURITY_SCAN_ENABLED:-true}" != "false" ]]; then
  security_root="$(mktemp -d "${TMPDIR:-/tmp}/onnel-codex-security.XXXXXX")"
  chmod 700 "$security_root"
  codex-security scan "$app_path" \
    --working-tree \
    --output-dir "$security_root/results" \
    --json \
    --fail-on-severity high >"$security_root/summary.json"
  security_scan="passed"
fi

git -C "$app_path" add -A
git -C "$app_path" commit -m "Fix ${task_id}"
commit="$(git -C "$app_path" rev-parse HEAD)"
git -C "$app_path" push -u origin "$branch"
python3 - "$packet" "$security_scan" >"$pr_body" <<'PY'
import json, sys
task=json.load(open(sys.argv[1], encoding='utf-8'))['task']
ticket=task['ticket']
print(f"# AI-Coder task: {task['task_id']}\n")
print("Human-approved Draft PR only. QA gate is required before merge.\n")
print(f"- Risk class: `{task['risk_class']}`")
print(f"- Observed symptom: {ticket['observed_symptom']}")
print(f"- Expected result: {ticket['expected_result']}")
print(f"- Performance baseline: {ticket['performance_baseline']}")
print(f"- Codex Security diff scan: `{sys.argv[2]}`\n")
print("## Completion criteria\n")
print(ticket['completion_criteria'])
print("\n## Verification commands\n")
for command in ticket['verification_commands']:
    print(f"- `{command}`")
PY
pr_url="$(cd "$app_path" && gh pr create --draft --base main --head "$branch" --title "Fix ${task_id}" --body-file "$pr_body")"
python3 "$engine_root/scripts/record_ai_coder_draft_pr.py" "$task_id" \
  --branch "$branch" \
  --pr-url "$pr_url" \
  --commit "$commit" \
  --security-scan "$security_scan"
echo "Draft PR created: $pr_url"
