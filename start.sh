#!/bin/bash
# Startup script for VACAY development

BACKEND_PORT=8010
FRONTEND_PORT=3000

echo "🏖️  Starting VACAY..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please create .env with your API keys:"
    echo "   GEMINI_API_KEY=..."
    echo "   # Optional alternative for agent chat:"
    echo "   DASHSCOPE_API_KEY=..."
    echo "   # Optional provider override: auto | gemini | aliyun"
    echo "   AGENT_LLM_PROVIDER=auto"
    echo "   TAVLY_API=..."
    echo "   MAPBOX_PUBLIC=..."
    echo "   MAPBOX_SECRET=..."
    exit 1
fi

# Check if venv exists
if [ ! -d venv ]; then
    echo "❌ Error: Python virtual environment not found!"
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
source venv/bin/activate

# Start backend in background
# Start backend in background
echo "🔧 Starting backend server..."
# Don't cd into backend, run from root so module 'backend' is found
python -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend in background
echo "🎨 Starting frontend dev server..."
cd frontend
VITE_API_URL="http://127.0.0.1:${BACKEND_PORT}" npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ VACAY is running!"
echo ""
echo "   Backend:  http://localhost:${BACKEND_PORT}"
echo "   Frontend: http://localhost:${FRONTEND_PORT}"
echo "   API Docs: http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "Press Ctrl+C to stop all servers..."

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Keep script running
wait
