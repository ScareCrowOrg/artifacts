#!/bin/bash
# ==============================================================================
# Traefik – entrypoint.sh (Service Worker pattern, like Cloudflared)
# ==============================================================================
# 1. Starts the Traefik binary with static configuration
# 2. Starts Redis L1 heartbeat (fire-and-forget)
# 3. Handles SIGTERM/SIGINT for graceful shutdown
# ==============================================================================

set -e

echo "[entrypoint] Traefik starting..."

# ── Start Traefik with static config ──────────────────────────────────────────
echo "[entrypoint] Starting Traefik binary..."
traefik --configfile=/app/traefik.yml &
TRAEFIK_PID=$!

# ── Start heartbeat daemon (fire-and-forget) ──────────────────────────────────
echo "[entrypoint] Starting heartbeat daemon..."
python3 /app/heartbeat.py || true
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
