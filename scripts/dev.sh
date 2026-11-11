#!/usr/bin/env bash
# Start the Sticky API and the Next.js app together.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x services/api/.venv/bin/uvicorn ]]; then
  python3 -m venv services/api/.venv
  services/api/.venv/bin/pip install -r services/api/requirements-dev.txt
fi

if [[ ! -d node_modules ]]; then
  npm install
fi

export NEXT_TELEMETRY_DISABLED=1
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
export STICKY_CORS_ORIGINS="${STICKY_CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"

services/api/.venv/bin/uvicorn app.main:app --app-dir services/api --reload --port 8000 &
API_PID=$!
npm run dev --workspace @sticky/web &
WEB_PID=$!

trap 'kill $API_PID $WEB_PID 2>/dev/null || true' EXIT
wait
