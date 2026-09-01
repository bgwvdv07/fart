#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# start.sh
# Starts the RSS Monitor backend (FastAPI + scheduler)
# =============================================================================

# Project root (adjust if your structure differs)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Python environment (change to your venv path if needed)
PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

# Ports
API_PORT="${API_PORT:-8000}"

# =============================================================================
# Helper functions
# =============================================================================

cleanup() {
    echo "Shutting down services..."
    if [ -n "${SCHEDULER_PID:-}" ] && kill -0 "$SCHEDULER_PID" 2>/dev/null; then
        kill "$SCHEDULER_PID"
    fi
    if [ -n "${API_PID:-}" ] && kill -0 "$API_PID" 2>/dev/null; then
        kill "$API_PID"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# =============================================================================
# Start services
# =============================================================================

echo "Starting RSS Monitor..."
echo "  - API:  http://127.0.0.1:${API_PORT}"
echo "  - Scheduler: running in background"
echo ""

# Start scheduler in background
python scheduler.py &
SCHEDULER_PID=$!

# Start FastAPI (uvicorn)
# Adjust "app.main:app" to match your actual FastAPI entry point
uvicorn app.main:app \
    --host 127.0.0.1 \
    --port "$API_PORT" \
    --reload &
API_PID=$!

# Wait for both processes
wait