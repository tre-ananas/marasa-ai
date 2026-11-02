#!/usr/bin/env bash
# Serves Marasa AI to your local network (one port, one process).
#
# Builds the frontend and serves it, together with the API, from FastAPI on
# 0.0.0.0:8000. Any device on the same Wi-Fi can open the app from a phone or
# tablet; the session is shared, so you can start on the computer and continue
# on the phone.
#
# Voice input needs a secure context (HTTPS) and will not work over plain HTTP
# on a LAN address — typing works, which is the point of using a phone.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

port="${PORT:-8000}"

lan_addresses() {
    if command -v ip >/dev/null 2>&1; then
        ip -4 addr show scope global 2>/dev/null |
            awk '/inet /{split($2, a, "/"); print a[1]}'
    fi
}

echo "==> Building the frontend"
(cd frontend && npm run build)

echo
echo "==> Serving on http://0.0.0.0:$port"
echo "    One session is shared by every device on the network."
for address in $(lan_addresses); do
    echo "    Open on your phone:  http://$address:$port"
done
echo "    Voice input needs HTTPS and will not work over plain HTTP; typing works."
echo

cd backend
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$port"
