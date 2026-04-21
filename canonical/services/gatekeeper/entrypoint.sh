#!/bin/bash
# GateKeeper service entrypoint
# 1. Registers an initial Redis L1 heartbeat (fire-and-forget).
# 2. Starts main.py with Python.
set -e

# Start heartbeat daemon before main.py starts so the Launcher's heartbeat
# check succeeds even during a cold start. Run as background process (&).
python3 /app/artifacts/canonical/services/gatekeeper/heartbeat.py &
HEARTBEAT_PID=$!

# Add /app to PYTHONPATH so imports like 'from artifacts.shared.centralhub_redis_client' work
export PYTHONPATH="/app/artifacts:${PYTHONPATH}"

cd /app/gatekeeper

# Run main.py (this becomes the main process)
exec python -u main.py
