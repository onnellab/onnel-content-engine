#!/usr/bin/env bash
# Produce a fact-only QA report from a Draft PR without changing app code.
set -euo pipefail

engine_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_id="${1:-}"
if [[ -z "$task_id" ]]; then echo "Usage: $0 TASK_ID" >&2; exit 2; fi
packet="$(mktemp "${TMPDIR:-/tmp}/codex-qa-packet.XXXXXX.json")"
report="$(mktemp "${TMPDIR:-/tmp}/codex-qa-report.XXXXXX.json")"
trap 'rm -f "$packet" "$report"' EXIT

python3 - "$engine_root" "$task_id" "$packet" <<'PY'
import csv, json, pathlib, sys
root, task_id, output = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
task=next((item for item in json.loads((root/'data/ai_coder_tasks.json').read_text(encoding='utf-8')).get('tasks', []) if item.get('task_id') == task_id), None)
if not task or task.get('status') != 'draft_pr_created': raise SystemExit('task must have a recorded Draft PR')
local=next((row for row in csv.DictReader((root/'data/local_repositories.csv').open(encoding='utf-8', newline='')) if row['app_slug'] == task.get('app_slug')), None)
if not local or not (pathlib.Path(local['path']).expanduser()/local['pubspec_path']).is_file(): raise SystemExit('mapped local Flutter checkout is unavailable')
apps={row['slug']:row for row in csv.DictReader((root/'data/apps_registry.csv').open(encoding='utf-8',newline=''))}
app=apps.get(task.get('app_slug'),{})
app_path=pathlib.Path(local['path']).expanduser()
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
json.dump({'task':task, 'app_path':local['path'], 'report_path':str(root/'data/qa-reports'/f'{task_id}.json'), 'qa_profile':profile, 'qa_profile_reason':profile_reason, 'ios_device_required':'ios' in app.get('platforms','').split('|'), 'ios_device_report':device_report}, output.open('w'), ensure_ascii=False, indent=2)
PY

app_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_path"])' "$packet")"
set +e
(cd "$app_path" && flutter analyze) >"${packet}.analyze" 2>&1; analyze=$?
(cd "$app_path" && flutter test) >"${packet}.test" 2>&1; tests=$?
if [[ -f "$app_path/tool/performance_gate.sh" ]]; then
  (cd "$app_path" && bash tool/performance_gate.sh) >"${packet}.performance" 2>&1; performance=$?
else
  echo "tool/performance_gate.sh is not configured" >"${packet}.performance"
  performance=2
fi
set -e
python3 - "$packet" "$analyze" "$tests" "$performance" <<'PY'
import json, pathlib, sys
path=pathlib.Path(sys.argv[1]); data=json.loads(path.read_text(encoding='utf-8'))
performance='passed' if sys.argv[4]=='0' else 'not_configured' if sys.argv[4]=='2' else 'failed'
data['command_results']={'flutter_analyze':'passed' if sys.argv[2]=='0' else 'failed','flutter_test':'passed' if sys.argv[3]=='0' else 'failed','performance':performance}
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
PY

codex exec -s read-only -C "$app_path" -o "$report" "Read '$packet', '$engine_root/prompts/codex_qa.md', and the app repository. First read AGENTS.md, CODEX_BOOT.md, CODEX.md, and SKILLS/00_SKILL_INDEX.md when they exist; app rules override this prompt. Do not edit any file. Use command_results from the packet for tests/static_analysis. If ios_device_required is true, ios_device_risk must be STOP unless ios_device_report has status PASS; cite that report only as evidence, never infer a physical-device pass. Do not edit any file. Return only one JSON object matching docs/operations/QA_REPORT_EXAMPLE.json. Every required check must be PASS, FAIL, or STOP with file/rule evidence. Never infer device/platform facts; use STOP if evidence is unavailable."
python3 -m json.tool "$report" >/dev/null
python3 - "$packet" "$report" <<'PY'
import json, pathlib, sys
packet=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
report=json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
if report.get('qa_profile') != packet.get('qa_profile'):
    raise SystemExit('QA report qa_profile does not match the prepared packet')
PY
mkdir -p "$engine_root/data/qa-reports"
cp "$report" "$engine_root/data/qa-reports/${task_id}.json"
python3 "$engine_root/scripts/validate_ai_qa_report.py" "$engine_root/data/qa-reports/${task_id}.json"
echo "Validated QA report: data/qa-reports/${task_id}.json"
