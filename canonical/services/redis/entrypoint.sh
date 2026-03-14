#!/bin/sh
#
# Redis service wrapper that starts Redis and registers heartbeat.
# Registers state:service:redis:available key in Redis every 60s with 180s TTL.
#

set -e

REDIS_PORT=${REDIS_PORT:-6380}
REDIS_PASSWORD=${REDIS_L1_PASSWORD:-scarerunner}
HEARTBEAT_INTERVAL=${HEARTBEAT_INTERVAL:-60}
HEARTBEAT_TTL=$((HEARTBEAT_INTERVAL * 3))

# ============================================================================
# Heartbeat function (runs in background)
# ============================================================================

heartbeat_loop() {
  echo "[heartbeat] Starting heartbeat loop (interval: ${HEARTBEAT_INTERVAL}s, ttl: ${HEARTBEAT_TTL}s)"

  while true; do
    # Register availability key in Redis
    redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" SET "state:service:redis:available" "1" EX $HEARTBEAT_TTL >/dev/null 2>&1

    if [ $? -eq 0 ]; then
      echo "[heartbeat] ✓ state:service:redis:available refreshed (TTL: ${HEARTBEAT_TTL}s)"
    else
      echo "[heartbeat] ⚠ Failed to refresh heartbeat (will retry in ${HEARTBEAT_INTERVAL}s)"
    fi

    sleep $HEARTBEAT_INTERVAL
  done
}

# ============================================================================
# Graceful shutdown
# ============================================================================

trap_handler() {
  echo "[entrypoint] SIGTERM received, initiating graceful shutdown..."

  # Kill heartbeat loop
  if [ -n "$HEARTBEAT_PID" ]; then
    kill $HEARTBEAT_PID 2>/dev/null || true
  fi

  # Shutdown Redis gracefully
  echo "[entrypoint] Shutting down Redis..."
  redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" SHUTDOWN >/dev/null 2>&1 || true

  exit 0
}

trap trap_handler SIGTERM SIGINT

# ============================================================================
# Start heartbeat in background
# ============================================================================

echo "[entrypoint] Starting Redis service wrapper..."
echo "[entrypoint] REDIS_PORT=$REDIS_PORT"

# ============================================================================
# Start Redis server in BACKGROUND (not foreground yet)
# ============================================================================

echo "[entrypoint] ✅ Starting Redis server..."
redis-server --port $REDIS_PORT --appendonly yes --requirepass "$REDIS_PASSWORD" &
REDIS_PID=$!

heartbeat_loop &
HEARTBEAT_PID=$!

# ============================================================================
# Wait for Redis to be ready
# ============================================================================

echo "[entrypoint] Waiting for Redis to be ready..."
MAX_RETRIES=30
RETRIES=0

while [ $RETRIES -lt $MAX_RETRIES ]; do
  if redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" ping >/dev/null 2>&1; then
    echo "[entrypoint] ✅ Redis is ready"
    break
  fi

  RETRIES=$((RETRIES + 1))
  if [ $RETRIES -ge $MAX_RETRIES ]; then
    echo "[entrypoint] ❌ Redis failed to start after $MAX_RETRIES seconds"
    kill $HEARTBEAT_PID 2>/dev/null || true
    kill $REDIS_PID 2>/dev/null || true
    exit 1
  fi

  sleep 1
done

# ============================================================================
# Register initial heartbeat
# ============================================================================

echo "[entrypoint] Registering initial heartbeat..."
redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" SET "state:service:redis:available" "1" EX $HEARTBEAT_TTL >/dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "[entrypoint] ✅ Heartbeat registered: state:service:redis:available"
else
  echo "[entrypoint] ⚠ Failed to register initial heartbeat (will retry in background)"
fi

# ============================================================================
# Wait for Redis process to complete (keep container running)
# ============================================================================

echo "[entrypoint] Redis and heartbeat monitoring are running (PID: $$)..."
wait $REDIS_PID
