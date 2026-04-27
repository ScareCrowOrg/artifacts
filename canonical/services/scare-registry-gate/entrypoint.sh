#!/bin/sh
#
# ScareRegistryGate service entrypoint.
# 1. Starts heartbeat.py (registers Redis key, runs continuously in background)
# 2. Runs /app/scare-registry-gate in foreground
#

set -e

echo "[entrypoint] Starting ScareRegistryGate..."

# Start heartbeat in background (fire-and-forget, keeps Redis key alive)
python3 /app/heartbeat.py &

# Give heartbeat time to register before the binary starts
sleep 1

# Start scare-registry-gate binary in foreground (inherits full environment)
echo "[entrypoint] Starting /app/scare-registry-gate..."
exec /app/scare-registry-gate
