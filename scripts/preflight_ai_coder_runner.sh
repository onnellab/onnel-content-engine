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
  command -v node >/dev/null || {
    echo "Codex Security gate requires Node.js 22 or later" >&2
    exit 1
  }
  node_major="$(node -p 'Number(process.versions.node.split(".")[0])')"
  [[ "$node_major" -ge 22 ]] || {
    echo "Codex Security gate requires Node.js 22 or later" >&2
    exit 1
  }
  command -v codex-security >/dev/null || {
    echo "AI_CODER_SECURITY_SCAN_ENABLED requires an installed codex-security CLI" >&2
    exit 1
  }
  codex-security login status >/dev/null
fi
git -C "$engine_root" diff --quiet
git -C "$engine_root" diff --cached --quiet
codex login status >/dev/null
GH_TOKEN="$AI_CODER_GITHUB_TOKEN" gh auth status >/dev/null
GH_TOKEN="$AI_CODER_GITHUB_TOKEN" gh auth setup-git
echo "Dedicated AI-Coder runner preflight passed."
