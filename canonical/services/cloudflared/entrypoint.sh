#!/bin/sh
#
# Cloudflared service entrypoint.
# 1. Starts heartbeat.py (fire-and-forget, registers in Redis and exits)
# 2. Optionally runs cloudflared tunnel if TUNNEL_TOKEN is set
#

set -e

echo "[entrypoint] Starting cloudflared service..."

# ============================================================================
# Start heartbeat in background (fire-and-forget)
# ============================================================================
# heartbeat.py starts BaseService heartbeat task and exits immediately.
# The heartbeat task continues running in background.

python /app/heartbeat.py &

# Give heartbeat time to initialize
sleep 1

# ============================================================================
# Start tunnel if TUNNEL_TOKEN is provided
# ============================================================================

if [ -n "${TUNNEL_TOKEN}" ]; then
  echo "[entrypoint] ✅ TUNNEL_TOKEN set – starting cloudflared tunnel in background..."
  cloudflared tunnel --no-autoupdate run --token "${TUNNEL_TOKEN}" &
else
  echo "[entrypoint] TUNNEL_TOKEN not set – running in heartbeat-only mode (bootstrap phase)"
fi

echo "[entrypoint] Cloudflared ready (heartbeat running)"

# Keep container alive; wait for all background jobs
wait
