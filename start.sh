#!/usr/bin/env bash
set -euo pipefail

# Local development runner for VacayClaw.
#
# Defaults:
#   backend:  http://127.0.0.1:8000
#   frontend: http://127.0.0.1:8080
#
# Optional Telegram webhook tunnel:
#   TELEGRAM_TUNNEL=1 ./start.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
HOST="${HOST:-127.0.0.1}"
VENV_DIR="${VENV_DIR:-venv}"
CONFIG_PATH="${APP_CONFIG_PATH:-config/config.yaml}"
LOG_DIR="${LOG_DIR:-logs}"
INSTALL_DEPS="${INSTALL_DEPS:-auto}"
TELEGRAM_TUNNEL="${TELEGRAM_TUNNEL:-0}"
RUN_TAG="$(date +%Y%m%d_%H%M%S)"
WORKSPACE_LABEL="$(basename "$ROOT_DIR")"
LOG_DIR_ABS="$ROOT_DIR/$LOG_DIR"
BACKEND_LOG="$LOG_DIR_ABS/backend_${RUN_TAG}.log"
FRONTEND_LOG="$LOG_DIR_ABS/frontend_${RUN_TAG}.log"
TUNNEL_LOG="$LOG_DIR_ABS/cloudflared_${RUN_TAG}.log"
WEBHOOK_LOG="$LOG_DIR_ABS/telegram_webhook_${RUN_TAG}.json"
EXPLICIT_PUBLIC_WEB_BASE_URL="${PUBLIC_WEB_BASE_URL:-}"
EXPLICIT_PUBLIC_API_BASE_URL="${PUBLIC_API_BASE_URL:-}"

PIDS=()

cleanup() {
  if [ "${#PIDS[@]}" -gt 0 ]; then
    kill "${PIDS[@]}" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "$label did not become healthy: $url" >&2
  return 1
}

backend_deps_present() {
  python - <<'PY' >/dev/null 2>&1
import fastapi
import uvicorn
PY
}

load_dotenv() {
  eval "$("$VENV_DIR/bin/python" - <<'PY'
from pathlib import Path
import shlex

for raw_line in Path(".env").read_text().splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        continue
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(f"export {key}={shlex.quote(value)}")
PY
)"
}

require_cmd python3
require_cmd npm
require_cmd curl

if [ ! -f .env ]; then
  cat >&2 <<'EOF'
Missing .env.

Create .env with the keys in docs/brd/env_vars.md.
At minimum, local demo runs need:
  GEMINI_API_KEY
  TAVLY_API
  MAPBOX_PUBLIC
  MAPBOX_SECRET
  SUPABASE_PROJECT_URL
  SUPABASE_SECRET_KEY

Telegram demo also needs:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_WEBHOOK_SECRET
EOF
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if [ "$INSTALL_DEPS" = "1" ] || { [ "$INSTALL_DEPS" = "auto" ] && ! backend_deps_present; }; then
  echo "Installing backend dependencies"
  python -m pip install --upgrade pip
  python -m pip install -r backend/requirements.txt
fi

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies"
  (
    cd frontend
    if [ -f package-lock.json ]; then
      npm ci
    else
      npm install
    fi
  )
fi

mkdir -p "$LOG_DIR_ABS"
ln -sfn "$(basename "$BACKEND_LOG")" "$LOG_DIR_ABS/backend.log"
ln -sfn "$(basename "$FRONTEND_LOG")" "$LOG_DIR_ABS/frontend.log"

load_dotenv

export VACAY_WORKSPACE_PATH="$ROOT_DIR"
export VACAY_WORKSPACE_LABEL="$WORKSPACE_LABEL"
export APP_CONFIG_PATH="$CONFIG_PATH"
export PUBLIC_WEB_BASE_URL="${EXPLICIT_PUBLIC_WEB_BASE_URL:-http://127.0.0.1:${FRONTEND_PORT}}"
export PUBLIC_API_BASE_URL="${EXPLICIT_PUBLIC_API_BASE_URL:-http://127.0.0.1:${BACKEND_PORT}}"

echo "Starting backend on http://${HOST}:${BACKEND_PORT}"
python -m uvicorn backend.main:app --host "$HOST" --port "$BACKEND_PORT" \
  > >(tee "$BACKEND_LOG") \
  2> >(tee -a "$BACKEND_LOG" >&2) &
PIDS+=("$!")

wait_for_http "http://127.0.0.1:${BACKEND_PORT}/api/health" "Backend"

TUNNEL_URL=""
if [ "$TELEGRAM_TUNNEL" = "1" ]; then
  require_cmd cloudflared

  echo "Starting Cloudflare tunnel for Telegram webhook"
  cloudflared tunnel --url "http://127.0.0.1:${BACKEND_PORT}" --no-autoupdate \
    > >(tee "$TUNNEL_LOG") \
    2> >(tee -a "$TUNNEL_LOG" >&2) &
  PIDS+=("$!")

  for _ in $(seq 1 45); do
    TUNNEL_URL="$(grep -Eo 'https://[-a-zA-Z0-9]+\.trycloudflare\.com' "$TUNNEL_LOG" | tail -n 1 || true)"
    if [ -n "$TUNNEL_URL" ]; then
      break
    fi
    sleep 1
  done

  if [ -z "$TUNNEL_URL" ]; then
    echo "Cloudflare tunnel did not report a public URL. Check $TUNNEL_LOG" >&2
  elif [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
    echo "Registering Telegram webhook at ${TUNNEL_URL}/api/telegram/webhook"
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
      -d "url=${TUNNEL_URL}/api/telegram/webhook" \
      -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
      > "$WEBHOOK_LOG"
  else
    echo "Tunnel is ready, but TELEGRAM_BOT_TOKEN or TELEGRAM_WEBHOOK_SECRET is missing."
  fi
fi

echo "Starting frontend on http://${HOST}:${FRONTEND_PORT}"
(
  cd frontend
  VITE_API_URL="http://127.0.0.1:${BACKEND_PORT}" \
  VITE_MAPBOX_PUBLIC="${MAPBOX_PUBLIC:-}" \
  VITE_WORKSPACE_LABEL="$WORKSPACE_LABEL" \
  VITE_APP_CONFIG_PATH="$CONFIG_PATH" \
  npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" \
    > >(tee "$FRONTEND_LOG") \
    2> >(tee -a "$FRONTEND_LOG" >&2)
) &
PIDS+=("$!")

echo
echo "VacayClaw is running."
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo "Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "API docs: http://127.0.0.1:${BACKEND_PORT}/docs"
echo "Config:   $CONFIG_PATH"
echo "Logs:     $LOG_DIR_ABS"
if [ -n "$TUNNEL_URL" ]; then
  echo "Telegram webhook tunnel: $TUNNEL_URL"
fi
echo
echo "Press Ctrl+C to stop all started processes."

wait "${PIDS[@]}"
