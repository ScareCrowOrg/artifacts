#!/bin/sh
#
# Auth-Proxy service entrypoint.
# 1. Starts heartbeat.py (fire-and-forget, registers in Redis and exits)
# 2. Runs /app/auth-proxy in foreground
#

set -e

echo "[entrypoint] Starting Auth-Proxy service..."

# Start heartbeat in background (fire-and-forget)
# heartbeat.py will start asyncio task and exit immediately
python3 /app/heartbeat.py &

# Give heartbeat time to register
sleep 1

# Start auth-proxy binary in foreground (inherits full environment)
echo "[entrypoint] Starting /app/auth-proxy..."
exec /app/auth-proxy
