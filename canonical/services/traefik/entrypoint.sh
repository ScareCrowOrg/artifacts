#!/bin/bash
# ==============================================================================
# Traefik – entrypoint.sh
# ==============================================================================
# 1. Starts the Traefik binary with static configuration
# 2. Waits for the Traefik API ping endpoint to respond
# 3. Registers heartbeat in Redis L1 (BaseService pattern)
# 4. Handles SIGTERM/SIGINT for graceful shutdown
# ==============================================================================

set -e

echo "[entrypoint] Traefik starting..."

# ── Start Traefik with static config ─────────────────────────────────────────
echo "[entrypoint] Starting Traefik binary..."
/usr/local/bin/traefik --configfile=/app/traefik.yml &
TRAEFIK_PID=$!

# ── Wait for Traefik API to be ready ─────────────────────────────────────────
echo "[entrypoint] Waiting for Traefik API on port 8080..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:8080/ping > /dev/null 2>&1; then
        echo "[entrypoint] OK: Traefik API ready!"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[entrypoint] WARNING: Traefik API did not respond within 60s - continuing anyway"
    fi
    sleep 1
done

# ── Start heartbeat daemon ────────────────────────────────────────────────────
echo "[entrypoint] Starting heartbeat daemon..."
python3 /app/artifacts/canonical/services/traefik/heartbeat.py &
HEARTBEAT_PID=$!

# ── Signal forwarding ─────────────────────────────────────────────────────────
_shutdown() {
    echo "[entrypoint] Signal received - shutting down gracefully..."
    kill $HEARTBEAT_PID 2>/dev/null || true
    kill $TRAEFIK_PID 2>/dev/null || true
    exit 0
}

trap _shutdown SIGTERM SIGINT SIGHUP

# ── Keep container alive ──────────────────────────────────────────────────────
echo "[entrypoint] Traefik ready. Waiting for process..."
wait $TRAEFIK_PID
