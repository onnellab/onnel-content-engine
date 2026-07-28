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
trap 'rm -f "$packet"' EXIT
python3 - "$engine_root" "$task_id" "$packet" <<'PY'
import csv, json, pathlib, sys
root, task_id, output = map(pathlib.Path, (sys.argv[1], sys.argv[2], sys.argv[3]))
tasks=json.loads((root/'data/ai_coder_tasks.json').read_text(encoding='utf-8')).get('tasks',[])
task=next((item for item in tasks if item.get('task_id') == str(task_id)), None)
if not task or task.get('status') != 'approved_for_draft_pr': raise SystemExit('task must be approved_for_draft_pr')
rows=list(csv.DictReader((root/'data/local_repositories.csv').open(encoding='utf-8', newline='')))
local=next((row for row in rows if row['app_slug'] == task.get('app_slug')), None)
if not local: raise SystemExit('no local repository mapping for task app')
if local['repository_name'] != task.get('repository','').split('/')[-1]: raise SystemExit('task repository and local mapping differ')
path=pathlib.Path(local['path']).expanduser()
if not (path/'pubspec.yaml').is_file(): raise SystemExit(f'Flutter app checkout not found: {path}')
json.dump({'task':task,'app_path':str(path),'pubspec_path':local['pubspec_path']}, output.open('w'), ensure_ascii=False, indent=2)
PY

app_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_path"])' "$packet")"
branch="ai/fix-${task_id//[^A-Za-z0-9._-]/-}"
git -C "$app_path" diff --quiet && git -C "$app_path" diff --cached --quiet || { echo "app worktree must be clean" >&2; exit 1; }
git -C "$app_path" fetch origin
if git -C "$app_path" show-ref --verify --quiet "refs/heads/$branch" || git -C "$app_path" ls-remote --exit-code --heads origin "$branch" >/dev/null; then
  echo "Draft branch already exists: $branch" >&2; exit 1
fi
git -C "$app_path" switch -c "$branch"

codex exec -s workspace-write -C "$app_path" "Read '$packet' and '$engine_root/prompts/codex_bugfix.md'. Implement only the approved task. First reproduce the issue or add a failing test. Do not touch billing, auth, privacy, cryptography, database migrations, signing, store metadata, or CI secrets. Do not commit, push, merge, deploy, publish, or create a PR. Run the relevant tests and report their results in your final response."

changed="$(git -C "$app_path" diff --name-only)"
[[ -n "$changed" ]] || { echo "Codex made no changes; no PR created" >&2; exit 1; }
if printf '%s\n' "$changed" | rg -n '(^|/)(ios/Runner/Info\.plist|android/app/src/main/AndroidManifest\.xml|.*secret.*|.*credential.*|.*migration.*|.*database.*|.*billing.*|.*payment.*|.*auth.*|.*crypto.*)$' -i; then
  echo "protected-path change detected; stopping before commit" >&2; exit 1
fi
if [[ -f "$app_path/pubspec.yaml" ]]; then
  (cd "$app_path" && flutter analyze && flutter test)
fi
git -C "$app_path" add -A
git -C "$app_path" commit -m "Fix ${task_id}"
commit="$(git -C "$app_path" rev-parse HEAD)"
git -C "$app_path" push -u origin "$branch"
pr_url="$(cd "$app_path" && gh pr create --draft --base main --head "$branch" --title "Fix ${task_id}" --body "AI-Coder task: ${task_id}\n\nHuman-approved Draft PR only. QA gate is required before merge.")"
python3 "$engine_root/scripts/record_ai_coder_draft_pr.py" "$task_id" --branch "$branch" --pr-url "$pr_url" --commit "$commit"
echo "Draft PR created: $pr_url"
