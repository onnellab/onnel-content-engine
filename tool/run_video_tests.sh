#!/bin/sh
# Portable local test entrypoint. Never mutate system Python or shared venvs.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNTIME="$ROOT/.runtime"
VENV="$RUNTIME/video-test-venv"

if [ -L "$RUNTIME" ] || [ -L "$VENV" ]; then
  echo 'Video test runtime must not be a symlink' >&2
  exit 2
fi
mkdir -p "$RUNTIME"

PATTERN=${1:-test_short_video*.py}
if [ "$(uname -s)" = "Darwin" ] && {
  [ "$PATTERN" = 'test_*.py' ] || [ "$PATTERN" = 'test_screenshot_guide*.py' ];
}; then
  if [ ! -f "$HOME/Library/Fonts/DejaVuSans.ttf" ] &&
     [ ! -f "/Library/Fonts/DejaVuSans.ttf" ]; then
    echo 'Approved DejaVu font missing: brew install --cask font-dejavu' >&2
    exit 2
  fi
fi

if [ ! -x "$VENV/bin/python" ]; then
  PYTHON=${ONNELLAB_VIDEO_TEST_PYTHON:-}
  if [ -z "$PYTHON" ]; then
    for candidate in python3.13 python3.14 python3.12 python3.11 python3.10 python3; do
      if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON=$candidate
        break
      fi
    done
  fi
  : "${PYTHON:?No Python installation found}"
  "$PYTHON" -m venv "$VENV"
fi

# Reconcile only this isolated venv against the exact pinned test requirements.
# Prefer wheels and avoid host compiler/toolchain upgrades.
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-input --only-binary=:all: \
  -r "$ROOT/requirements-test.txt"
exec "$VENV/bin/python" -B "$ROOT/scripts/run_unit_tests.py" --pattern "${1:-test_short_video*.py}"
