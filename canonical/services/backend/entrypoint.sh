#!/bin/bash
# Backend service entrypoint
# Starts uvicorn with optional --reload flag based on UVICORN_RELOAD env var.
set -e

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
