#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/venv}"

echo "[codex setup] repo: $ROOT_DIR"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[codex setup] python3 is required" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[codex setup] npm is required" >&2
  exit 1
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend/requirements.txt

# Chromium is enough for the current Playwright-based booking flow.
python -m playwright install chromium

pushd frontend >/dev/null
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
popd >/dev/null

mkdir -p logs downloads docs/research

echo "[codex setup] done"
echo "[codex setup] next: scripts/codex/verify.sh"
