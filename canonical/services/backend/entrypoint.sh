#!/bin/bash
# Backend service entrypoint
# 1. Registers an initial Redis L1 heartbeat (fire-and-forget).
# 2. Starts uvicorn with optional --reload flag based on UVICORN_RELOAD env var.
set -e

# Register initial heartbeat before uvicorn starts so the Launcher's heartbeat
# check succeeds even during a cold start.  Errors are non-fatal (|| true).
python3 /app/artifacts/canonical/services/backend/heartbeat.py || true

cd /app/backend

if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
    exec python -u -m uvicorn app.main:app \
        --host "${API_HOST:-0.0.0.0}" \
        --port "${API_PORT:-5050}" \
        --reload
else
    exec python -u -m uvicorn app.main:app \
        --host "${API_HOST:-0.0.0.0}" \
        --port "${API_PORT:-5050}"
fi
