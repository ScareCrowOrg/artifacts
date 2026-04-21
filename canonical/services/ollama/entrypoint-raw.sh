#!/bin/sh
#
# Ollama service entrypoint (replaces original entrypoint.sh for raw container).
# 1. Starts Ollama and waits for readiness
# 2. Starts heartbeat immediately (fire-and-forget, registers in Redis)
# 3. Pre-pulls models in background (non-blocking)
# 4. Runs Ollama in foreground (PID 1)
#

set -e

echo "[entrypoint] Starting Ollama service..."

# ============================================================================
# Start heartbeat FIRST (synchronous, before Ollama)
# ============================================================================
# This registers state:service:ollama:available in Redis L1 ASAP so Launcher
# knows the service is alive - doesn't wait for Ollama or models to finish.

echo "[entrypoint] Starting Ollama heartbeat registration (fire-and-forget)..."
echo "[entrypoint] PYTHONPATH=${PYTHONPATH}"
echo "[entrypoint] REDIS_L1_HOST=${REDIS_L1_HOST}"
echo "[entrypoint] REDIS_L1_PORT=${REDIS_L1_PORT}"

# Run heartbeat in background - outputs to stderr so docker logs captures it
echo "[entrypoint] About to execute: python3 /app/heartbeat.py"
python3 /app/heartbeat.py 2>&1 &
HEARTBEAT_PID=$!
echo "[entrypoint] Heartbeat process started with PID=$HEARTBEAT_PID"
sleep 1
if ps -p $HEARTBEAT_PID > /dev/null 2>&1; then
  echo "[entrypoint] ✅ Heartbeat process is running"
else
  echo "[entrypoint] ⚠️  Heartbeat process died immediately"
fi

# ============================================================================
# Start Ollama and wait for readiness
# ============================================================================

echo "[entrypoint] Starting Ollama server..."
/usr/bin/ollama serve &
OLLAMA_PID=$!

# ============================================================================
# Wait for Ollama to be ready (max 120s)
# ============================================================================

echo "[entrypoint] Waiting for Ollama to be ready..."
TIMEOUT=120
ELAPSED=0
while ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "[entrypoint] ERROR: Ollama failed to start within ${TIMEOUT}s"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  echo "[entrypoint] Still waiting... ($ELAPSED/${TIMEOUT}s)"
done

echo "[entrypoint] ✅ Ollama is ready!"

# ============================================================================
# Pre-pull models in background (non-blocking)
# ============================================================================
# Models download asynchronously while service remains available.
# If cache is already mounted and populated, this completes quickly.
# First startup with no cache takes 30-45 min, but service is accessible.

(
  echo "[entrypoint] Pre-pulling models in background..."

  # Models from artifacts/canonical/ai_models/README.md
  MODELS=(
    "mistral"           # 7B - general purpose
    "phi"               # 2.7B - fast, lightweight
    "phi3"              # 3.8B - Microsoft efficient
    "deepseek-coder"    # 6.7B - code generation
    "qwen2.5-coder"     # 14B - large code model
    "gemma"             # 7B - Google open model
  )

  for model in "${MODELS[@]}"; do
    echo "[entrypoint] Pulling $model..."
    if ollama pull "$model"; then
      echo "[entrypoint] ✅ $model pulled successfully"
    else
      echo "[entrypoint] ⚠️  Failed to pull $model (will retry on demand)"
    fi
  done

  echo "[entrypoint] ✅ Model initialization complete!"
) &
MODELS_PID=$!

# ============================================================================
# Keep Ollama running in foreground (PID 1)
# ============================================================================

echo "[entrypoint] ✅ Ollama service ready and discoverable"
wait $OLLAMA_PID
