#!/bin/bash
# Startup script for VACAY development

echo "🏖️  Starting VACAY..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please create .env with your API keys:"
    echo "   GEMINI_API_KEY=..."
    echo "   DASHSCOPE_API_KEY=..."
    echo "   AGENT_LLM_PROVIDER=aliyun"
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
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend in background
echo "🎨 Starting frontend dev server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ VACAY is running!"
echo ""
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers..."

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Keep script running
wait
