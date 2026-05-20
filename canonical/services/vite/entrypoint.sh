#!/bin/sh
#
# Vite service entrypoint.
# 1. Starts heartbeat.py (fire-and-forget, registers in Redis and exits)
# 2. Runs npm run dev in foreground
#

set -e

echo "[entrypoint] Starting Vite service..."

# Start heartbeat in background (fire-and-forget)
# heartbeat.py will start asyncio task and exit immediately
python /app/heartbeat.py &

# Give heartbeat time to register
sleep 1

# Start watcher-bridge in background if enabled
# This polls filesystem for changes that Docker Desktop bind mounts miss
if [ "${VITE_HMR_BRIDGE_ENABLED:-true}" = "true" ]; then
  echo "[entrypoint] Starting watcher-bridge..."
  node /app/artifacts/canonical/services/vite/watcher-bridge.mjs &
fi

# Start npm run dev in foreground (inherits full environment)
echo "[entrypoint] Starting npm run dev..."
cd /app/artifacts
exec npm run dev
