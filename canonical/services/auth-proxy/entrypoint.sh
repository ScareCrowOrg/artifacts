#!/bin/bash
#
# Auth-Proxy service entrypoint.
# 1. Starts heartbeat.py (fire-and-forget, registers in Redis and exits)
# 2. Runs /app/auth-proxy in foreground, optionally tee-ing to SCARE_LOG_DESTINATION
#

set -e

echo "[entrypoint] Starting Auth-Proxy service..."

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

# Start heartbeat in background (fire-and-forget)
# heartbeat.py will start asyncio task and exit immediately
python3 /app/heartbeat.py &

# Give heartbeat time to register
sleep 1

# Start auth-proxy binary in foreground, optionally tee-ing logs to file
if [ -n "${SCARE_LOG_DESTINATION}" ]; then
    echo "[entrypoint] Starting /app/auth-proxy (stdout+stderr → ${SCARE_LOG_DESTINATION})..."
    # Pipe stdout+stderr through tee to duplicate to file.
    # PIPESTATUS is a bash-specific feature; this entrypoint uses bash (see shebang).
    /app/auth-proxy 2>&1 | tee -a "${SCARE_LOG_DESTINATION}" &
    PROXY_PIPE_PID=$!
    # Forward SIGTERM/SIGINT to the auth-proxy process group for graceful shutdown
    trap 'kill -TERM $PROXY_PIPE_PID 2>/dev/null; wait $PROXY_PIPE_PID' TERM INT
    wait $PROXY_PIPE_PID
    exit $?
else
    echo "[entrypoint] Starting /app/auth-proxy..."
    exec /app/auth-proxy
fi
