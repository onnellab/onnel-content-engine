#!/usr/bin/env bash
# Compatibility entrypoint: free local checks plus separately supplied review evidence.
set -euo pipefail

engine_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_id="${1:-}"
if [[ ! "$task_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
   { [[ $# -ne 1 ]] && [[ $# -ne 3 ]]; } ||
   { [[ $# -eq 3 ]] && [[ "$2" != "--review-report" || ! -f "$3" ]]; }; then
  echo "Usage: $0 TASK_ID [--review-report REVIEW.json]" >&2
  exit 2
fi
packet="$(mktemp "${TMPDIR:-/tmp}/codex-qa-packet.XXXXXX.json")"
report="$(mktemp "${TMPDIR:-/tmp}/codex-qa-report.XXXXXX.json")"
trap 'rm -f "$packet" "$report" "${packet}.analyze" "${packet}.test" "${packet}.performance"' EXIT

python3 - "$engine_root" "$task_id" "$packet" <<'PY'
import csv, json, pathlib, subprocess, sys
root, task_id, output = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
task=next((item for item in json.loads((root/'data/ai_coder_tasks.json').read_text(encoding='utf-8')).get('tasks', []) if item.get('task_id') == task_id), None)
if not task or task.get('status') != 'draft_pr_created': raise SystemExit('task must have a recorded Draft PR')
local=next((row for row in csv.DictReader((root/'data/local_repositories.csv').open(encoding='utf-8', newline='')) if row['app_slug'] == task.get('app_slug')), None)
if not local or not (pathlib.Path(local['path']).expanduser()/local['pubspec_path']).is_file(): raise SystemExit('mapped local Flutter checkout is unavailable')
apps={row['slug']:row for row in csv.DictReader((root/'data/apps_registry.csv').open(encoding='utf-8',newline=''))}
app=apps.get(task.get('app_slug'),{})
app_path=pathlib.Path(local['path']).expanduser()
head=subprocess.check_output(['git','-C',str(app_path),'rev-parse','HEAD'],text=True).strip()
if not task.get('commit') or task['commit'] != head:
    raise SystemExit('mapped app HEAD must match the recorded Draft PR commit')
if subprocess.check_output(['git','-C',str(app_path),'status','--porcelain'],text=True).strip():
    raise SystemExit('mapped app checkout must be clean for commit-bound QA evidence')
pubspec=(app_path/local['pubspec_path']).read_text(encoding='utf-8')
explicit_profile=str(task.get('qa_profile','')).strip()
profile='default'
profile_reason='No Firestore autosave QA profile evidence.'
if explicit_profile:
    if explicit_profile not in {'default','flutter_riverpod_firestore_autosave_v1'}:
        raise SystemExit(f'unsupported QA profile: {explicit_profile}')
    profile=explicit_profile
    profile_reason='Selected by the audited AI-Coder task contract.'
else:
    uses_riverpod=any(name in pubspec for name in ('flutter_riverpod:', 'riverpod:'))
    uses_firestore='cloud_firestore:' in pubspec
    autosave_evidence=False
    if uses_riverpod and uses_firestore:
        markers=('flushSave', 'flush_save', 'autosave', 'autoSave', 'debounce')
        for source in (app_path/'lib').rglob('*.dart'):
            try: text=source.read_text(encoding='utf-8')
            except OSError: continue
            if any(marker in text for marker in markers):
                autosave_evidence=True
                break
    if uses_riverpod and uses_firestore and autosave_evidence:
        profile='flutter_riverpod_firestore_autosave_v1'
        profile_reason='Riverpod, cloud_firestore, and committed autosave/flush/debounce code detected.'
device_path=root/'data/ios-device-qa-reports'/f'{task_id}.json'
try: device_report=json.loads(device_path.read_text(encoding='utf-8'))
except (OSError,json.JSONDecodeError): device_report=None
json.dump({'task':task, 'app_path':str(app_path), 'report_path':str(root/'data/qa-reports'/f'{task_id}.json'), 'qa_profile':profile, 'qa_profile_reason':profile_reason, 'ios_device_required':'ios' in app.get('platforms','').split('|'), 'ios_device_report':device_report}, output.open('w'), ensure_ascii=False, indent=2)
PY

app_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_path"])' "$packet")"
set +e
(cd "$app_path" && flutter analyze) >"${packet}.analyze" 2>&1; analyze=$?
(cd "$app_path" && flutter test) >"${packet}.test" 2>&1; tests=$?
performance_missing=0
if [[ -f "$app_path/tool/performance_gate.sh" ]]; then
  (cd "$app_path" && bash tool/performance_gate.sh) >"${packet}.performance" 2>&1; performance=$?
else
  echo "tool/performance_gate.sh is not configured" >"${packet}.performance"
  performance=2
  performance_missing=1
fi
set -e
python3 - "$packet" "$analyze" "$tests" "$performance" "$performance_missing" <<'PY'
import json, pathlib, subprocess, sys
path=pathlib.Path(sys.argv[1]); data=json.loads(path.read_text(encoding='utf-8'))
performance='not_configured' if sys.argv[5]=='1' else 'passed' if sys.argv[4]=='0' else 'failed'
data['command_results']={'flutter_analyze':'passed' if sys.argv[2]=='0' else 'failed','flutter_test':'passed' if sys.argv[3]=='0' else 'failed','performance':performance}
data['command_exit_codes']={'flutter_analyze':int(sys.argv[2]),'flutter_test':int(sys.argv[3]),'performance':int(sys.argv[4])}
app_path=data['app_path']
head=subprocess.check_output(['git','-C',app_path,'rev-parse','HEAD'],text=True).strip()
dirty=subprocess.check_output(['git','-C',app_path,'status','--porcelain'],text=True).strip()
data['source_integrity']='passed' if head == data['task']['commit'] and not dirty else 'unverified'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
PY

# macOS ships Bash 3.2: an empty array expansion is unbound under `set -u`.
if [[ $# -eq 3 ]]; then
  python3 "$engine_root/scripts/assemble_local_qa_report.py" "$packet" \
    --output "$report" --review-report "$3"
else
  python3 "$engine_root/scripts/assemble_local_qa_report.py" "$packet" --output "$report"
fi
mkdir -p "$engine_root/data/qa-reports"
cp "$report" "$engine_root/data/qa-reports/${task_id}.json"
python3 "$engine_root/scripts/validate_ai_qa_report.py" "$engine_root/data/qa-reports/${task_id}.json"
echo "Validated QA report: data/qa-reports/${task_id}.json"
