#!/usr/bin/env bash
# Local staging: API on :8000, Vite staging UI on :5173/staging.html
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install)
fi

API_PID=""
cleanup() {
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

PYTHONPATH=backend uvicorn app.main:app --reload --app-dir backend --port 8000 &
API_PID=$!

echo "API:  http://localhost:8000/api/v1/health"
echo "UI:   http://localhost:5173/staging.html"
echo "Press Ctrl+C to stop."

cd frontend && npm run dev:staging
