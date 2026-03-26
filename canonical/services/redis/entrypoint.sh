#!/bin/sh
#
# Redis service wrapper that starts Redis and registers heartbeat.
# Registers state:service:redis:available key in Redis every 60s with 180s TTL.
#

set -e

REDIS_PORT=${REDIS_PORT:-6380}
REDIS_PASSWORD=${REDIS_L1_PASSWORD:-scarerunner}
# REDIS_ADMIN_USERNAME: Admin user name (MUST be injected from settings.json redis:admin:username)
REDIS_ADMIN_USERNAME=${REDIS_ADMIN_USERNAME:-admin}
# REDIS_ADMIN_PASSWORD: Admin user password (MUST be injected from vault redis:admin:password)
# This is always injected by Launcher from vault, no random fallback needed.
if [ -z "$REDIS_ADMIN_PASSWORD" ]; then
  echo "[entrypoint] ❌ ERROR: REDIS_ADMIN_PASSWORD not set (must be injected by Launcher)"
  exit 1
fi
HEARTBEAT_INTERVAL=${HEARTBEAT_INTERVAL:-60}
HEARTBEAT_TTL=$((HEARTBEAT_INTERVAL * 3))

# ============================================================================
# Heartbeat function (runs in background)
# ============================================================================

heartbeat_loop() {
  # Disable 'set -e' for this loop so it doesn't exit on redis-cli failures
  set +e

  echo "[heartbeat] Starting heartbeat loop (interval: ${HEARTBEAT_INTERVAL}s, ttl: ${HEARTBEAT_TTL}s)"
  local attempt=0

  while true; do
    attempt=$((attempt + 1))
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Register availability key in Redis (capture stderr for debugging)
    local output
    output=$(redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" SET "state:service:redis:available" "1" EX $HEARTBEAT_TTL 2>&1)
    local status=$?

    if [ $status -eq 0 ]; then
      echo "[$timestamp] [heartbeat] ✓ Attempt $attempt: Key 'state:service:redis:available' refreshed with TTL ${HEARTBEAT_TTL}s"
    else
      echo "[$timestamp] [heartbeat] ❌ Attempt $attempt: Failed to set heartbeat key"
      echo "[$timestamp] [heartbeat]    Error: $output"
      echo "[$timestamp] [heartbeat]    Will retry in ${HEARTBEAT_INTERVAL}s..."
    fi

    sleep $HEARTBEAT_INTERVAL
  done

  # Re-enable 'set -e' if we somehow exit the loop
  set -e
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

echo "[entrypoint] Starting heartbeat loop in background..."
heartbeat_loop &
HEARTBEAT_PID=$!
echo "[entrypoint] Heartbeat loop PID: $HEARTBEAT_PID"

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
initial_output=$(redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" SET "state:service:redis:available" "1" EX $HEARTBEAT_TTL 2>&1)
initial_status=$?

if [ $initial_status -eq 0 ]; then
  echo "[entrypoint] ✅ Heartbeat registered: state:service:redis:available (TTL: ${HEARTBEAT_TTL}s)"
  echo "[entrypoint]    Key will be checked by Launcher at: state:service:redis:available"
else
  echo "[entrypoint] ❌ Failed to register initial heartbeat"
  echo "[entrypoint]    Error: $initial_output"
  echo "[entrypoint]    Background heartbeat loop will retry..."
fi

# ============================================================================
# Setup ACL: Read-Only User (default) + Admin User
# ============================================================================

echo "[entrypoint] Setting up Redis ACL..."

# Configure read-only default user
# - Can READ settings:* and vault:* (markers)
# - Can WRITE to request:secret:* (send secret requests)
# - Denied admin operations (FLUSHDB, FLUSHALL, ACL admin, etc.)
redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" ACL SETUSER default \
  on \
  ">$REDIS_PASSWORD" \
  '~*' '+get' '+mget' \
  '~request:secret:*' '~state:*' '+set' '+mset' \
  '-@all' '-@admin' \
  >/dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "[entrypoint] ✅ ACL: default (read-only) user configured"
else
  echo "[entrypoint] ⚠ ACL: failed to configure default user"
fi

# Configure admin user (for Launcher only)
# - Full access to all keys and commands
# - Username and password injected by Launcher
echo "[entrypoint] Creating admin user \"$REDIS_ADMIN_USERNAME\"..."
redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" ACL SETUSER "$REDIS_ADMIN_USERNAME" \
  on \
  ">$REDIS_ADMIN_PASSWORD" \
  '~*' \
  '+@all' \
  >/dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "[entrypoint] ✅ ACL: $REDIS_ADMIN_USERNAME (full-access) user configured"
else
  echo "[entrypoint] ⚠ ACL: failed to configure $REDIS_ADMIN_USERNAME user"
fi

# Persist ACL configuration to disk
redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" ACL SAVE >/dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "[entrypoint] ✅ ACL configuration saved (2 users: default read-only, admin full-access)"
else
  echo "[entrypoint] ⚠ ACL save failed (configuration may not persist across restart)"
fi

# ============================================================================
# Wait for Redis process to complete (keep container running)
# ============================================================================

echo "[entrypoint] Redis and heartbeat monitoring are running (PID: $$)..."
wait $REDIS_PID
