#!/bin/bash

# Manual Server Restart Commands
# Run these commands in your terminal

echo "=== Step 1: Kill any running uvicorn processes ==="
pkill -f "uvicorn main:app"
sleep 2

echo "=== Step 2: Navigate to backend directory ==="
cd /Users/manasakallakuri/Downloads/DataMIQ/backend

echo "=== Step 3: Start the server ==="
nohup .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 > server.log 2>&1 &

echo "=== Step 4: Wait for server to start ==="
sleep 5

echo "=== Step 5: Check server health ==="
curl http://localhost:8000/health

echo ""
echo "=== Server should be running now! ==="
echo "Check with: ps aux | grep uvicorn"
