#!/bin/sh
# ==============================================================================
# Traefik – entrypoint.sh (Service Worker pattern, like Cloudflared)
# ==============================================================================
# 1. Starts the Traefik binary with static configuration
# 2. Starts service-discovery daemon (Redis L1 → traefik-services.yml)
# 3. Starts Redis L1 heartbeat (fire-and-forget)
# 4. Handles SIGTERM/SIGINT for graceful shutdown
# ==============================================================================

set -e

echo "[entrypoint] Traefik starting..."

# ── Start Traefik with static config ──────────────────────────────────────────
echo "[entrypoint] Starting Traefik binary..."
traefik --configfile=/app/traefik.yml &
TRAEFIK_PID=$!

# ── Start service discovery daemon (background) ───────────────────────────────
echo "[entrypoint] Starting service discovery daemon..."
python3 /app/service_discovery.py &
DISCOVERY_PID=$!

# ── Start heartbeat daemon (background) ───────────────────────────────────────
echo "[entrypoint] Starting heartbeat daemon..."
python3 /app/heartbeat.py &
HEARTBEAT_PID=$!

# ── Signal forwarding ─────────────────────────────────────────────────────────
_shutdown() {
    echo "[entrypoint] Signal received - shutting down gracefully..."
    kill $DISCOVERY_PID 2>/dev/null || true
    kill $HEARTBEAT_PID 2>/dev/null || true
    kill $TRAEFIK_PID 2>/dev/null || true
    exit 0
}

trap _shutdown SIGTERM SIGINT SIGHUP

# ── Keep container alive ──────────────────────────────────────────────────────
echo "[entrypoint] Traefik ready. Waiting for process..."
wait $TRAEFIK_PID
