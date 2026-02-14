#!/bin/bash

# Restart Backend Server Script
# This script kills the existing backend process and starts a fresh one

echo "🔄 Restarting Backend Server..."
echo ""

# Kill existing process on port 8000
echo "1️⃣ Stopping existing server..."
lsof -ti :8000 | xargs kill -9 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Stopped existing server"
else
    echo "   ℹ️  No existing server found"
fi
echo ""

# Activate virtual environment
echo "2️⃣ Activating virtual environment..."
source .venv/bin/activate
echo "   ✅ Virtual environment activated"
echo ""

# Start server
echo "3️⃣ Starting fresh server..."
echo "   📡 Server will be available at: http://localhost:8000"
echo "   📚 API docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start uvicorn with reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
