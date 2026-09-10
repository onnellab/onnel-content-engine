#!/usr/bin/env bash
# Fail closed before an approved task can mutate an app checkout.
set -euo pipefail

engine_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -n "${AI_CODER_GITHUB_TOKEN:-}" ]] || {
  echo "AI_CODER_GITHUB_TOKEN is required for app push and Draft PR creation" >&2
  exit 1
}
for command in codex gh git rg flutter python3; do
  command -v "$command" >/dev/null || {
    echo "dedicated AI-Coder runner is missing: $command" >&2
    exit 1
  }
done
if [[ "${AI_CODER_SECURITY_SCAN_ENABLED:-true}" != "false" ]]; then
  for scanner in gitleaks semgrep osv-scanner; do
    command -v "$scanner" >/dev/null || {
      echo "Free security gate requires installed scanner: $scanner" >&2
      exit 1
    }
  done
  [[ -f "$engine_root/tool/free_security_gate.py" &&
     -f "$engine_root/tool/security_rules.yml" ]] || {
    echo "Free security gate bundle is incomplete" >&2
    exit 1
  }
fi
git -C "$engine_root" diff --quiet
git -C "$engine_root" diff --cached --quiet
codex login status >/dev/null
GH_TOKEN="$AI_CODER_GITHUB_TOKEN" gh auth status >/dev/null
GH_TOKEN="$AI_CODER_GITHUB_TOKEN" gh auth setup-git
echo "Dedicated AI-Coder runner preflight passed."
