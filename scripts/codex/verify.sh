#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/venv}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

cd "$ROOT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[codex verify] missing virtualenv at $VENV_DIR" >&2
  echo "[codex verify] run scripts/codex/setup_cloud.sh first" >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

echo "[codex verify] backend tests"
pytest -q \
  backend/tests/test_video_processing.py \
  backend/tests/test_response_formatter.py \
  backend/tests/test_booking_agent.py \
  backend/tests/test_workspace_plumbing.py \
  backend/tests/test_workspace_runtime.py \
  backend/tests/test_itinerary_builder.py \
  backend/tests/test_itinerary_media_mapping.py \
  backend/tests/test_supabase_storage_config.py

echo "[codex verify] frontend tests"
pushd frontend >/dev/null
npm test
echo "[codex verify] frontend build"
npm run build
popd >/dev/null

echo "[codex verify] all checks passed"
