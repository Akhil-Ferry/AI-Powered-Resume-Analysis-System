#!/usr/bin/env bash
# Starts backend (Flask, via uv) and frontend (React, via npm) together.
# First run: make sure you've run `uv sync` in backend/ and `npm install` in frontend/.
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting backend on http://localhost:5000 ..."
(cd "$ROOT_DIR/backend" && uv run python app.py) &
BACKEND_PID=$!

sleep 2

echo "Starting frontend on http://localhost:5173 ..."
(cd "$ROOT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

wait
