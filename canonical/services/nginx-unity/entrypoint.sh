#!/bin/bash
# ==============================================================================
# Nginx Unity – entrypoint.sh
# ==============================================================================
# 1. Waits for Nginx Unit API to become ready (port 8080)
# 2. Registers initial heartbeat in Redis L1
# 3. Keeps the container alive
#
# Routes are registered dynamically via the Nginx Unit HTTP API by the Node.js
# orchestrator sidecar after upstream services become available.
# ==============================================================================

set -e

echo "[entrypoint] Nginx Unit starting..."

# ── Wait for Nginx Unit API to be ready ───────────────────────────────────────
echo "[entrypoint] Waiting for Nginx Unit API on port 8080..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8080/api/config > /dev/null 2>&1; then
        echo "[entrypoint] Nginx Unit API ready!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[entrypoint] WARNING: Nginx Unit API did not respond within 30s – continuing anyway"
    fi
    sleep 1
done

# ── Register initial heartbeat ────────────────────────────────────────────────
echo "[entrypoint] Registering initial heartbeat..."
python3 /app/artifacts/canonical/services/nginx-unity/heartbeat.py || true

# ── Signal forwarding ─────────────────────────────────────────────────────────
_shutdown() {
    echo "[entrypoint] SIGTERM received – shutting down gracefully..."
    exit 0
}

trap _shutdown SIGTERM SIGINT

# ── Keep container alive ──────────────────────────────────────────────────────
# Nginx Unit runs as the main process managed by unit:latest base image.
# We keep the container alive indefinitely.
echo "[entrypoint] Nginx Unit ready. Container running indefinitely."
while true; do sleep 3600; done
