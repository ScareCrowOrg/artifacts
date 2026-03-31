#!/bin/bash
# ==============================================================================
# Nginx Unity – entrypoint.sh
# ==============================================================================
# Waits for Nginx Unit API to become ready (port 8080), then runs the FastAPI
# heartbeat sidecar in the foreground (keeping the container alive).
#
# Routes are registered dynamically via the Nginx Unit HTTP API by the Node.js
# orchestrator sidecar after upstream services become available.
#
# SIGTERM propagation: Docker sends SIGTERM to PID 1 (this script). The trap
# below forwards the signal to the Python sidecar so it shuts down gracefully.
# ==============================================================================

set -e

# ── Defaults ──────────────────────────────────────────────────────────────────
export WORKER_ID="${WORKER_ID:-nginx-unity}"
export SIDECAR_HOST="${SIDECAR_HOST:-0.0.0.0}"
export SIDECAR_PORT="${SIDECAR_PORT:-9000}"

echo "[entrypoint] Nginx Unit starting (WORKER_ID=${WORKER_ID})..."

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

# ── Signal forwarding ─────────────────────────────────────────────────────────
_shutdown() {
    echo "[entrypoint] SIGTERM received – shutting down gracefully..."
    if [ -n "${SIDECAR_PID}" ]; then
        kill -TERM "${SIDECAR_PID}" 2>/dev/null || true
    fi
    wait
    echo "[entrypoint] Shutdown complete."
}

trap _shutdown SIGTERM SIGINT

# ── Start FastAPI heartbeat sidecar in background ─────────────────────────────
echo "[entrypoint] Starting FastAPI heartbeat sidecar..."
python3 /app/main.py &
SIDECAR_PID=$!
echo "[entrypoint] FastAPI sidecar started (PID ${SIDECAR_PID})."

# Wait for the sidecar to exit (keeps the container alive)
wait "${SIDECAR_PID}"
