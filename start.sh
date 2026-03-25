#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

# Build frontend if not already built
if [ ! -d "frontend/.output" ]; then
    echo "Building frontend (first run)..."
    cd frontend && npm install --silent 2>/dev/null && API_BASE="http://localhost:8188" npx nuxt generate 2>/dev/null
    cd ..
    echo "Frontend built."
fi

# Start backend (serves API + built frontend)
python -m vargen --host 0.0.0.0 --port 8188 "$@"
