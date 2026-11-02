#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python scripts/verify_project.py
python -m compileall -q backend ai_memory tests scripts
pytest -q
python -c 'import backend.main; print(f"FastAPI route import OK: {len(backend.main.app.routes)} routes")'
if command -v npm >/dev/null 2>&1; then
  cd frontend
  npm install --no-audit --no-fund
  npm run lint
  npm run typecheck
  NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}" npm run build
else
  echo "WARNING: npm not installed; frontend build not run." >&2
fi
if command -v docker >/dev/null 2>&1; then
  cd "$ROOT"
  docker compose config -q
else
  echo "WARNING: Docker not installed; Docker Compose validation not run." >&2
fi
