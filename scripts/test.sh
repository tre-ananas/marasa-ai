#!/usr/bin/env bash
# Runs the backend (pytest) and frontend (vitest) test suites.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "==> Backend tests (pytest)"
(cd backend && uv run pytest -q)

echo
echo "==> Frontend tests (vitest)"
(cd frontend && npm test)

echo
echo "All tests passed."
