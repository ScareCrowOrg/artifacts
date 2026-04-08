#!/bin/bash
# Backend service entrypoint
# 1. Registers an initial Redis L1 heartbeat (fire-and-forget).
# 2. Starts uvicorn with optional --reload flag based on UVICORN_RELOAD env var.
set -e

# Start heartbeat daemon before uvicorn starts so the Launcher's heartbeat
# check succeeds even during a cold start. Run as background process (&).
python3 /app/artifacts/canonical/services/backend/heartbeat.py &
HEARTBEAT_PID=$!

cd /app/backend

# Add /app to PYTHONPATH so imports like 'from artifacts.shared.jwt_utils' work
# without this, Python looks in /app/backend/artifacts (which doesn't exist)
export PYTHONPATH="/app:${PYTHONPATH}"

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
