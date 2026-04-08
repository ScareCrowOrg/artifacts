#!/bin/bash
# ==============================================================================
# Nginx Unity – entrypoint.sh
# ==============================================================================
# Wrapper around the official nginx/unit entrypoint that:
# 1. Calls the original /usr/local/bin/docker-entrypoint.sh to load config & start unitd
# 2. Registers initial heartbeat in Redis L1
# 3. Keeps the container alive
#
# Routes are registered dynamically via the Nginx Unit HTTP API by the Node.js
# orchestrator sidecar after upstream services become available.
# ==============================================================================

set -e

echo "[entrypoint] Nginx Unity starting..."

# ── Call the original nginx/unit entrypoint with unitd as the command ──────────
# This will handle:
# - Loading config from /docker-entrypoint.d/unit.conf.json
# - Starting unitd with proper initialization
echo "[entrypoint] Invoking original nginx/unit entrypoint..."
/usr/local/bin/docker-entrypoint.sh unitd --no-daemon &
UNITD_PID=$!

# ── Expose Nginx Unit control socket as HTTP via socat ──────────────────────────
# socat bridges the Unix socket (/var/run/control.unit.sock) to TCP port 8080
# This allows HTTP clients to interact with the Nginx Unit API
echo "[entrypoint] Exposing Nginx Unit API via HTTP on port 8080 (socat)..."
sleep 2
socat TCP-LISTEN:8080,reuseaddr,fork UNIX-CONNECT:/var/run/control.unit.sock &
SOCAT_PID=$!
sleep 1

# ── Wait for Nginx Unit API to be ready ───────────────────────────────────────
echo "[entrypoint] Waiting for Nginx Unit API on port 8080..."
for i in $(seq 1 60); do
    if curl -s http://127.0.0.1:8080/api/config > /dev/null 2>&1; then
        echo "[entrypoint] OK: Nginx Unit API ready!"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[entrypoint] WARNING: Nginx Unit API did not respond within 60s - continuing anyway"
    fi
    sleep 1
done

# ── Start heartbeat daemon ────────────────────────────────────────────────────
echo "[entrypoint] Starting heartbeat daemon..."
python3 /app/artifacts/canonical/services/nginx-unity/heartbeat.py &
HEARTBEAT_PID=$!

# ── Signal forwarding ─────────────────────────────────────────────────────────
_shutdown() {
    echo "[entrypoint] SIGTERM received - shutting down gracefully..."
    kill $HEARTBEAT_PID 2>/dev/null || true
    kill $SOCAT_PID 2>/dev/null || true
    kill $UNITD_PID 2>/dev/null || true
    exit 0
}

trap _shutdown SIGTERM SIGINT

# ── Keep container alive ──────────────────────────────────────────────────────
echo "[entrypoint] Nginx Unit ready. Waiting for unitd..."
wait $UNITD_PID
