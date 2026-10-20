#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
backend_pid=$!
cleanup() { kill "$backend_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
npm run dev --prefix frontend
