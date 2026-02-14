#!/bin/bash

# Frontend Startup Script
# Run this from the project root directory

echo "=========================================="
echo "Starting Frontend Development Server"
echo "=========================================="
echo ""

# Navigate to frontend directory
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "⚠️  node_modules not found. Installing dependencies..."
    npm install
fi

echo "✓ Starting Vite dev server on port 3000..."
echo ""
echo "Frontend will be available at: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the dev server
npm run dev
