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

# Start npm run dev in foreground (inherits full environment)
echo "[entrypoint] Starting npm run dev..."
cd /app/artifacts
exec npm run dev
