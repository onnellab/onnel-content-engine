#!/usr/bin/env bash
# Run integration tests on one explicitly selected physical iOS device.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_id="${1:-}"
device_id="${2:-}"
confirm="${3:-}"
if [[ -z "$task_id" || -z "$device_id" || "$confirm" != "--execute" ]]; then
  echo "Usage: $0 TASK_ID IOS_DEVICE_ID --execute" >&2
  exit 2
fi
[[ "$(uname -s)" == "Darwin" ]] || { echo "iOS physical-device QA requires macOS" >&2; exit 1; }
[[ -z "$(git -C "$root" status --porcelain)" ]] || { echo "refusing iOS QA: content-engine worktree has local changes" >&2; exit 1; }
git -C "$root" pull --ff-only origin main
publish_report() {
  git -C "$root" add "data/ios-device-qa-reports/${task_id}.json"
  git -C "$root" commit -m "Record iOS device QA result for ${task_id}"
  git -C "$root" push origin HEAD:main
}
packet="$(mktemp "${TMPDIR:-/tmp}/ios-device-qa.XXXXXX.json")"
devices="$(mktemp "${TMPDIR:-/tmp}/flutter-devices.XXXXXX.json")"
trap 'rm -f "$packet" "$devices"' EXIT
python3 - "$root" "$task_id" "$packet" <<'PY'
import csv,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); task_id=sys.argv[2]; output=pathlib.Path(sys.argv[3])
task=next((x for x in json.loads((root/'data/ai_coder_tasks.json').read_text(encoding='utf-8')).get('tasks',[]) if x.get('task_id')==task_id),None)
if not task or task.get('status')!='draft_pr_created': raise SystemExit('task must have a recorded Draft PR')
local=next((x for x in csv.DictReader((root/'data/local_repositories.csv').open(encoding='utf-8',newline='')) if x['app_slug']==task.get('app_slug')),None)
if not local or not (pathlib.Path(local['path']).expanduser()/local['pubspec_path']).is_file(): raise SystemExit('mapped local Flutter checkout is unavailable')
json.dump({'task':task,'app_path':local['path']},output.open('w'),indent=2)
PY
app_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_path"])' "$packet")"
(cd "$app_path" && flutter devices --machine) > "$devices"
python3 - "$devices" "$device_id" <<'PY'
import json,sys
items=json.load(open(sys.argv[1])); device=next((x for x in items if x.get('id')==sys.argv[2]),None)
if not device or device.get('targetPlatform')!='ios' or device.get('emulator') is not False: raise SystemExit('selected device must be a connected physical iOS device')
PY
mkdir -p "$root/data/ios-device-qa-reports"
report="$root/data/ios-device-qa-reports/${task_id}.json"
if [[ ! -d "$app_path/integration_test" ]] || ! find "$app_path/integration_test" -name '*_test.dart' -print -quit | grep -q .; then
  python3 - "$report" "$task_id" "$device_id" <<'PY'
import json,sys
json.dump({'task_id':sys.argv[2],'device_id':sys.argv[3],'status':'STOP','evidence':'No integration_test/*_test.dart exists; physical device verification cannot be claimed.'},open(sys.argv[1],'w'),indent=2); open(sys.argv[1],'a').write('\n')
PY
  echo "STOP: no integration test; report recorded at $report" >&2
  publish_report
  exit 1
fi
set +e
(cd "$app_path" && flutter test integration_test -d "$device_id")
result=$?
set -e
python3 - "$report" "$task_id" "$device_id" "$result" <<'PY'
import json,sys
status='PASS' if sys.argv[4]=='0' else 'FAIL'
json.dump({'task_id':sys.argv[2],'device_id':sys.argv[3],'status':status,'evidence':'flutter test integration_test executed on selected physical iOS device.'},open(sys.argv[1],'w'),indent=2); open(sys.argv[1],'a').write('\n')
PY
if [[ "$result" != "0" ]]; then
  publish_report
  exit "$result"
fi
publish_report
echo "PASS: physical iOS device QA report recorded at $report"
