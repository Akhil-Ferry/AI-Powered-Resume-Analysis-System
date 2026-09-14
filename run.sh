#!/usr/bin/env bash
# Requires an already-running PostgreSQL database with pgvector and backend/.env.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
(cd "$ROOT_DIR/backend" && uv run python manage.py upgrade)
(cd "$ROOT_DIR/backend" && exec uv run python server.py) &
BACKEND_PID=$!
(cd "$ROOT_DIR/frontend" && exec npm run dev -- --port 5174 --strictPort) &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT
echo "App: http://localhost:5174 | API: http://localhost:5000"
wait
