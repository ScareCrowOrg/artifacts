#!/bin/sh
#
# Redis service wrapper that starts Redis and registers heartbeat.
# Registers state:service:redis:available key in Redis every 60s with 180s TTL.
#

set -e

REDIS_PORT=${REDIS_PORT:-6380}
REDIS_PASSWORD=${REDIS_L1_PASSWORD:-scarerunner}
# REDIS_ADMIN_PASSWORD: Set this env var explicitly in production so the
# Launcher can use a known admin password (encrypted in vault).
# If not set, a random password is generated at startup – operators must
# set REDIS_ADMIN_PASSWORD when Launcher needs admin Redis access.
REDIS_ADMIN_PASSWORD=${REDIS_ADMIN_PASSWORD:-$(openssl rand -hex 16)}
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
  '~settings:*' '~vault:*' '~request:secret:*' '~state:*' \
  '+get' '+mget' '+set' '+mset' '+del' '+exists' '+keys' \
  '+scan' '+incr' '+decr' '+lpush' '+rpush' '+lpop' '+rpop' \
  '+lrange' '+sadd' '+srem' '+smembers' '+zadd' '+zrange' \
  '+@read' '+@write' \
  '-@admin' '-flushdb' '-flushall' \
  >/dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "[entrypoint] ✅ ACL: default (read-only) user configured"
else
  echo "[entrypoint] ⚠ ACL: failed to configure default user"
fi

# Configure admin user (for Launcher only)
# - Full access to all keys and commands
redis-cli -p $REDIS_PORT -a "$REDIS_PASSWORD" ACL SETUSER admin \
  on \
  ">$REDIS_ADMIN_PASSWORD" \
  '~*' \
  '+@all' \
  >/dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "[entrypoint] ✅ ACL: admin (full-access) user configured"
else
  echo "[entrypoint] ⚠ ACL: failed to configure admin user"
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
