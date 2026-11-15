#!/usr/bin/env bash
# Serves Marasa AI locally on this device (one port, one process).
#
# Builds the frontend and serves it together with the API from FastAPI on
# 127.0.0.1. The app is intentionally not exposed to the LAN or the internet.
# OpenCode Go credentials live only in memory for the signed-in browser session.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

port="${PORT:-8787}"

echo "==> Building the frontend"
(cd frontend && npm run build)

echo
echo "==> Serving on http://127.0.0.1:$port"
echo "    Device-local only; other network devices cannot connect."
echo "    OpenCode Go sign-in is required for each browser session."
echo

cd backend
exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$port"
