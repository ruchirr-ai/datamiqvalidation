#!/bin/bash

echo "========================================="
echo "  Starting DataMIQ Backend Server"
echo "========================================="
echo ""

# Kill any existing backend processes
echo "Stopping any existing backend processes..."
pkill -9 -f "uvicorn main:app" 2>/dev/null
sleep 2

# Navigate to backend directory
cd backend || exit 1

echo "Working directory: $(pwd)"
echo ""

# Verify we're in the correct directory
if [ ! -f "main.py" ]; then
    echo "ERROR: main.py not found!"
    exit 1
fi

# Verify virtual environment exists
if [ ! -f ".venv/bin/uvicorn" ]; then
    echo "ERROR: Virtual environment not found!"
    exit 1
fi

echo "✓ Virtual environment found"
echo "✓ Starting uvicorn on port 8000..."
echo ""
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/api/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================="
echo ""

# Start the server
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
