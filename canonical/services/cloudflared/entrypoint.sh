#!/bin/sh
#
# Cloudflared service entrypoint.
#
# Docker requirement: PID 1 must stay alive for the container to keep running.
# Strategy: heartbeat.py becomes PID 1 (runs in foreground, indefinitely).
#          cloudflared tunnel runs in background (if TUNNEL_TOKEN set).
#
# If either process dies, container exits (graceful failure detection).
#

set -e

echo "[entrypoint] Starting cloudflared service..."

# ============================================================================
# Start tunnel in background if TUNNEL_TOKEN is provided
# ============================================================================
# This runs as a background job. If it dies, heartbeat will continue.
# If heartbeat dies, container will exit (expected behavior).

if [ -n "${TUNNEL_TOKEN}" ]; then
  echo "[entrypoint] ✅ TUNNEL_TOKEN set – starting cloudflared tunnel in background..."
  cloudflared tunnel --no-autoupdate run --token "${TUNNEL_TOKEN}" &
  TUNNEL_PID=$!
  echo "[entrypoint] Tunnel PID: $TUNNEL_PID"
else
  echo "[entrypoint] ⏸️  TUNNEL_TOKEN not set – running in heartbeat-only mode (bootstrap phase)"
fi

# ============================================================================
# Start heartbeat in FOREGROUND (as PID 1)
# ============================================================================
# exec replaces this shell process with heartbeat.py
# heartbeat.py becomes PID 1 and keeps the container alive indefinitely.
# When/if heartbeat.py exits, the container exits (graceful shutdown).

echo "[entrypoint] 🚀 Starting heartbeat in foreground (PID 1)..."
exec python /app/heartbeat.py
