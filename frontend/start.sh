#!/bin/bash

# Frontend Development Server Startup Script

echo "🚀 Starting Prompt Analyzer Frontend..."
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "⚙️  Creating .env.local from example..."
    cp .env.local.example .env.local 2>/dev/null || echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
    echo ""
fi

echo "✨ Starting development server on http://localhost:3000"
echo "📡 Backend should be running on http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

npm run dev

