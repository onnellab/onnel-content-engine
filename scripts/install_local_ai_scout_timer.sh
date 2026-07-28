#!/usr/bin/env bash
# Installs the draft-only systemd user timer. Run manually on the Codex machine.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
systemctl --user --version >/dev/null
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 "$root/systemd/onnel-ai-scout.service" "$HOME/.config/systemd/user/onnel-ai-scout.service"
install -m 0644 "$root/systemd/onnel-ai-scout.timer" "$HOME/.config/systemd/user/onnel-ai-scout.timer"
systemctl --user daemon-reload
systemctl --user enable --now onnel-ai-scout.timer
systemctl --user list-timers onnel-ai-scout.timer
