#!/bin/bash

# Quirk Analysis - Quick Start Script

echo "🚀 Starting Quirk Analysis System..."
echo ""

# Check if in correct directory
if [ ! -f "api.py" ]; then
    echo "❌ Error: api.py not found. Run this script from the project root."
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js not found. Please install Node.js 18+"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt -q

# Install frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Start backend in background
echo "🔧 Starting FastAPI backend on port 8000..."
python3 api.py &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to initialize..."
sleep 3

# Start frontend
echo "🎨 Starting Next.js frontend on port 3000..."
cd frontend && npm run dev

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT
