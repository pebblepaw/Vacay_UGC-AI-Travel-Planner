#!/bin/bash
# Startup script for VACAY development

BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
VENV_DIR="${VENV_DIR:-venv}"
CONFIG_PATH="${APP_CONFIG_PATH:-config/config.yaml}"
LOG_DIR="${LOG_DIR:-logs}"
RUN_TAG="$(date +%Y%m%d_%H%M%S)"
WORKSPACE_PATH="$(pwd)"
WORKSPACE_LABEL="$(basename "$WORKSPACE_PATH")"
LOG_DIR_ABS="$WORKSPACE_PATH/$LOG_DIR"
BACKEND_LOG="$LOG_DIR_ABS/backend_${RUN_TAG}.log"
FRONTEND_LOG="$LOG_DIR_ABS/frontend_${RUN_TAG}.log"

echo "🏖️  Starting VACAY..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please create .env with your API keys:"
    echo "   GEMINI_API_KEY=..."
    echo "   # Optional alternative for agent chat:"
    echo "   DASHSCOPE_API_KEY=..."
    echo "   TAVLY_API=..."
    echo "   MAPBOX_PUBLIC=..."
    echo "   MAPBOX_SECRET=..."
    echo "   Then edit config/config.yaml for model roles and language."
    exit 1
fi

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Error: Python virtual environment not found!"
    echo "   Expected at: $VENV_DIR"
    echo "   Run: python3 -m venv venv"
    exit 1
fi

# Check if frontend dependencies are installed
if [ ! -d frontend/node_modules ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
    echo ""
fi

# Activate venv
source "$VENV_DIR/bin/activate"
mkdir -p "$LOG_DIR_ABS"
ln -sfn "$(basename "$BACKEND_LOG")" "$LOG_DIR_ABS/backend.log"
ln -sfn "$(basename "$FRONTEND_LOG")" "$LOG_DIR_ABS/frontend.log"

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
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(f"export {key}={shlex.quote(value)}")
PY
)"

export VACAY_WORKSPACE_PATH="$WORKSPACE_PATH"
export VACAY_WORKSPACE_LABEL="$WORKSPACE_LABEL"
export APP_CONFIG_PATH="$CONFIG_PATH"

# Start backend in background
# Start backend in background
echo "🔧 Starting backend server..."
# Don't cd into backend, run from root so module 'backend' is found
python -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
  > >(tee "$BACKEND_LOG") \
  2> >(tee -a "$BACKEND_LOG" >&2) &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend in background
echo "🎨 Starting frontend dev server..."
cd frontend
VITE_API_URL="http://127.0.0.1:${BACKEND_PORT}" \
VITE_MAPBOX_PUBLIC="${MAPBOX_PUBLIC:-}" \
VITE_WORKSPACE_LABEL="$WORKSPACE_LABEL" \
VITE_APP_CONFIG_PATH="$CONFIG_PATH" \
npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
  > >(tee "$FRONTEND_LOG") \
  2> >(tee -a "$FRONTEND_LOG" >&2) &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ VACAY is running!"
echo ""
echo "   Workspace: $WORKSPACE_PATH"
echo "   Config:    $CONFIG_PATH"
echo "   Backend:  http://localhost:${BACKEND_PORT}"
echo "   Frontend: http://localhost:${FRONTEND_PORT}"
echo "   API Docs: http://localhost:${BACKEND_PORT}/docs"
echo "   Backend log:  $BACKEND_LOG"
echo "   Frontend log: $FRONTEND_LOG"
if [ -n "${MAPBOX_PUBLIC:-}" ]; then
    echo "   Map frontend token: present"
else
    echo "   Map frontend token: missing"
fi
echo ""
echo "Press Ctrl+C to stop all servers..."

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Keep script running
wait
