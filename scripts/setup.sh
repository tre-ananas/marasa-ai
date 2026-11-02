#!/usr/bin/env bash
# One-command setup for Marasa AI on macOS/Linux.
#
#   ./scripts/setup.sh              # use Playwright Chromium for PDF rendering
#   ./scripts/setup.sh --edge       # skip the browser download (not supported on Linux)
#
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

step() { printf '\n==> %s\n' "$1"; }
note() { printf '    %s\n' "$1"; }

step "Checking Python 3.12+"
if ! command -v python3 >/dev/null 2>&1; then
    echo "!! Python 3.12+ is required but was not found." >&2
    exit 1
fi
python3 - <<'PY'
import sys
if sys.version_info < (3, 12):
    sys.exit("!! Python 3.12+ is required (found %d.%d)." % sys.version_info[:2])
print("    python %d.%d" % sys.version_info[:2])
PY

step "Checking uv (Python package manager)"
if ! command -v uv >/dev/null 2>&1; then
    note "installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
note "$(uv --version)"

step "Installing backend dependencies (uv sync)"
(cd backend && uv sync)
note "installing Playwright Chromium for PDF rendering..."
(cd backend && uv run playwright install chromium)

step "Checking Node.js 20+"
if ! command -v node >/dev/null 2>&1; then
    echo "!! Node.js 20+ is required to build the frontend. Install it from nodejs.org and re-run." >&2
    exit 1
fi
node_major="$(node --version | sed 's/^v//' | cut -d. -f1)"
if [ "$node_major" -lt 20 ]; then
    echo "!! Node.js 20+ is required (found $(node --version))." >&2
    exit 1
fi
note "node $(node --version)"

step "Installing frontend dependencies (npm ci)"
(cd frontend && npm ci)

step "Preparing configuration"
if [ ! -f .env ]; then
    cp .env.example .env
    note "created .env from .env.example"
else
    note ".env already exists (left untouched)"
fi

step "Verifying the installation"
(cd backend && uv run python -c "from app.main import app; print('backend OK:', app.title)")
(cd backend && uv run pytest -q)

printf '\nSetup complete.\n'
printf '  Start everything:  ./scripts/dev.sh\n'
printf '  Run the tests:     ./scripts/test.sh\n'
printf '  Then open:         http://localhost:5173\n\n'
