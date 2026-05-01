#!/bin/bash
# GateKeeper service entrypoint
# 1. Registers an initial Redis L1 heartbeat (fire-and-forget).
# 2. Starts main.py with Python.
set -e

# ── SCARE_LOG_DESTINATION diagnostics ─────────────────────────────────────────
if [ -n "${SCARE_LOG_DESTINATION}" ]; then
    echo "[entrypoint] [DEBUG] SCARE_LOG_DESTINATION=${SCARE_LOG_DESTINATION}"
    LOG_DIR=$(dirname "${SCARE_LOG_DESTINATION}")
    if [ -d "${LOG_DIR}" ]; then
        echo "[entrypoint] [DEBUG] ${LOG_DIR} exists: YES | writable: $([ -w "${LOG_DIR}" ] && echo YES || echo NO)"
        echo "[entrypoint] [DEBUG] ${LOG_DIR} contents: $(ls -la "${LOG_DIR}" 2>/dev/null | tail -5 || echo '(empty)')"
    else
        echo "[entrypoint] [DEBUG] ${LOG_DIR} does NOT exist — volume mount may have failed"
    fi
else
    echo "[entrypoint] [DEBUG] SCARE_LOG_DESTINATION is not set — file logging disabled"
fi
# ──────────────────────────────────────────────────────────────────────────────

# Start heartbeat daemon before main.py starts so the Launcher's heartbeat
# check succeeds even during a cold start. Run as background process (&).
python3 /app/artifacts/canonical/services/gatekeeper/heartbeat.py &
HEARTBEAT_PID=$!

# Add /app to PYTHONPATH so imports like 'from artifacts.shared.centralhub_redis_client' work
export PYTHONPATH="/app/artifacts:${PYTHONPATH}"

cd /app/gatekeeper

# Run main.py (this becomes the main process)
exec python -u main.py
