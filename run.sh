#!/usr/bin/env bash
# Verbatim — start the local API (and serve the built UI if present).
# Local-only: binds to 127.0.0.1 and talks to nothing but the Ollama runtime.
set -euo pipefail
cd "$(dirname "$0")"
HOST="${VERBATIM_HOST:-127.0.0.1}"
PORT="${VERBATIM_PORT:-8000}"
echo "Starting Verbatim API on http://${HOST}:${PORT}"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" "$@"
