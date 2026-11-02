#!/usr/bin/env bash
# Runs the Marasa AI backend and frontend together. Ctrl+C stops both.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

backend_port="${BACKEND_PORT:-8000}"
frontend_port="${FRONTEND_PORT:-5173}"

# Pick a free port if the preferred one is taken (a stale server should never
# break `dev`).
free_port() {
    python3 - "$1" <<'PY'
import socket
import sys

start = int(sys.argv[1])
for port in range(start, start + 20):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        break
else:
    sys.exit(f"no free port near {start}")
PY
}

backend_port="$(free_port "$backend_port")"
frontend_port="$(free_port "$frontend_port")"
export MARASA_BACKEND_PORT="$backend_port"
export MARASA_FRONTEND_PORT="$frontend_port"

cleanup() {
    [ -n "${backend_pid:-}" ] && kill "$backend_pid" 2>/dev/null || true
    [ -n "${frontend_pid:-}" ] && kill "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend on http://127.0.0.1:$backend_port"
(cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port "$backend_port" --reload) &
backend_pid=$!

echo "==> Starting frontend on http://127.0.0.1:$frontend_port"
(cd frontend && npm run dev -- --port "$frontend_port") &
frontend_pid=$!

for _ in $(seq 1 40); do
    sleep 0.5
    if curl -fsS "http://127.0.0.1:$backend_port/api/health" >/dev/null 2>&1; then
        echo
        echo "Marasa is running."
        echo "  App:     http://127.0.0.1:$frontend_port"
        echo "  Backend: http://127.0.0.1:$backend_port/api/health"
        break
    fi
done

echo "Press Ctrl+C to stop."
wait
